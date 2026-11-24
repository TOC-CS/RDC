"""Client-neutral, typed routing for the existing native mobile adapter.

The route is chosen before dispatch. No route changes or retries after an
operation fails. Terminal locations are explicit, not inferred from a command.
"""
import copy
import hashlib
import re
import unicodedata
from time import perf_counter
from jsonschema import Draft202012Validator
from .errors import RDCError

READ_ROUTES = {
    'list': ('list','device_api'),
    'discover': ('app_discover','device_api'),
    'app_state': ('app_state','device_api'),
    'ios_status': ('ios_status','device_api'),
    'android_status': ('android_usb_status','device_api'),
    'observe': ('observe','structured_ui'),
    'frame': ('screenshot','visual'),
    'direct_prepare': ('ios_app_prepare','device_api'),
}
WRITE_ROUTES = {
    'open_ready': ('start','device_api'),
    'switch_ready': ('app_open','device_api'),
    'terminate': ('app_terminate','device_api'),
    'tap': ('tap','structured_ui'),
    'fill': ('fill','structured_ui'),
    'swipe': ('swipe','structured_ui'),
    'gesture': ('gesture','structured_ui'),
    'visual_gesture': ('visual_gesture','visual'),
    'close': ('close','device_api'),
}
# Deliberately exclude direct_launch from the generic mutation wrapper.
# It has a mandatory owner-only approval path at Engine._execute.
TERMINAL_ROUTES = {
    'local_terminal': ('mobile_sandbox','rdc_mobile_command_execute',False),
    'worker_terminal': ('worker_host','rdc_job_run',False),
    'remote_ssh': ('remote_host',None,False),
    'direct_device': ('device_api','rdc_mobile_ios_app_launch',True),
}

def descriptors():
    def schema(operations):
        return {'type':'object','properties':{
            'operation':{'type':'string','enum':sorted(operations)},
            'arguments':{'type':'object','maxProperties':12}},
            'required':['operation','arguments'],'additionalProperties':False}
    return [
        {'name':'rdc_mobile_command_read',
         'description':'Client-neutral mobile command router. Discover apps, read native controls or a verified frame, inspect a terminal execution location, or prepare a direct device launch. No mutations.',
         'inputSchema':schema(set(READ_ROUTES)|{'terminal_route','capabilities'}),
         'x-rdc-mutating':False,'annotations':{'readOnlyHint':True,'destructiveHint':False,'idempotentHint':False,'openWorldHint':True}},
        {'name':'rdc_mobile_command_execute',
         'description':'Execute one typed authorized native mobile operation. Prefer device API for app lifecycle, structured UI for observed controls, visual input only with a current verified frame. Uses existing route validation. Never retry uncertain input.',
         'inputSchema':schema(set(WRITE_ROUTES)|{'local_command'}),
         'x-rdc-mutating':True,'annotations':{'readOnlyHint':False,'destructiveHint':True,'idempotentHint':False,'openWorldHint':True}},
    ]

COMPANION_BUNDLE = 'org.tocministries.rdc.mobile'
TERMINAL_MARKER = 'RDC device-local terminal'
RECEIPT = re.compile(
    r'^RDC terminal result \| device-local \| run=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}) \| command=([0-9a-f]{64}) \| exit=([01]) \| ([0-9]{1,12}\.[0-9]{2}) ms$',
    re.MULTILINE)
LOCAL_SCHEMA = {'type':'object','properties':{
    'session_id':{'type':'string','minLength':1,'maxLength':128},
    'observation_id':{'type':'string','minLength':1,'maxLength':128},
    'command':{'type':'string','minLength':1,'maxLength':4000}},
    'required':['session_id','observation_id','command'],'additionalProperties':False}
LOCAL_VALIDATOR = Draft202012Validator(LOCAL_SCHEMA)

