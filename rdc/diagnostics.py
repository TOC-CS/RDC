"""Bounded local diagnostics. No caller text is persisted or exported.

SQLite operates in memory; its serialized image is read/written through checked
file descriptors. sqlite3 never opens a caller-controlled filesystem path.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import queue
import sqlite3
import stat
import threading
import time

MAX_QUEUE = 256
MAX_EVENTS = 2048
MAX_STORE_BYTES = 2 * 1024 * 1024
# Event -> (component, severity, recovery). These are the only stored strings.
EVENTS = {
    'operation_failed': ('worker', 'error', 'verified_repair_or_owner_action'),
    'unexpected_error': ('worker', 'error', 'verified_repair_or_owner_action'),
    'connection_interrupted': ('relay', 'warning', 'transport_retry'),
    'reconnect_attempt': ('relay', 'info', 'transport_retry'),
    'reconnected': ('relay', 'info', 'transport_restored'),
    'permanent_failure': ('relay', 'error', 'owner_action'),
    'outcome_unknown': ('relay', 'error', 'inspect_before_new_action'),
    'interrupted_before_dispatch': ('relay', 'warning', 'no_replay'),
    'worker_rejected': ('relay', 'error', 'owner_action'),
    'result_upload_retry': ('relay', 'warning', 'result_upload_only'),
    'result_uploaded': ('relay', 'info', 'result_delivery_confirmed'),
    'result_undeliverable': ('relay', 'error', 'inspect_before_new_action'),
}
TOOLS = frozenset(('files', 'jobs', 'browser', 'mobile', 'desktop', 'credentials', 'system', 'other'))


def _tool_category(tool):
    if type(tool) is not str:
        return 'other'
    for prefix, category in (('rdc_file_', 'files'), ('rdc_directory_', 'files'),
                             ('rdc_job_', 'jobs'), ('rdc_browser_', 'browser'),
                             ('rdc_mobile_', 'mobile'), ('rdc_desktop_', 'desktop'),
                             ('rdc_credentials_', 'credentials'), ('rdc_system_', 'system'),
                             ('rdc_diagnostics_', 'system'), ('rdc_preview_', 'system')):
        if tool.startswith(prefix):
            return category
    return 'other'


def safe_record(recorder, component, event, tool=None):
    """Diagnostics failure must never replace an operation result/exception."""
    try:
        if recorder is not None:
            recorder.record(component, event, tool)
    except Exception:
        pass


def _limit(value):
    if type(value) is not int or not 1 <= value <= 50:
        raise ValueError('diagnostic limit must be an integer from 1 to 50')
    return value


def _empty():
    return {'available': False, 'incomplete': True, 'storage_status': 'unavailable', 'retained_events': 0,
            'events': [], 'totals': {}, 'dropped_events': 0, 'invalid_events': 0,
            'pending_events': 0, 'capture_scope': 'retained_history_and_current_process',
            'recovery_scope': 'observations_only_no_action_replay_or_code_installation'}


class Diagnostics:
    """Nonblocking finite submissions with a bounded, daemon background writer.

    state_dir must already exist and be private. No disk access occurs on record.
    close waits at most 250ms, and reports pending/incomplete capture afterwards.
    read_status does not create directories, locks, databases or writer threads.
    """
    def __init__(self, state_dir):
        self._state = Path(state_dir).expanduser().absolute()
        self._queue = queue.Queue(MAX_QUEUE)
        self._closing = threading.Event()
        self._lock = threading.Lock()
        self._failed = False
        self._dropped = 0
        self._invalid = 0
        self._active = 0
        self._unreported_drops = 0
        self._thread = threading.Thread(target=self._run, name='rdc-diagnostics', daemon=True)
        self._thread.start()

    def record(self, component, event, tool=None):
        if (type(component) is not str or type(event) is not str or
                event not in EVENTS or EVENTS[event][0] != component):
            with self._lock:
                self._invalid += 1
            return
        record = (time.time(), component, event, EVENTS[event][1], _tool_category(tool), EVENTS[event][2])
        with self._lock:
            if self._closing.is_set():
                self._dropped += 1; self._unreported_drops += 1
                return
            try:
                self._queue.put_nowait(record)
            except queue.Full:
                self._dropped += 1; self._unreported_drops += 1

    @staticmethod
    def _private(info, directory=False):
        if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
            raise ValueError
        if os.name != 'nt' and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError

    @staticmethod
    def _supported():
        return os.name == 'posix' and hasattr(os, 'O_NOFOLLOW') and os.open in os.supports_dir_fd

    @contextmanager
    def _directory(self, create=False):
        # Descriptor-relative nofollow operations are available on supported Unix
        # workers, including macOS. Fail closed on platforms lacking them.
        if not self._supported():
            raise OSError('safe descriptor-relative diagnostics unavailable')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
        parent = os.open(self._state, flags)
        child = None
        try:
            self._private(os.fstat(parent), True)
            if create:
                try: os.mkdir('diagnostics', mode=0o700, dir_fd=parent)
                except FileExistsError: pass
            child = os.open('diagnostics', flags, dir_fd=parent)
            self._private(os.fstat(child), True)
            # Refuse a directory path replaced since it was opened. Subsequent
            # I/O still uses pinned descriptors, never the replacement path.
            for observed, expected in ((os.stat(self._state, follow_symlinks=False), os.fstat(parent)),
                                       (os.stat('diagnostics', dir_fd=parent, follow_symlinks=False), os.fstat(child))):
                if (observed.st_dev, observed.st_ino) != (expected.st_dev, expected.st_ino):
                    raise ValueError
            yield child
        finally:
            if child is not None: os.close(child)
            os.close(parent)

    @contextmanager
    def _file(self, directory, name, write=False):
        flags = (os.O_RDWR | os.O_CREAT) if write else os.O_RDONLY
        fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
        try:
            info = os.fstat(fd); self._private(info)
            if info.st_nlink != 1 or info.st_size > MAX_STORE_BYTES:
                raise ValueError
            yield fd
        finally:
            os.close(fd)

    @staticmethod
    def _load(fd):
        os.lseek(fd, 0, os.SEEK_SET)
        chunks = []; size = 0
        while True:
            chunk = os.read(fd, min(65536, MAX_STORE_BYTES + 1 - size))
            if not chunk: break
            chunks.append(chunk); size += len(chunk)
            if size > MAX_STORE_BYTES: raise ValueError
        db = sqlite3.connect(':memory:')
        # A replaced store may contain recursive views or expensive SQL. The
        # finite file bound alone does not bound query execution.
        deadline = time.monotonic() + .1
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_STORE_BYTES)
        try:
            db.execute('PRAGMA trusted_schema=OFF')
            if size:
                db.deserialize(b''.join(chunks))
            else:
                db.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, time REAL, component TEXT, event TEXT, severity TEXT, tool TEXT, recovery TEXT)')
                db.execute('CREATE TABLE capture (id INTEGER PRIMARY KEY CHECK(id=1), dropped INTEGER)')
                db.execute('INSERT INTO capture VALUES (1,0)')
                db.commit()
            return db
        except Exception:
            db.close(); raise

    @staticmethod
    @contextmanager
    def _locked(fd, write=False):
        import fcntl
        for attempt in range(6 if write else 1):
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not write or attempt == 5: raise
                # Only the background writer waits, at most 50ms per batch.
                time.sleep(.01)
        try: yield
        finally: fcntl.flock(fd, fcntl.LOCK_UN)

    def _persist(self, records):
        with self._directory(create=True) as directory:
            with self._file(directory, 'events.lock', True) as lock:
                with self._locked(lock, True), self._file(directory, 'events.sqlite3', True) as fd:
                    db = self._load(fd)
                    try:
                        with self._lock: drops = self._unreported_drops
                        with db:
                            db.executemany('INSERT INTO events (time,component,event,severity,tool,recovery) VALUES (?,?,?,?,?,?)', records)
                            db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?)', (MAX_EVENTS,))
                            db.execute('UPDATE capture SET dropped=dropped+? WHERE id=1', (drops,))
                        data = db.serialize()
                        if len(data) > MAX_STORE_BYTES: raise ValueError
                        os.lseek(fd, 0, os.SEEK_SET)
                        view = memoryview(data)
                        while view:
                            written = os.write(fd, view)
                            if written <= 0: raise OSError
                            view = view[written:]
                        os.ftruncate(fd, len(data))
                        os.fsync(fd)
                        with self._lock:
                            self._unreported_drops -= drops
                            self._failed = False
                    finally:
                        db.close()

    def _run(self):
        while not self._closing.is_set() or not self._queue.empty():
            try: first = self._queue.get(timeout=.02)
            except queue.Empty: continue
            records = [first]
            while len(records) < MAX_QUEUE:
                try: records.append(self._queue.get_nowait())
                except queue.Empty: break
            with self._lock: self._active = len(records)
            try:
                self._persist(records)
            except Exception:
                with self._lock:
                    self._failed = True
                    self._dropped += len(records); self._unreported_drops += len(records)
            finally:
                with self._lock: self._active = 0
                for _ in records: self._queue.task_done()

    def _read(self, limit):
        report = _empty()
        if not self._supported():
            report['storage_status'] = 'unsupported_platform'
            return report
        try:
            with self._directory() as directory:
                with self._file(directory, 'events.lock') as lock:
                    with self._locked(lock), self._file(directory, 'events.sqlite3') as fd:
                        db = self._load(fd)
                        try:
                            count = db.execute('SELECT count(*) FROM events').fetchone()[0]
                            if count > MAX_EVENTS: raise ValueError
                            rows = db.execute('SELECT time,component,event,severity,tool,recovery FROM events ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
                            # Validate even persisted bytes. An externally edited
                            # store cannot turn this report into a text export.
                            events = []
                            for timestamp, component, event, severity, tool, recovery in rows:
                                if (type(timestamp) not in (float, int) or not 0 <= timestamp < 2**53 or
                                        type(event) is not str or event not in EVENTS or
                                        (component, severity, recovery) != EVENTS[event] or tool not in TOOLS):
                                    raise ValueError
                                events.append(dict(time=timestamp, component=component, event=event, severity=severity, tool=tool, recovery=recovery))
                            totals = {}
                            for event, total in db.execute('SELECT event,count(*) FROM events GROUP BY event'):
                                if event not in EVENTS: raise ValueError
                                totals[event] = total
                            dropped = db.execute('SELECT dropped FROM capture WHERE id=1').fetchone()[0]
                            if type(dropped) is not int or not 0 <= dropped < 2**63: raise ValueError
                            report.update(available=True, incomplete=bool(dropped), storage_status='ready', retained_events=count,
                                          events=events, totals=totals, dropped_events=dropped)
                        finally: db.close()
        except Exception:
            pass
        return report

    def snapshot(self, limit=50):
        _limit(limit)
        report = self._read(limit)
        with self._lock:
            pending = self._queue.qsize() + self._active
            report.update(pending_events=pending, invalid_events=self._invalid)
            report['dropped_events'] += self._unreported_drops
            report['incomplete'] = report['incomplete'] or bool(pending or self._unreported_drops or self._failed)
            if self._failed:
                report['available'] = False
                if report['storage_status'] != 'unsupported_platform': report['storage_status'] = 'unavailable'
        return report

    @classmethod
    def read_status(cls, state_dir, limit=50):
        _limit(limit)
        reader = object.__new__(cls)
        reader._state = Path(state_dir).expanduser().absolute()
        report = reader._read(limit)
        report['capture_scope'] = 'retained_history_only_live_process_counters_unavailable'
        return report

    def close(self):
        self._closing.set()
        self._thread.join(timeout=.25)
