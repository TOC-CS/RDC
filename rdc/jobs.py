import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import time
import uuid

from .errors import RDCError


ACTIVE = ('queued', 'running', 'cancelling')


class Jobs:
    def __init__(self, settings, store, files):
        self.settings = settings
        self.store = store
        self.files = files
        self.directory = store.directory / 'jobs'
        self.directory.mkdir(exist_ok=True, mode=0o700)

    def reconcile(self):
        # Heartbeats belong to detached workers, not MCP connections. Do not infer
        # survival from a reused PID. A stale worker never becomes "completed".
        cutoff = time.time() - 120
        with self.store.connection() as db:
            db.execute("UPDATE jobs SET status='interrupted', finished_at=?, error=? "
                       "WHERE status IN ('queued','running','cancelling') AND COALESCE(heartbeat,created_at)<?",
                       (time.time(), 'Worker heartbeat expired; completion is unknown. Do not blindly retry side effects.', cutoff))

    def start(self, argv, cwd, timeout=None, idempotency_key=None):
        if not self.settings.allow_exec:
            raise RDCError('capability_disabled', 'Command execution is disabled in the owner configuration.')
        directory = self.files.resolve(cwd, directory=True)
        timeout = timeout if timeout is not None else self.settings.job_timeout
        if timeout > self.settings.job_timeout:
            raise RDCError('invalid_arguments', 'Timeout exceeds the owner-configured job timeout.')
        payload = {'argv':argv, 'cwd':str(directory), 'timeout':timeout,
                   'max_output_bytes':self.settings.max_output_bytes}
        encoded = json.dumps(payload, sort_keys=True, separators=(',',':'))
        fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
        self.reconcile()
        identifier = str(uuid.uuid4())
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if idempotency_key is not None:
                previous = db.execute('SELECT id,fingerprint FROM jobs WHERE client_key=?', (idempotency_key,)).fetchone()
                if previous:
                    if previous['fingerprint'] != fingerprint:
                        raise RDCError('idempotency_conflict', 'This retry key already belongs to different command arguments.')
                    return {'job': self.store.job(previous['id']), 'reused': True}
            count = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running','cancelling')").fetchone()[0]
            if count >= self.settings.max_concurrent_jobs:
                raise RDCError('capacity', 'Worker job capacity is full. Wait or cancel an existing job.')
            db.execute('INSERT INTO jobs(id,fingerprint,client_key,spec,status,created_at) VALUES (?,?,?,?,?,?)',
                       (identifier, fingerprint, idempotency_key, encoded, 'queued', time.time()))
        environment = os.environ.copy()
        package_root = str(Path(__file__).resolve().parent.parent)
        environment['PYTHONPATH'] = package_root + (os.pathsep + environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
        kwargs = {'start_new_session':True} if os.name != 'nt' else {
            'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
        try:
            with open(self.directory/f'{identifier}.worker.log', 'ab') as errors:
                process = subprocess.Popen([sys.executable, '-m', 'rdc.worker', str(self.store.directory), identifier],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors,
                                           cwd=package_root, env=environment, close_fds=True, **kwargs)
            # Keep no pipe tied to the MCP server. The job worker owns its process tree.
            with self.store.connection() as db:
                db.execute('UPDATE jobs SET worker_pid=? WHERE id=?', (process.pid, identifier))
            # Reap our launcher after it exits without tying worker lifetime to this instance.
            import threading
            threading.Thread(target=process.wait, daemon=True).start()
        except OSError as exc:
            with self.store.connection() as db:
                db.execute("UPDATE jobs SET status='failed', finished_at=?, error=? WHERE id=?",
                           (time.time(), str(exc), identifier))
            raise RDCError('launch_failed', 'Could not start the durable worker.', {'job_id':identifier}) from exc
        return {'job':self.store.job(identifier), 'reused':False}

    def status(self, job_id):
        self.reconcile()
        return {'job':self.store.job(job_id)}

    def list(self, limit=100):
        self.reconcile()
        return {'jobs':self.store.jobs(limit)}

    def output(self, job_id, offset=0, limit=65536):
        job = self.status(job_id)['job']
        path = self.directory/f'{job_id}.output'
        limit = min(limit, self.settings.max_read_bytes)
        if path.exists():
            with open(path, 'rb') as source:
                size = os.fstat(source.fileno()).st_size
                if offset > size:
                    raise RDCError('invalid_offset', 'Output offset is beyond the saved log.', {'bytes_available':size})
                source.seek(offset)
                data = source.read(limit)
        else:
            size = 0
            data = b''
            if offset:
                raise RDCError('invalid_offset', 'No output is available at that offset.')
        return {'job_id':job_id, 'device_id':self.store.device_id, 'offset':offset,
                'next_offset':offset+len(data), 'text':data.decode('utf-8', errors='replace'),
                'encoding':'utf-8', 'offset_unit':'bytes', 'status':job['status'],
                'complete':job['status'] not in ACTIVE, 'truncated':job['truncated'], 'bytes_available':size}

    def preview(self, job_id=None):
        """Allowlisted persisted state and an explicitly selected bounded tail."""
        self.reconcile()
        fields = 'id,status,created_at,started_at,finished_at,exit_code,bytes_written,truncated'
        with self.store.connection() as db:
            rows = db.execute(f"SELECT {fields} FROM jobs ORDER BY "
                              "CASE WHEN status IN ('queued','running','cancelling') THEN 0 ELSE 1 END,created_at DESC LIMIT 11").fetchall()
            active = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running','cancelling')").fetchone()[0]
            selected = db.execute(f'SELECT {fields} FROM jobs WHERE id=?', (job_id,)).fetchone() if job_id else None
        jobs = [{**{key:row[key] for key in row.keys() if key!='id'},
                 'job_id':row['id'],'truncated':bool(row['truncated'])} for row in rows[:10]]
        result = {'jobs':jobs,'jobs_truncated':len(rows)>10,'active_jobs':active}
        if job_id:
            if selected is None:
                raise RDCError('job_not_found','No job with that ID belongs to this worker.')
            result['job_output'] = self._preview_tail(job_id, selected)
        return result

    def _preview_tail(self, job_id, job):
        # Fail closed on redirected/nonregular logs. The selected byte slice is
        # actual stdout/stderr, never a command reconstruction or synthetic feed.
        path = self.directory/f'{job_id}.output'
        size = offset = 0
        data = b''
        try:
            if not hasattr(os, 'O_NOFOLLOW') and path.is_symlink():
                raise OSError('Redirected output')
            descriptor = os.open(path, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))
            with os.fdopen(descriptor, 'rb') as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise OSError('Nonregular output')
                size = info.st_size
                offset = max(0, size-min(8192,self.settings.max_read_bytes))
                source.seek(offset)
                data = source.read(min(8192,self.settings.max_read_bytes))
        except FileNotFoundError:
            pass
        except OSError:
            raise RDCError('output_unavailable','The selected job output is unavailable.') from None
        return {'job_id':job_id,'offset':offset,'next_offset':offset+len(data),
                'text':data.decode('utf-8',errors='replace'),'bytes_available':size,
                'complete':job['status'] not in ACTIVE,'truncated':bool(job['truncated']) or offset>0,
                'encoding':'utf-8','offset_unit':'bytes'}

    def cancel(self, job_id):
        job = self.store.job(job_id)
        if job['status'] in ACTIVE:
            with self.store.connection() as db:
                db.execute("UPDATE jobs SET cancel_requested=1 WHERE id=? AND status IN ('queued','running','cancelling')", (job_id,))
        return {'job':self.store.job(job_id), 'cancel_requested':True}

    def input(self, job_id, text='', close=False):
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status,stdin_closed FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row:
                raise RDCError('job_not_found', 'No job with that ID belongs to this worker.')
            if row['status'] not in ACTIVE or row['stdin_closed']:
                raise RDCError('stdin_closed', 'This job no longer accepts input.')
            pending = db.execute('SELECT COALESCE(sum(length(CAST(text AS BLOB))),0) FROM job_input WHERE job_id=? AND delivered=0', (job_id,)).fetchone()[0]
            if pending + len(text.encode()) > self.settings.max_read_bytes:
                raise RDCError('input_too_large', 'Queued input exceeds the worker input limit.')
            cursor = db.execute('INSERT INTO job_input(job_id,text,close_input) VALUES (?,?,?)', (job_id,text,int(close)))
            if close:
                db.execute('UPDATE jobs SET stdin_closed=1 WHERE id=?', (job_id,))
        return {'job_id':job_id, 'input_id':cursor.lastrowid, 'queued':True, 'close':close}