def terminal_details(observation):
    text=observation.get('text','')
    if (not isinstance(text,str) or text.splitlines().count(TERMINAL_MARKER)!=1
            or any(observation.get(k,True) for k in ('text_truncated','controls_truncated','control_scan_truncated'))):
        return None
    controls=observation.get('controls',[])
    fields=[c for c in controls if c.get('editable') and c.get('can_fill') and not c.get('secure')]
    runs=[c for c in controls if c.get('name')=='Run local command' and not c.get('editable') and not c.get('secure')]
    if len(fields)!=1 or len(runs)!=1 or any(c.get('secure') for c in controls):
        return None
    matches=list(RECEIPT.finditer(text))
    return {'field':fields[0]['handle'],'run':runs[0]['handle'],
            'run_enabled':bool(runs[0].get('can_tap')),
            'prior_runs':{m.group(1) for m in matches},
            'observation_id':observation.get('observation_id')}

def record_terminal_observation(session,observation):
    session.pop('terminal_observation',None)
    metadata=terminal_details(observation)
    if metadata is not None:
        session['terminal_observation']=metadata

def _require_companion(mobile,session):
    # Bind to the owner-defined device and companion app, never an arbitrary
    # bundle provided by an AI client. The normal input path rechecks iOS.
    profile=mobile._profiles[session['profile']]
    if session['platform']=='iOS':
        actual=mobile._app_target(session,session.get('active_profile',session['profile']))
    elif session['platform']=='Android':
        actual=profile['capabilities'].get('appium:appPackage')
        if actual==COMPANION_BUNDLE:
            actual=mobile._wd(session,'GET','/appium/device/current_package')
    else:
        actual=None
    if actual!=COMPANION_BUNDLE:
        raise RDCError('mobile_app_scope_required','The RDC companion must be the verified active application.')

def _local_command(mobile,args):
    if next(LOCAL_VALIDATOR.iter_errors(args),None) is not None:
        raise RDCError('invalid_arguments','Invalid local command arguments.')
    command=args['command']
    if (not command.strip() or len(command.encode('utf-8'))>4000
            or any(unicodedata.category(ch)=='Cc' for ch in command)):
        raise RDCError('invalid_arguments','Use one bounded local command without control characters.')
    session=mobile._sessions.get(args['session_id'])
    if session is None: raise RDCError('session_not_found','Mobile session unavailable.')
    if session.get('setup_status'):
        raise RDCError('mobile_cleanup_required','Mobile session requires cleanup.')
    metadata=session.get('terminal_observation')
    if (not metadata or session.get('observation_id')!=args['observation_id']
            or metadata['observation_id']!=args['observation_id']):
        raise RDCError('stale_observation','Observe the local terminal before submitting a command.')
    _require_companion(mobile,session)
    prior=set(metadata['prior_runs'])
    digest=hashlib.sha256(command.encode('utf-8')).hexdigest()
    base={'session_id':session['session_id'],'command_route':'mobile_sandbox',
          'execution_location':'mobile_device','command_sha256':digest,
          'execution_verified':False,'executed':False,
          'submission_status':'not_submitted'}
    mobile._publish_status(busy=True)
    try:
        try:
            mobile._act(session,'fill',{'session_id':session['session_id'],
                'observation_id':args['observation_id'],'handle':metadata['field'],'text':command})
        except Exception:
            mobile._invalidate(session)
            return base | {'input_status':'unknown','next_step':'observe; do not automatically resubmit'}
        try:
            _require_companion(mobile,session)
            after=mobile._observe(session)
            ready=terminal_details(after)
            if not ready or not ready['run_enabled']:
                return base | {'input_status':'acknowledged','next_step':'inspect current terminal'}
            prior.update(ready['prior_runs'])
            _require_companion(mobile,session)
        except Exception:
            mobile._invalidate(session)
            return base | {'input_status':'acknowledged','next_step':'observe; do not automatically resubmit'}
        # Submit exactly once. A lost click response or missing receipt never
        # triggers another click. The on-device app owns execution and results.
        try:
            mobile._act(session,'tap',{'session_id':session['session_id'],
                'observation_id':after['observation_id'],'handle':ready['run']})
        except Exception:
            mobile._invalidate(session)
            return base | {'submission_status':'unknown','next_step':'inspect receipt; do not replay'}
        base.update(submission_status='acknowledged')
        try:
            _require_companion(mobile,session)
            observation=mobile._observe(session)
            if terminal_details(observation) is None:
                return base | {'next_step':'inspect receipt; do not replay'}
            matches=list(RECEIPT.finditer(observation['text']))
            if len(matches)!=1: return base | {'next_step':'observe receipt; do not replay'}
            receipt=matches[0]
            if receipt.group(1) in prior or receipt.group(2)!=digest:
                return base | {'next_step':'observe receipt; do not replay'}
            return base | {'execution_verified':True,'executed':True,
                           'run_id':receipt.group(1),'exit_code':int(receipt.group(3)),
                           'device_elapsed_ms':float(receipt.group(4)),
                           'observation':observation}
        except Exception:
            return base | {'next_step':'observe receipt; do not replay'}
    finally:
        mobile._publish_status()

