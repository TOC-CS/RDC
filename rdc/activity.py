"""Bounded metadata about actual admitted work. Never retain caller arguments."""
from collections import deque
import copy
import re
import threading
import time
import uuid


# Observers are deliberately absent: opening or polling a viewer cannot become
# the work it follows. Page/native observe is agent work and can select focus.
VISUAL_ACTIONS = {
    'rdc_browser_'+action for action in ('start','observe','navigate','click','fill','pointer','keys','close')
} | {
    'rdc_mobile_'+action for action in ('start','observe','tap','fill','swipe','close')
} | {
    'rdc_desktop_'+action for action in ('pointer','keys','type')
} | {
    'rdc_android_'+action for action in ('tap','input','key','swipe','long_press','launch_app')
}
JOB_ACTIONS = {'rdc_job_start', 'rdc_job_run', 'rdc_job_cancel', 'rdc_job_input'}
FILE_ACTIONS = {'rdc_file_read','rdc_file_read_many','rdc_file_search','rdc_file_write','rdc_file_edit','rdc_directory_create'}
SESSION_ID = re.compile(r'^(?:(?:mobile-)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|desktop|android-adb)$')


def _session_id(value):
    return isinstance(value,str) and SESSION_ID.fullmatch(value) is not None


class Activity:
    def __init__(self):
        self._lock = threading.Lock()
        self._current = {}
        self._active_count = 0
        self._recent = deque(maxlen=20)
        self._focus = {}
        self._sequence = 0

    def begin(self, name, arguments):
        if name not in VISUAL_ACTIONS | JOB_ACTIONS | FILE_ACTIONS:
            return None
        row = {'activity_id':str(uuid.uuid4()), 'tool':name, 'started_at':time.time()}
        target = ('desktop' if name.startswith('rdc_desktop_') else
                  'android-adb' if name.startswith('rdc_android_') else arguments.get('session_id'))
        if _session_id(target):
            row['session_id'] = target
        # The caller holds this small token for completion; only the visible
        # current-record map is capped, with an accurate truncation indicator.
        with self._lock:
            self._active_count += 1
            if len(self._current) < 32:
                self._current[row['activity_id']] = row
        return row

    def finish(self, token, result=None, success=False):
        if token is None:
            return
        row = {**token, 'status':'completed' if success else 'failed', 'finished_at':time.time()}
        if success and isinstance(result, dict):
            if _session_id(result.get('session_id')):
                row['session_id'] = result['session_id']
            job = result.get('job')
            if isinstance(job, dict) and job.get('id'):
                row['job_id'] = job['id']
        with self._lock:
            self._active_count -= 1
            self._current.pop(row['activity_id'], None)
            self._recent.appendleft(row)
            session = row.get('session_id')
            if success and session and row['tool'] in VISUAL_ACTIONS:
                if isinstance(result, dict) and result.get('closed'):
                    self._focus.pop(session, None)
                else:
                    self._sequence += 1
                    self._focus[session] = {'session_id':session, 'sequence':self._sequence,
                                           'tool':row['tool'], 'completed_at':row['finished_at']}
                    # At most sixteen visual sessions and two configured native
                    # targets are live. Retire oldest metadata even before a read.
                    if len(self._focus) > 18:
                        self._focus.pop(min(self._focus, key=lambda key:self._focus[key]['sequence']))

    def snapshot(self, live_session_ids):
        with self._lock:
            # Session metadata can precede a concurrent successful start. Filter
            # this response without discarding the newer work's focus history.
            focus = max((value for key,value in self._focus.items() if key in live_session_ids),
                        key=lambda row:row['sequence'], default=None)
            return copy.deepcopy({'focus':focus,
                'current_operations':sorted(self._current.values(), key=lambda row:row['started_at'], reverse=True),
                'current_operations_truncated':self._active_count > len(self._current),
                'recent_operations':list(self._recent)})
