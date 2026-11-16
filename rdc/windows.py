"""Exact native-window preview bindings; never substitute a display or focus target."""
import hashlib
import json
import os
import platform
import plistlib
from pathlib import Path
import subprocess
import re
import sys
import threading
import time
import uuid

from .errors import RDCError


def fail(code, message):
    raise RDCError(code, message)


class MacWindowBackend:
    def __init__(self, state_dir):
        self.state_dir = Path(state_dir)
        self.lock = threading.Lock()

    def prepare(self):
        if sys.platform != 'darwin':
            fail('window_capture_unavailable', 'Window previews currently require macOS 14 or later.')
        source = Path(__file__).with_name('native') / 'WindowPreview.swift'
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:24]
        folder = self.state_dir / 'native-window-helper'
        bundle=folder/'RDC Window Preview.app'
        binary=bundle/'Contents'/'MacOS'/'rdc-window-preview'
        stamp=folder/'source-sha256'
        with self.lock:
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not binary.exists() or not stamp.exists() or stamp.read_text()!=digest:
                temporary = folder / ('build-' + str(uuid.uuid4()))
                try:
                    sdk_path=subprocess.run(['/usr/bin/xcrun','--show-sdk-path'],capture_output=True,text=True,timeout=10)
                    sdks=[]
                    host=tuple(int(x) for x in platform.mac_ver()[0].split('.')[:2])
                    for path in Path(sdk_path.stdout.strip()).parent.glob('MacOSX*.sdk'):
                        match=re.fullmatch(r'MacOSX(\d+)\.(\d+)\.sdk',path.name)
                        if match and int(match[1])>=14: sdks.append((tuple(map(int,match.groups())),path))
                    compatible=[item for item in sdks if item[0]<=host]
                    chosen=max(compatible)[1] if compatible else min(sdks)[1] if sdks else None
                    sdk_args=['-sdk',str(chosen)] if chosen else []
                    built = subprocess.run(['/usr/bin/xcrun','swiftc','-parse-as-library','-O',*sdk_args,
                        '-target',platform.machine()+'-apple-macosx14.0',
                        '-module-cache-path',str(folder/'module-cache'),str(source),'-o',str(temporary)],
                        capture_output=True, timeout=300)
                    if built.returncode:
                        fail('window_capture_unavailable', 'The native window helper could not build. Install the Apple command-line tools and inspect the build separately.')
                    temporary.chmod(0o700)
                    binary.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                    os.replace(temporary,binary)
                    (bundle/'Contents'/'Info.plist').write_bytes(plistlib.dumps({
                        'CFBundleIdentifier':'org.tocministries.rdc.window-preview',
                        'CFBundleName':'RDC Window Preview','CFBundleExecutable':'rdc-window-preview',
                        'CFBundlePackageType':'APPL','CFBundleVersion':'6','LSUIElement':True,
                        'NSHighResolutionCapable':True}))
                    signed=subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(bundle)],capture_output=True,timeout=20)
                    if signed.returncode: fail('window_capture_unavailable','The native window helper could not be signed locally.')
                    stamp.write_text(digest)
                except (OSError,subprocess.TimeoutExpired):
                    fail('window_capture_unavailable','The native helper build could not finish. Complete native helper setup before opening the preview.')
                finally:
                    temporary.unlink(missing_ok=True)
        return binary

    def __call__(self, action, **arguments):
        binary=self.prepare()
        try:
            result = subprocess.run([str(binary)],input=json.dumps({'action':action,**arguments}).encode(),
                                    capture_output=True,timeout=15)
            if len(result.stdout)>12*1024*1024: raise ValueError
            data=json.loads(result.stdout)
        except (OSError,subprocess.TimeoutExpired,ValueError):
            fail('window_capture_unavailable','The native window operation could not be confirmed. Inspect the window before retrying a resize.')
        if data.get('ok') is not True:
            code=data.get('code')
            messages={
                'screen_permission_required':'macOS Screen Recording permission is required for the window capture helper.',
                'accessibility_permission_required':'Enable RDC Window Preview in System Settings > Privacy & Security > Accessibility to resize this window. If missing, run the owner setup: rdc setup-macos. The older RDC entry is separate; capture can continue.',
                'session_not_found':'The bound native window is no longer available.',
                'window_ambiguous':'The exact Accessibility window could not be identified; nothing was resized.',
                'resize_unavailable':'The application does not allow this window to be resized.',
                'window_capture_unavailable':'The native window operation failed; no desktop fallback was used.',
            }
            fail(code if code in messages else 'window_capture_unavailable',messages.get(code,messages['window_capture_unavailable']))
        return data


