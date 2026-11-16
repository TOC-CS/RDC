from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid

from jsonschema import Draft202012Validator

from . import __version__
from .activity import Activity
from .diagnostics import Diagnostics, safe_record
from .errors import RDCError
from .files import Files
from .jobs import Jobs
from .store import Store


def tool(name, description, properties=None, required=(), mutating=False, **flags):
    return {'name':name, 'description':description, 'inputSchema':{'type':'object',
            'properties':properties or {}, 'required':list(required), 'additionalProperties':False},
            'annotations':{'readOnlyHint':not mutating, 'destructiveHint':mutating,
                           'idempotentHint':not mutating, 'openWorldHint':flags.get('open_world',False)},
            'x-rdc-mutating':mutating}


STRING = {'type':'string','minLength':1,'maxLength':4096}
JOB_ID = {'type':'string','pattern':r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'}
PREVIEW_SESSION_ID = {'type':'string','pattern':r'^(?:(?:(?:mobile|window)-)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|desktop|android-adb)$'}
SHA = {'type':'string','pattern':r'^[0-9a-f]{64}$'}
LIMIT = {'type':'integer','minimum':1,'maximum':262144}


class Engine:
    def __init__(self, settings):
        self.settings = settings
        self.store = Store(settings.state_dir)
        self.files = Files(settings)
        self.jobs = Jobs(settings,self.store,self.files)
        self._input_lock = threading.RLock()
        self.activity = Activity()
        try:
            from .adapters import Adapters
            self.adapters = Adapters(settings)
        except ModuleNotFoundError as exc:
            if exc.name != 'rdc.adapters':
                raise
            self.adapters = None
        from .credentials import CredentialBroker
        self.credentials = CredentialBroker(self)
        self._tools = {item['name']:item for item in self._catalog()}
        self._validators = {name:Draft202012Validator(item['inputSchema']) for name,item in self._tools.items()}
        try:
            self.diagnostics = Diagnostics(settings.state_dir)
        except Exception:
            self.diagnostics = None

    def _catalog(self):
        content = {'type':'string','maxLength':self.settings.max_read_bytes}
        items = [
            tool('rdc_system_status','Get worker identity, permissions, capability status and counts.'),
            tool('rdc_diagnostics_status','Read bounded private incident categories and observed recovery outcomes. '
                 'Does not repair code, replay actions, or change permissions.',
                 {'limit':{'type':'integer','minimum':1,'maximum':50}}),
            tool('rdc_preview_open','Show or reopen the live RDC preview inside a compatible AI app. '
                 'Pass the session_id for the browser or configured device this task is using. The view shows only that source; closing it leaves work running.',
                 {'session_id':PREVIEW_SESSION_ID}),
            tool('rdc_preview_activity','Read actual current and recent worker operations, visual focus and bounded job state. '
                 'An explicitly selected job_id includes at most 8 KiB of its real retained output. Never executes or repeats work.',
                 {'job_id':JOB_ID}),
            tool('rdc_preview_frame','Read one live frame for the embedded RDC view. '
                 'Does not create, close, pause, or mutate a browser or mobile session.',
                 {'session_id':PREVIEW_SESSION_ID},['session_id']),
            tool('rdc_preview_resize','Resize only the exact native window explicitly bound with resize_to_view enabled. Never changes focus or source. Recover pending operations instead of repeating uncertain mutations.',
                 {'session_id':PREVIEW_SESSION_ID,'width':{'type':'integer','minimum':240,'maximum':2560},
                  'height':{'type':'integer','minimum':180,'maximum':1600},
                  '_rdc_request_id':{'type':'string','minLength':1,'maxLength':200}},['session_id','width','height'],True),
            tool('rdc_file_list','List a directory within the granted roots.', {'path':STRING,'limit':{'type':'integer','minimum':1,'maximum':1000}}),
            tool('rdc_file_read','Read UTF-8 text with deterministic byte offsets and a SHA-256 version.',
                 {'file_path':STRING,'offset':{'type':'integer','minimum':0},'limit':LIMIT},['file_path']),
            tool('rdc_file_read_many','Read up to 20 independent files in one call. Per-file failures are retained.',
                 {'file_paths':{'type':'array','items':STRING,'minItems':1,'maxItems':20}},['file_paths']),
            tool('rdc_file_search','Bounded literal content search; reports skipped files and truncation.',
                 {'path':STRING,'query':{'type':'string','minLength':1,'maxLength':2000},
                  'limit':{'type':'integer','minimum':1,'maximum':1000},'max_files':{'type':'integer','minimum':1,'maximum':10000}},['path','query']),
            tool('rdc_file_write','Atomically create a UTF-8 file. To replace, supply its current expected_sha256.',
                 {'file_path':STRING,'content':content,'expected_sha256':SHA},['file_path','content'],True),
            tool('rdc_file_edit','Replace exact text after verifying SHA-256 and occurrence count. Uses file_path.',
                 {'file_path':STRING,'old_text':{**content,'minLength':1},'new_text':content,'expected_sha256':SHA,
                  'expected_count':{'type':'integer','minimum':1,'maximum':10000}},
                 ['file_path','old_text','new_text','expected_sha256'],True),
            tool('rdc_directory_create','Create one directory within granted roots. Its parent must exist.',
                 {'path':STRING},['path'],True),
            tool('rdc_job_start','Start an authorized command as a durable job. argv runs without shell expansion. '
                 'Supply a shell explicitly when needed. Command permissions are those of the worker account.',
                 {'argv':{'type':'array','minItems':1,'maxItems':256,'items':{'type':'string','maxLength':262144}},
                  'cwd':STRING,'timeout':{'type':'number','exclusiveMinimum':0,'maximum':604800},
                  'idempotency_key':{'type':'string','minLength':1,'maxLength':200}},['argv','cwd'],True,open_world=True),
            tool('rdc_job_run','Run a short authorized terminal command with a bounded inline wait. '
                 'Returns bounded output and exact exit status in this call if finished; '
                 'otherwise returns the original durable job ID for later status/output, '
                 'stdin, cancellation and recovery. Same approvals and permissions as job_start.',
                 {'argv':{'type':'array','minItems':1,'maxItems':256,'items':{'type':'string','maxLength':262144}},
                  'cwd':STRING,'timeout':{'type':'number','exclusiveMinimum':0,'maximum':604800},
                  'idempotency_key':{'type':'string','minLength':1,'maxLength':200},
                  'wait_ms':{'type':'integer','minimum':0,'maximum':3000},
                  'output_limit':LIMIT},['argv','cwd'],True,open_world=True),
            tool('rdc_job_status','Read persistent job state and exit status.', {'job_id':JOB_ID},['job_id']),
            tool('rdc_job_output','Read a retained stdout/stderr log. offset=0 always means the beginning; offsets are bytes.',
                 {'job_id':JOB_ID,'offset':{'type':'integer','minimum':0},'limit':LIMIT},['job_id']),
            tool('rdc_job_list','List recent jobs, including completed jobs.', {'limit':{'type':'integer','minimum':1,'maximum':500}}),
            tool('rdc_job_cancel','Request cancellation of an owned job and its process group.', {'job_id':JOB_ID},['job_id'],True),
            tool('rdc_job_input','Queue UTF-8 stdin for an interactive job. close=true closes its stdin after this input.',
                 {'job_id':JOB_ID,'text':content,'close':{'type':'boolean'}},['job_id'],True),
            tool('rdc_request_status','Read a persisted approval decision. Approval itself is owner-only.', {'request_id':JOB_ID},['request_id']),
            tool('rdc_credentials_list','List owner-configured opaque credential aliases and permitted website origins. Never returns passwords or provider locators.'),
            tool('rdc_credentials_request','Request a private saved-password fill into a freshly observed password input. '
                 'Owner Allow Once or a matching persistent grant is required even in trusted mode. Never submits the form.',
                 {'credential_id':JOB_ID,'session_id':JOB_ID,'observation_id':JOB_ID,
                  'password_handle':{'type':'string','minLength':1,'maxLength':64},
                  'idempotency_key':{'type':'string','minLength':1,'maxLength':200}},
                 ['credential_id','session_id','observation_id','password_handle','idempotency_key'],True,open_world=True),
            tool('rdc_credentials_status','Read a credential request state without disclosing a password. Owner decisions are outside the agent catalog.',
                 {'request_id':JOB_ID},['request_id']),
        ]
        if self.adapters:
            items.extend(self.adapters.catalog())
        from .preview import UI_URI
        for item in items:
            if item['name'] == 'rdc_preview_open':
                item['_meta'] = {'ui':{'resourceUri':UI_URI, 'visibility':['model','app']},
                                 'openai/outputTemplate':UI_URI,
                                 'openai/widgetAccessible':True,
                                 'openai/ui':{'entrypoints':[{'type':'thread'}]}}
            elif item['name'] in ('rdc_preview_frame','rdc_preview_activity','rdc_preview_resize'):
                # Visibility is only a routing hint. This operation remains
                # read-only even if called directly by a model or raw client.
                item['_meta'] = {'ui':{'visibility':['app']}, 'openai/widgetAccessible':True}
        return items

    def catalog(self):
        return list(self._tools.values())

    def _validate(self,name,arguments):
        if name not in self._tools:
            raise RDCError('unknown_tool', f'Unknown RDC tool: {name}')
        errors = sorted(self._validators[name].iter_errors(arguments),key=lambda e:str(e.path))
        if errors:
            raise RDCError('invalid_arguments',errors[0].message)
        if name in ('rdc_job_start', 'rdc_job_run'):
            if not self.settings.allow_exec:
                raise RDCError('capability_disabled','Command execution is disabled in the owner configuration.')
            if not arguments['argv'][0] or any('\0' in part for part in arguments['argv']):
                raise RDCError('invalid_arguments','Command and arguments cannot contain NUL, and command must be nonempty.')
            self.files.resolve(arguments['cwd'],directory=True)
        if name.startswith('rdc_file_') and 'file_path' in arguments:
            self.files.resolve(arguments['file_path'])
        if name in ('rdc_directory_create','rdc_file_list','rdc_file_search'):
            self.files.resolve(arguments.get('path','.'))

    def _execute(self,name,arguments,owner=False):
        self._validate(name,arguments)
        mutating = self._tools[name].get('x-rdc-mutating',False)
        stopping = name in ('rdc_job_cancel','rdc_browser_close','rdc_mobile_close')
        with self._input_lock:
            if not owner and mutating and not stopping:
                if self.store.get('paused') == 'true':
                    raise RDCError('paused','Agent actions are paused by the owner. Read-only observation remains available.')
                # PyAutoGUI uses this OS login's real cursor and keyboard. A
                # configuration label cannot verify isolation. Require an
                # owner decision for each native input, even in trusted mode.
                if name in ('rdc_desktop_pointer','rdc_desktop_keys','rdc_desktop_type') and self.settings.desktop_mode != 'disabled':
                    return self._queue(name,arguments)
                if self.settings.approval_mode == 'review' and name != 'rdc_credentials_request':
                    if name=='rdc_preview_resize' and self.adapters:
                        # window_open is itself owner-reviewed. Its explicit
                        # binding-scoped grant covers continuous pane resizing;
                        # request arguments cannot create or expand that grant.
                        self.adapters.windows.require_resize_authorization(arguments['session_id'])
                    else:
                        return self._queue(name,arguments)
        # The lock is an admission gate, not a global tool execution lock.
        # Slow reads and browser navigation must not block pause or job cancel.
        return {'ok':True,**self._invoke(name,arguments)}

    def _guarded(self,operation,tool_name=None):
        try:
            result = operation()
            if isinstance(result,dict) and result.get('ok') is False:
                safe_record(self.diagnostics,'worker','operation_failed',tool_name)
            return result
        except RDCError as exc:
            safe_record(self.diagnostics,'worker','operation_failed',tool_name)
            return exc.result()
        except FileNotFoundError:
            safe_record(self.diagnostics,'worker','operation_failed',tool_name)
            return RDCError('not_found','Requested file or program does not exist.').result()
        except PermissionError:
            safe_record(self.diagnostics,'worker','operation_failed',tool_name)
            return RDCError('permission_denied','The operating system denied access.').result()
        except (OSError,ValueError,sqlite3.Error) as exc:
            safe_record(self.diagnostics,'worker','operation_failed',tool_name)
            return RDCError('operation_failed',str(exc)).result()
        except Exception:
            safe_record(self.diagnostics,'worker','unexpected_error',tool_name)
            raise

    def call(self,name,arguments=None):
        return self._guarded(lambda:self._execute(name,arguments if arguments is not None else {}),name)

    def owner_call(self,name,arguments=None):
        return self._guarded(lambda:self._execute(name,arguments if arguments is not None else {},owner=True),name)

    def _invoke(self,name,args):
        # Only admitted invocations reach this point. Validation failures and
        # pending owner approval are never presented as work being executed.
        token = self.activity.begin(name,args)
        try:
            result = self._invoke_inner(name,args)
        except Exception:
            self.activity.finish(token,success=False)
            raise
        self.activity.finish(token,result,success=not isinstance(result,dict) or result.get('ok',True))
        return result

    def _preview_sessions(self):
        if self.adapters:
            snapshot = getattr(self.adapters,'activity_status',self.adapters.status)()
        else:
            snapshot = {}
        allowed = ('session_id','backend','browser','url','title','width','height','observation_id','cursor',
                   'profile','platform','automation','input_notice','privacy_sensitive','setup_status','resize_to_view','bundle_id')
        sessions = []
        for category in ('browser','mobile','window'):
            for session in snapshot.get(category,{}).get('sessions',[]):
                row = {key:session[key] for key in allowed if key in session}
                row.update(kind=category,viewport={'width':row.get('width'),'height':row.get('height')})
                sessions.append(row)
        # Listing configured native targets performs no capture or native I/O.
        # They are never selected automatically by the preview.
        if self.adapters and self.settings.desktop_mode != 'disabled':
            sessions.append({'session_id':'desktop','kind':'desktop','title':'Configured desktop',
                             'width':None,'height':None,'viewport':{'width':None,'height':None}})
        if self.adapters and self.settings.adb_serial:
            sessions.append({'session_id':'android-adb','kind':'adb','title':'Configured Android device',
                             'width':None,'height':None,'viewport':{'width':None,'height':None}})
        sources = [snapshot.get(category,{}) for category in ('browser','mobile')]
        timestamps = [source['updated_at'] for source in sources if isinstance(source.get('updated_at'),(int,float))]
        status = {'busy':any(source.get('busy',False) for source in sources),
                  'status_stale':any(source.get('status_stale',False) for source in sources),
                  'updated_at':min(timestamps) if timestamps else time.time()}
        return sessions,status

    def _preview_activity(self,job_id=None):
        sessions,status = self._preview_sessions()
        activity = self.activity.snapshot({row['session_id'] for row in sessions})
        if any(row['tool'].startswith(('rdc_desktop_','rdc_android_')) for row in activity['current_operations']):
            status.update(busy=True,status_stale=True)
        return {'device_id':self.store.device_id,'observed_at':time.time(),
                'paused':self.store.get('paused')=='true','sessions':sessions,'session_status':status,
                **activity,**self.jobs.preview(job_id),'pending_approvals':len(self.store.approvals())}

    def _invoke_inner(self,name,args):
        handlers = {'rdc_file_list':self.files.list,'rdc_file_read':self.files.read,'rdc_file_search':self.files.search,
                    'rdc_file_write':self.files.write,'rdc_file_edit':self.files.edit,'rdc_job_start':self.jobs.start,
                    'rdc_job_run':self.jobs.run,
                    'rdc_job_status':self.jobs.status,'rdc_job_output':self.jobs.output,'rdc_job_list':self.jobs.list,
                    'rdc_job_cancel':self.jobs.cancel,'rdc_job_input':self.jobs.input}
        if name in handlers:
            return handlers[name](**args)
        if name == 'rdc_system_status':
            return self.status(summary=True)
        if name == 'rdc_diagnostics_status':
            if self.diagnostics is not None:
                return self.diagnostics.snapshot(**args)
            report = Diagnostics.read_status(self.settings.state_dir,**args)
            report.update(available=False,incomplete=True,
                          capture_scope='retained_history_only_live_capture_unavailable')
            return report
        if name == 'rdc_credentials_list':
            return self.credentials.list()
        if name == 'rdc_credentials_request':
            return self.credentials.request(**args)
        if name == 'rdc_credentials_status':
            return self.credentials.status(**args)
        if name == 'rdc_preview_activity':
            return self._preview_activity(**args)
        if name == 'rdc_preview_open':
            selected = args.get('session_id')
            if selected == 'desktop':
                raise RDCError('window_required','This preview requires the exact task window. Use rdc_window_list and rdc_window_open; full-display previews are disabled.')
            sessions = []
            if selected:
                available, _ = self._preview_sessions()
                sessions = [row for row in available if row['session_id'] == selected]
                if not sessions:
                    raise RDCError('session_not_found','Requested session is no longer active in this worker.')
            return {'device_id':self.store.device_id,'session_id':selected,'sessions':sessions,
                    'paused':self.store.get('paused')=='true',
                    'viewer':{'bound_to_session':bool(selected),'close_keeps_working':True,'worker_required':True},
                    'message':'This preview shows only the requested session. Closing it leaves work running.'
                              if selected else 'Pass the session_id for the visual source this task is using.'}
        if name == 'rdc_preview_frame':
            if args['session_id']=='desktop':
                raise RDCError('window_required','Select the exact task window. Full-display previews are disabled.')
            if not self.adapters:
                raise RDCError('capability_disabled','Device adapters are unavailable.')
            shot = self.adapters.snapshot(args['session_id'])
            if args['session_id'] in ('desktop','android-adb'):
                shot = {key:value for key,value in shot.items() if key!='serial'}
            return {**shot,'device_id':self.store.device_id,'captured_at':time.time(),
                    'viewport':{'width':shot['width'],'height':shot['height']},
                    'paused':self.store.get('paused')=='true'}
        if name == 'rdc_preview_resize':
            if not self.adapters or not args['session_id'].startswith('window-'):
                raise RDCError('resize_not_enabled','Only explicitly resize-enabled native window bindings accept this request.')
            with self.adapters._native_lock:
                result=self.adapters.windows.resize(args['session_id'],args['width'],args['height'],request_id=args.get('_rdc_request_id'))
            return {**result,'device_id':self.store.device_id}
        if name == 'rdc_file_read_many':
            paths = args['file_paths']
            def read(path):
                return self._guarded(lambda:{'ok':True,**self.files.read(path,limit=max(1024,self.settings.max_read_bytes//len(paths)))})
            with ThreadPoolExecutor(max_workers=min(4,len(paths))) as pool:
                return {'results':list(pool.map(read,paths))}
        if name == 'rdc_directory_create':
            path = self.files.resolve(args['path'])
            path.mkdir(exist_ok=True,mode=0o700)
            return {'path':str(path)}
        if name == 'rdc_request_status':
            with self.store.connection() as db:
                row = db.execute('SELECT * FROM approvals WHERE id=?',(args['request_id'],)).fetchone()
            if not row:
                raise RDCError('request_not_found','Approval request not found.')
            return {'request':self.store.approval_data(row)}
        if self.adapters:
            return self.adapters.call(name,args)
        raise RDCError('capability_disabled','Device adapters are unavailable.')

    def _queue(self,name,args):
        encoded = json.dumps(args,sort_keys=True,separators=(',',':'))
        digest = hashlib.sha256((name+'\n'+encoded).encode()).hexdigest()
        key = f'{name}:{args["idempotency_key"]}' if args.get('idempotency_key') else None
        identifier = str(uuid.uuid4())
        now = time.time()
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if key:
                row = db.execute('SELECT * FROM approvals WHERE client_key=?',(key,)).fetchone()
                if row:
                    if row['digest'] != digest:
                        raise RDCError('idempotency_conflict','This retry key belongs to different approval arguments.')
                    if row['result']:
                        return json.loads(row['result'])
                    return {'ok':True,'status':row['status'],'request_id':row['id'],'expires_at':row['expires_at']}
            db.execute('INSERT INTO approvals(id,name,arguments,digest,status,created_at,expires_at,client_key) VALUES (?,?,?,?,?,?,?,?)',
                       (identifier,name,encoded,digest,'pending',now,now+900,key))
        return {'ok':True,'status':'pending_approval','request_id':identifier,'expires_at':now+900,
                'message':'Review this exact operation in local RDC owner administration. Native desktop input can take over your mouse or keyboard; the live preview is observation only.'}

    def decide(self,request_id,approve):
        return self._guarded(lambda:self._decide(request_id,approve))

    def _decide(self,request_id,approve):
        if type(approve) is not bool:
            raise RDCError('invalid_arguments','approve must be a boolean.')
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM approvals WHERE id=?',(request_id,)).fetchone()
            if not row:
                raise RDCError('request_not_found','Approval request not found.')
            if row['status'] != 'pending':
                raise RDCError('already_decided','This request has already been decided or is executing.')
            if row['expires_at'] < time.time():
                # Persist outside the raising transaction below.
                expired = True
                db.execute("UPDATE approvals SET status='expired' WHERE id=?",(request_id,))
            else:
                expired = False
                db.execute('UPDATE approvals SET status=? WHERE id=?',('executing' if approve else 'rejected',request_id))
        if expired:
            raise RDCError('expired','This review request has expired. Submit a fresh request.')
        if not approve:
            result = {'ok':True,'status':'rejected','request_id':request_id}
        else:
            arguments = json.loads(row['arguments'])
            expected = hashlib.sha256((row['name']+'\n'+row['arguments']).encode()).hexdigest()
            if expected != row['digest']:
                result = RDCError('integrity_error','Stored request integrity check failed.').result()
            else:
                result = self.owner_call(row['name'],arguments)
        with self.store.connection() as db:
            db.execute('UPDATE approvals SET status=?,result=? WHERE id=?',
                       ('completed' if approve and result['ok'] else 'failed' if approve else 'rejected',json.dumps(result),request_id))
        return result

    def pause(self,paused=True):
        if type(paused) is not bool:
            raise RDCError('invalid_arguments','paused must be a boolean.')
        with self._input_lock:
            self.store.set('paused','true' if paused else 'false')
        return {'ok':True,'paused':paused,'message':'Already-admitted actions may finish. Running jobs continue; cancel them individually when needed.'}

    def status(self,summary=False):
        jobs = self.jobs.list()['jobs']
        approvals = self.store.approvals()
        result = {'ok':True,'name':'RDC','version':__version__,'device_id':self.store.device_id,
                  'settings':self.settings.public(),'paused':self.store.get('paused')=='true',
                  'adapters':self.adapters.status() if self.adapters else {},
                  'jobs':jobs,'approvals':approvals}
        if summary:
            result.pop('jobs')
            result.pop('approvals')
            result['job_count'] = len(jobs)
            result['pending_approvals'] = len(approvals)
        else:
            result['credentials'] = self.credentials.owner_snapshot()
        return result

    def snapshot(self,session_id=None):
        if not self.adapters:
            raise RDCError('capability_disabled','Device adapters are unavailable.')
        return self.adapters.snapshot(session_id)

    def close(self):
        try:
            self.credentials.close()
            if self.adapters:
                self.adapters.close()
        finally:
            try:
                if self.diagnostics is not None:
                    self.diagnostics.close()
            except Exception:
                pass