def _capabilities(mobile):
    def describe(mapping):
        return {op:{'route':route,'tool':'rdc_mobile_'+action,
                    'input_schema':copy.deepcopy(mobile._catalog['rdc_mobile_'+action]['inputSchema'])}
                for op,(action,route) in mapping.items()}
    read=describe(READ_ROUTES)
    execute=describe(WRITE_ROUTES)
    execute['local_command']={'route':'mobile_sandbox','tool':'rdc_mobile_command_execute',
                              'input_schema':copy.deepcopy(LOCAL_SCHEMA)}
    return {'schema_version':1,'read':read,'execute':execute,
            'terminal_locations':list(TERMINAL_ROUTES),
            'direct_launch_requires_owner_review':True,'automatic_retry':False}

def dispatch(mobile, tool, request):
    started=perf_counter()
    op=request['operation']
    args=dict(request['arguments'])
    read=tool=='rdc_mobile_command_read'
    if read and op=='capabilities':
        if args: raise RDCError('invalid_arguments','Capabilities takes no arguments.')
        return _capabilities(mobile)
    if not read and op=='local_command':
        routing_ms=round((perf_counter()-started)*1000,3)
        result=_local_command(mobile,args)
        return result | {'routing_ms':routing_ms,'command_total_ms':round((perf_counter()-started)*1000,3)}
    if read and op=='terminal_route':
        if set(args)!={'mode'} or not isinstance(args['mode'],str) or args['mode'] not in TERMINAL_ROUTES:
            raise RDCError('invalid_arguments','Choose an explicit terminal execution location.')
        route,next_tool,review=TERMINAL_ROUTES[args['mode']]
        return {'command_route':route,'executed':False,'next_tool':next_tool,
                'owner_review_required':review,'route_status':'companion_ui' if route=='mobile_sandbox' else ('existing_tool' if next_tool else 'integration_pending'),
                **({'next_operation':'local_command'} if route=='mobile_sandbox' else {}),
                'routing_ms':round((perf_counter()-started)*1000,3)}
    mapping=READ_ROUTES if read else WRITE_ROUTES
    if op not in mapping:
        raise RDCError('invalid_arguments','Unsupported command operation.')
    action,route=mapping[op]
    name='rdc_mobile_'+action
    if op in ('open_ready','switch_ready'):
        args['include_observation']=True
    # The existing downstream call validates its full schema before dispatch.
    routing_ms=round((perf_counter()-started)*1000,3)
    result=mobile._call(name,args)
    return result | {'command_route':route,'selected_tool':name,
                     'routing_ms':routing_ms,
                     'command_total_ms':round((perf_counter()-started)*1000,3)}