class Windows:
    def __init__(self, settings, backend=None):
        self.settings=settings
        self.backend=backend or MacWindowBackend(getattr(settings,'state_dir',Path('/tmp/rdc-unconfigured')))
        self.targets={}
        self.sessions={}
        self.resize_requests={}
        self.lock=threading.RLock()

    def _allowed(self):
        if self.settings.desktop_mode=='disabled':
            fail('adapter_disabled','Native window capture requires the existing owner desktop grant.')

    @staticmethod
    def _identity(row):
        return {key:row[key] for key in ('window_id','pid','launch_id')}

    def list(self):
        with self.lock:
            self._allowed()
            rows=self.backend('list').get('windows',[])[:128]
            self.targets={}
            result=[]
            for row in rows:
                target_id=str(uuid.uuid4())
                self.targets[target_id]={'row':dict(row),'expires':time.monotonic()+120}
                result.append({key:row[key] for key in ('title','bundle_id','width','height') if key in row} | {'target_id':target_id})
            return {'windows':result}

    def _current(self, row):
        wanted=self._identity(row)
        matches=[item for item in self.backend('list').get('windows',[]) if self._identity(item)==wanted]
        if len(matches)!=1:
            fail('session_not_found','The bound native window has ended or changed identity.')
        return matches[0]

    def open(self, target_id, resize_to_view=False):
        with self.lock:
            self._allowed()
            target=self.targets.get(target_id)
            if not target or target['expires']<time.monotonic():
                fail('stale_observation','List native windows again before binding one.')
            row=self._current(target['row'])
            for session in self.sessions.values():
                if self._identity(session)==self._identity(row):
                    # Existing bindings are never silently granted resizing.
                    if session['resize_to_view']!=resize_to_view:
                        fail('window_already_bound','This window already has a binding with different resize authorization.')
                    return self._info(session)
            if len(self.sessions)>=8: fail('session_limit','At most eight native window previews may be bound.')
            session={**row,'session_id':'window-'+str(uuid.uuid4()),'resize_to_view':resize_to_view}
            self.sessions[session['session_id']]=session
            return self._info(session)

    @staticmethod
    def _info(session):
        return {key:session[key] for key in ('session_id','title','bundle_id','width','height','resize_to_view') if key in session}

    def _session(self, session_id):
        self._allowed()
        session=self.sessions.get(session_id)
        if session is None: fail('session_not_found','Native window preview binding has ended.')
        try: row=self._current(session)
        except RDCError as error:
            if error.code=='session_not_found': self.sessions.pop(session_id,None)
            raise
        session.update(row)
        return session

    def snapshot(self, session_id):
        with self.lock:
            session=self._session(session_id)
            try: shot=self.backend('capture',**self._identity(session))
            except RDCError as error:
                if error.code=='session_not_found': self.sessions.pop(session_id,None)
                raise
            return {**shot,'session_id':session_id,'resize_to_view':session['resize_to_view']}

    def resize(self, session_id, width, height, request_id=None):
        with self.lock:
            signature=(session_id,width,height)
            if request_id in self.resize_requests:
                previous=self.resize_requests[request_id]
                if previous['signature']!=signature: fail('request_id_conflict','This resize request ID belongs to different dimensions.')
                if previous['result'] is None: fail('outcome_unknown','The original resize could not be confirmed and will not be repeated.')
                return dict(previous['result'])
            session=self._session(session_id)
            if not session['resize_to_view']: fail('resize_not_enabled','This window was not opened with resize-to-view authorization.')
            if type(width) is not int or type(height) is not int or not 240<=width<=2560 or not 180<=height<=1600:
                fail('invalid_arguments','Window dimensions are outside the supported range.')
            if request_id:
                if len(self.resize_requests)>=512: fail('request_limit','This worker has reached its retained resize-request limit.')
                self.resize_requests[request_id]={'signature':signature,'result':None}
            try: result=self.backend('resize',**self._identity(session),width=width,height=height)
            except RDCError as error:
                if error.code=='session_not_found': self.sessions.pop(session_id,None)
                # These helper failures happen before AXSetAttributeValue.
                # Uncertain execution remains a tombstone and is never replayed.
                if error.code in ('screen_permission_required','accessibility_permission_required','window_ambiguous'):
                    self.resize_requests.pop(request_id,None)
                raise
            session.update(width=result['width'],height=result['height'])
            reply={**self._info(session),'size_constrained':abs(result['width']-width)>2 or abs(result['height']-height)>2}
            if request_id: self.resize_requests[request_id]['result']=reply
            return reply

    def require_resize_authorization(self, session_id):
        with self.lock:
            self._allowed()
            session=self.sessions.get(session_id)
            if session is None: fail('session_not_found','Native window preview binding has ended.')
            if not session['resize_to_view']: fail('resize_not_enabled','This window binding does not authorize pane-driven resizing.')

    def close(self, session_id):
        with self.lock:
            self.sessions.pop(session_id,None)
            return {'session_id':session_id,'closed':True,'window_keeps_running':True}

    def status(self):
        with self.lock:
            return {'sessions':[self._info(s) for s in self.sessions.values()]}
