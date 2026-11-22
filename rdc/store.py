from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .errors import RDCError


class Store:
    def __init__(self, state_dir):
        self.directory = Path(state_dir)
        if self.directory.is_symlink():
            raise RDCError('invalid_config', 'RDC state directory cannot be a symbolic link.')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != 'nt':
            self.directory.chmod(0o700)
        self.path = self.directory / 'rdc.sqlite3'
        if self.path.is_symlink():
            raise RDCError('invalid_config', 'RDC database cannot be a symbolic link.')
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, client_key TEXT UNIQUE,
                    spec TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL,
                    started_at REAL, finished_at REAL, heartbeat REAL, pid INTEGER, worker_pid INTEGER,
                    exit_code INTEGER, bytes_written INTEGER NOT NULL DEFAULT 0,
                    truncated INTEGER NOT NULL DEFAULT 0, cancel_requested INTEGER NOT NULL DEFAULT 0,
                    stdin_closed INTEGER NOT NULL DEFAULT 0, error TEXT
                );
                CREATE TABLE IF NOT EXISTS job_input (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                    text TEXT NOT NULL, close_input INTEGER NOT NULL, delivered INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, arguments TEXT NOT NULL,
                    digest TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL,
                    expires_at REAL NOT NULL, result TEXT, client_key TEXT UNIQUE
                );
            ''')
            db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('device_id', str(uuid.uuid4())))
            db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('paused', 'false'))
        if os.name != 'nt':
            self.path.chmod(0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=15000')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key, default=None):
        with self.connection() as db:
            row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            return row['value'] if row else default

    def set(self, key, value):
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, value))

    @property
    def device_id(self):
        return self.get('device_id')

    def job(self, identifier):
        with self.connection() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise RDCError('job_not_found', 'No job with that ID belongs to this worker.')
        data = dict(row)
        spec = json.loads(data.pop('spec'))
        data.update({key: spec[key] for key in ('argv', 'cwd', 'timeout')})
        data.pop('fingerprint')
        data['truncated'] = bool(data['truncated'])
        data['device_id'] = self.device_id
        return data

    def job_count(self, limit=100):
        """Match bounded list length without N+1 detailed job reads."""
        with self.connection() as db:
            total=db.execute('SELECT COUNT(*) AS n FROM jobs').fetchone()['n']
        return min(total,limit)

    def jobs(self, limit=100):
        with self.connection() as db:
            ids = [r['id'] for r in db.execute('SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?', (limit,))]
        return [self.job(identifier) for identifier in ids]

    def approvals_count(self, limit=100):
        """Keep expiration authoritative while avoiding JSON decoding."""
        with self.connection() as db:
            db.execute("UPDATE approvals SET status='expired' "
                       "WHERE status='pending' AND expires_at<?", (time.time(),))
            total=db.execute("SELECT COUNT(*) AS n FROM approvals "
                             "WHERE status='pending'").fetchone()['n']
        return min(total,limit)

    def approvals(self, limit=100):
        with self.connection() as db:
            db.execute("UPDATE approvals SET status='expired' WHERE status='pending' AND expires_at<?", (time.time(),))
            rows = db.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self.approval_data(row) for row in rows]

    @staticmethod
    def approval_data(row):
        data = dict(row)
        data['arguments'] = json.loads(data['arguments'])
        if data['result']:
            data['result'] = json.loads(data['result'])
        return data

