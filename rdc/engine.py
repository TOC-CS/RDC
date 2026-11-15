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
PREVIEW_SESSION_ID = {'type':'string','pattern':r'^(?:mobile-)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'}
SHA = {'type':'string','pattern':r'^[0-9a-f]{64}$'}
LIMIT = {'type':'integer','minimum':1,'maximum':262144}


class Engine:
    def __init__(self, settings):
        self.settings = settings
        self.store = Store(settings.state_dir)
        self.files = Files(settings)
        self.jobs = Jobs(settings,self.store,self.files)
        self._input_lock = threading.RLock()
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

    def _catalog(self):
        content = {'type':'string','maxLength':self.settings.max_read_bytes}
        items = [
            tool('rdc_system_status','Get worker identity, permissions, capability status and counts.'),
            tool('rdc_preview_open','Show or reopen the live RDC preview inside a compatible AI app. '
                 'Attaches to an existing browser or configured mobile session; closing the view leaves work running.',
                 {'session_id':PREVIEW_SESSION_ID}),
            tool('rdc_preview_frame','Read one live frame for the embedded RDC view. '
                 'Does not create, close, pause, or mutate a browser or mobile session.',
                 {'session_id':PREVIEW_SESSION_ID},['session_id']),
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
                                 'openai/ui':{'entrypoints':[{'type':'thread'},{'type':'global'}]}}
            elif item['name'] == 'rdc_preview_frame':
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
        if name == 'rdc_job_start':
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
                if self.settings.approval_mode == 'review' and name != 'rdc_credentials_request':
                    return self._queue(name,arguments)
        # The lock is an admission gate, not a global tool execution lock.
        # Slow reads and browser navigation must not block pause or job cancel.
        return {'ok':True,**self._invoke(name,arguments)}

    def _guarded(self,operation):
        try:
            return operation()
        except RDCError as exc:
            return exc.result()
        except FileNotFoundError:
            return RDCError('not_found','Requested file or program does not exist.').result()
        except PermissionError:
            return RDCError('permission_denied','The operating system denied access.').result()
        except (OSError,ValueError,sqlite3.Error) as exc:
            return RDCError('operation_failed',str(exc)).result()

    def call(self,name,arguments=None):
        return self._guarded(lambda:self._execute(name,arguments if arguments is not None else {}))

    def owner_call(self,name,arguments=None):
        return self._guarded(lambda:self._execute(name,arguments if arguments is not None else {},owner=True))

    def _invoke(self,name,args):
        handlers = {'rdc_file_list':self.files.list,'rdc_file_read':self.files.read,'rdc_file_search':self.files.search,
                    'rdc_file_write':self.files.write,'rdc_file_edit':self.files.edit,'rdc_job_start':self.jobs.start,
                    'rdc_job_status':self.jobs.status,'rdc_job_output':self.jobs.output,'rdc_job_list':self.jobs.list,
                    'rdc_job_cancel':self.jobs.cancel,'rdc_job_input':self.jobs.input}
        if name in handlers:
            return handlers[name](**args)
        if name == 'rdc_system_status':
            return self.status(summary=True)
        if name == 'rdc_credentials_list':
            return self.credentials.list()
        if name == 'rdc_credentials_request':
            return self.credentials.request(**args)
        if name == 'rdc_credentials_status':
            return self.credentials.status(**args)
        if name == 'rdc_preview_open':
            adapters = self.adapters.status() if self.adapters else {}
            sessions = ([dict(s,kind='browser') for s in adapters.get('browser',{}).get('sessions',[])] +
                        [dict(s,kind='mobile') for s in adapters.get('mobile',{}).get('sessions',[])])
            selected = args.get('session_id')
            if selected and selected not in {s['session_id'] for s in sessions}:
                raise RDCError('session_not_found','Requested session is no longer active in this worker.')
            if not selected and sessions:
                selected = sessions[0]['session_id']
            sessions = [{**s,'viewport':{'width':s['width'],'height':s['height']}} for s in sessions]
            return {'device_id':self.store.device_id,'session_id':selected,'sessions':sessions,
                    'paused':self.store.get('paused')=='true',
                    'active_jobs':sum(j['status'] in ('queued','running','cancelling') for j in self.jobs.list()['jobs']),
                    'pending_approvals':len(self.store.approvals()),
                    'viewer':{'close_keeps_working':True,'worker_required':True},
                    'message':'Hide or close this preview without stopping the worker. Reopen with the same session ID.'
                              if selected else 'No session is active. Start an authorized browser or configured mobile workflow, then reopen the preview.'}
        if name == 'rdc_preview_frame':
            if not self.adapters:
                raise RDCError('capability_disabled','Device adapters are unavailable.')
            shot = self.adapters.snapshot(args['session_id'])
            return {**shot,'device_id':self.store.device_id,'captured_at':time.time(),
                    'viewport':{'width':shot['width'],'height':shot['height']},
                    'paused':self.store.get('paused')=='true'}
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
                'message':'Review this exact operation in the RDC owner preview.'}

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
        self.credentials.close()
        if self.adapters:
            self.adapters.close()
