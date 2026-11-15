"""Owner-configured native Appium sessions, separate from browser automation.

Only fixed protocol operations cross the driver boundary. Driver URLs,
capabilities, native XML, element IDs, and exception payloads stay private.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import ipaddress
import json
import math
import re
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

from jsonschema import Draft202012Validator

from .errors import RDCError


MAX_SESSIONS = 8
MAX_RESPONSE_BYTES = 12 * 1024 * 1024
MAX_XML_BYTES = 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ELEMENT_KEY = 'element-6066-11e4-a52e-4f735466cecf'
INPUT_NOTICE = ('Native actions use the selected device screen and may interrupt its user. '
                'Use a separate simulator, emulator, or dedicated device for independent work.')
MESSAGES = {
    'invalid_config': 'Invalid mobile profile. Use an owner-defined native Android/UiAutomator2 or iOS/XCUITest profile with a safe endpoint and flat capabilities.',
    'invalid_arguments': 'Invalid mobile arguments. Use the advertised tool schema and current observation.',
    'unknown_tool': 'Unknown mobile tool.',
    'closed': 'Mobile adapters are closed.',
    'profile_not_found': 'The owner has not configured that mobile profile.',
    'session_limit': 'At most eight mobile sessions may run. Close an existing session first.',
    'profile_in_use': 'This profile or its configured native device already has a session. Inspect or close that session before starting another.',
    'session_not_found': 'The mobile session does not exist in this worker.',
    'mobile_driver_error': 'The native driver rejected the request. No driver payload was returned. Inspect the device before repeating an input.',
    'mobile_unavailable': 'The native driver is unavailable or timed out. The action may have occurred; inspect the device before repeating it.',
    'mobile_protocol_error': 'The native driver returned an unsupported or malformed response.',
    'mobile_session_gone': 'The native driver reports that this session no longer exists. Close its RDC session record before starting the profile again.',
    'mobile_cleanup_required': 'Mobile setup or cleanup could not be confirmed. List mobile sessions and close the retained session before using that profile again.',
    'mobile_creation_unknown': 'Session creation could not be confirmed and no driver ID was received. The owner must inspect the configured Appium server and resolve any session before restarting RDC. This profile will not be started again automatically.',
    'mobile_native_required': 'This profile must remain in the native NATIVE_APP context. Webviews belong in a separately configured browser workflow.',
    'output_limit': 'The native driver response exceeds the permitted output size.',
    'observation_failed': 'Native observation failed. No hierarchy or control content was returned.',
    'stale_observation': 'The native observation is stale. Observe the current screen before acting.',
    'secure_input_required': 'This is a native secure field. The owner must enter the value on the device; native credential-provider filling is not available.',
    'screenshot_redaction_required': 'This native session contains or previously exposed a secure field. Safe image masking is unavailable, so no screenshot was returned. Do not bypass this refusal with another capture route.',
    'screenshot_failed': 'Native screenshot privacy or capture could not be verified. No image was returned.',
}


def fail(code):
    raise RDCError(code, MESSAGES[code]) from None


def validate_mobile_profiles(profiles):
    """Validate owner configuration without returning private field values."""
    try:
        if not isinstance(profiles, dict) or len(profiles) > 32:
            fail('invalid_config')
        for alias, profile in profiles.items():
            if (not isinstance(alias, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', alias)
                    or not isinstance(profile, dict)
                    or set(profile) != {'platformName', 'automationName', 'endpoint', 'capabilities'}):
                fail('invalid_config')
            if (profile['platformName'], profile['automationName']) not in (
                    ('Android', 'UiAutomator2'), ('iOS', 'XCUITest')):
                fail('invalid_config')
            endpoint = profile['endpoint']
            if not isinstance(endpoint, str) or not 1 <= len(endpoint) <= 4096 or any(c.isspace() or ord(c) < 32 for c in endpoint):
                fail('invalid_config')
            parsed = urllib.parse.urlsplit(endpoint)
            hostname = parsed.hostname
            if (not hostname or parsed.username is not None or parsed.password is not None
                    or parsed.query or parsed.fragment or parsed.port == 0):
                fail('invalid_config')
            try:
                loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                loopback = hostname.lower() == 'localhost'
            if parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback):
                fail('invalid_config')
            caps = profile['capabilities']
            if (not isinstance(caps, dict) or len(caps) > 64
                    or any(not isinstance(k, str) or not 1 <= len(k) <= 128 for k in caps)
                    or len(json.dumps(caps, allow_nan=False).encode()) > 32768):
                fail('invalid_config')
            if set(caps) & {'platformName', 'appium:platformName', 'automationName', 'appium:automationName', 'appium:options', 'browserName'}:
                fail('invalid_config')
            if any(':' not in key and key not in ('acceptInsecureCerts','timeouts','unhandledPromptBehavior','strictFileInteractability','proxy','pageLoadStrategy','setWindowRect') for key in caps):
                fail('invalid_config')
            for key in ('autoAcceptAlerts', 'autoDismissAlerts', 'autoGrantPermissions', 'autoWebview', 'fullReset'):
                if caps.get('appium:' + key, False) is not False:
                    fail('invalid_config')
            if caps.get('appium:noReset', True) is not True:
                fail('invalid_config')
            udid = caps.get('appium:udid')
            if not isinstance(udid, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}', udid):
                fail('invalid_config')
            if caps.get('unhandledPromptBehavior', 'ignore') != 'ignore':
                fail('invalid_config')
            timeout = caps.get('appium:newCommandTimeout', 120)
            if type(timeout) is not int or not 30 <= timeout <= 600:
                fail('invalid_config')
    except RDCError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError):
        fail('invalid_config')


def _catalog():
    string = {'type': 'string', 'minLength': 1, 'maxLength': 128}
    session = {'session_id': string}
    observed = session | {'observation_id': string}
    control = observed | {'handle': {'type':'string', 'pattern':r'^c[0-9]{1,3}$'}}
    coordinates = {key:{'type':'integer', 'minimum':0, 'maximum':16384}
                   for key in ('start_x','start_y','end_x','end_y')}
    rows = [
        ('list', 'List owner-configured native mobile profiles and active sessions. Private connection details are omitted.', False, {}, ()),
        ('start', 'Start one native Appium session using an owner-configured profile. This may launch the configured app and use the selected device screen.', True,
         {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'}}, ('profile',)),
        ('observe', 'Read bounded native labels and fresh control handles. Editable values and secure field labels are redacted.', False, session, ('session_id',)),
        ('tap', 'Tap a current observed native control once. No automatic retry follows an uncertain outcome.', True, control, ('session_id','observation_id','handle')),
        ('fill', 'Replace text in a current nonsecure editable native control. Secure fields require owner input on the device.', True,
         control | {'text':{'type':'string','maxLength':4000}}, ('session_id','observation_id','handle','text')),
        ('swipe', 'Swipe in native logical coordinates from a current observation. Refresh the observation after any input.', True,
         observed | coordinates | {'duration_ms':{'type':'integer','minimum':50,'maximum':10000}},
         ('session_id','observation_id','start_x','start_y','end_x','end_y')),
        ('screenshot', 'Capture the native screen only after privacy checks. Secure or unverifiable screens fail closed.', False, session, ('session_id',)),
        ('close', 'Close the exact native driver session. A failed cleanup remains listed for explicit recovery.', True, session, ('session_id',)),
    ]
    return [{'name':'rdc_mobile_' + name, 'description':description,
        'inputSchema':{'type':'object','properties':properties,'required':list(required),'additionalProperties':False},
        'x-rdc-mutating':mutating,
        'annotations':{'readOnlyHint':not mutating,'destructiveHint':mutating,'idempotentHint':not mutating,'openWorldHint':True}}
        for name,description,mutating,properties,required in rows]


def _flag(attributes, key, default=False):
    raw = attributes.get(key)
    if raw is None: return default
    if raw not in ('true','false','1','0'): raise ValueError('Invalid native boolean')
    return raw in ('true','1')


def _bounds(attributes, platform):
    if platform == 'Android':
        match = re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', attributes.get('bounds',''))
        if not match: return None
        x,y,right,bottom = map(int, match.groups())
        values = (x,y,right-x,bottom-y)
    else:
        if any(k not in attributes for k in ('x','y','width','height')): return None
        values = tuple(float(attributes[k]) for k in ('x','y','width','height'))
    if any(not math.isfinite(v) or abs(v)>32768 for v in values) or values[2]<=0 or values[3]<=0:
        return None
    return dict(zip(('x','y','width','height'), values))


def _native_tree(source, platform):
    """Parse a complete bounded native hierarchy. Never export XML or values."""
    if not isinstance(source, str) or not source or len(source)>MAX_XML_BYTES:
        raise ValueError('Invalid native source')
    encoded = source.encode('utf-8')
    if len(encoded)>MAX_XML_BYTES or '<!' in source:
        raise ValueError('Unsafe or oversized native source')
    rows = []
    stack = []
    for event, element in ET.iterparse(io.BytesIO(encoded), events=('start','end')):
        if event == 'end':
            stack.pop()
            continue
        if len(rows)>=5000 or len(stack)>=64: raise ValueError('Native source bound exceeded')
        parent = stack[-1] if stack else None
        if parent is None:
            path = '/*[1]'
        else:
            parent['children'] += 1
            path = parent['path'] + '/*[' + str(parent['children']) + ']'
        a = element.attrib
        wrapper = element.tag in ('hierarchy','AppiumAUT')
        kind = a.get('class', element.tag) if platform == 'Android' else a.get('type', element.tag)
        if not isinstance(kind, str) or len(kind)>160: raise ValueError('Invalid native type')
        if platform == 'Android':
            if not wrapper and not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_.$]+', kind):
                raise ValueError('Unknown Android node')
            editable = kind.endswith(('EditText','AutoCompleteTextView')) or _flag(a, 'editable')
            secure = _flag(a, 'password', default=editable)
            interactive = editable or secure or _flag(a,'clickable') or _flag(a,'long-clickable') or kind.endswith(
                ('Button','Switch','CheckBox','RadioButton','SeekBar','Spinner'))
            visible = _flag(a, 'displayed', _flag(a,'visible-to-user', True))
            label = a.get('text') or a.get('content-desc') or ''
        elif platform == 'iOS':
            if not wrapper and not re.fullmatch(r'XCUIElementType[A-Za-z]+', kind):
                raise ValueError('Unknown iOS node')
            editable = kind.endswith(('TextField','TextView'))
            secure = kind == 'XCUIElementTypeSecureTextField' or _flag(a, 'secure')
            interactive = editable or secure or kind.endswith(('Button','Switch','Cell','Link','Slider','Key','PickerWheel','SegmentedControl')) or _flag(a,'accessible')
            visible = _flag(a, 'visible', True)
            label = a.get('label') or a.get('name') or ''
        else:
            raise ValueError('Unsupported native platform')
        row = {'element':element,'path':path,'parent':parent,'children':0,'wrapper':wrapper,'kind':kind,
            'editable':editable or secure,'secure':secure,'interactive':interactive,
            'visible':visible and (parent is None or parent['visible']), 'enabled':_flag(a,'enabled', True),
            'bounds':_bounds(a,platform), 'label':label, 'private_branch':editable or secure,
            'private_ancestor':parent is not None and (parent['editable'] or parent['private_ancestor'])}
        rows.append(row)
        stack.append(row)
    if (not rows or not any(not r['wrapper'] for r in rows)
            or (platform=='Android' and rows[0]['element'].tag != 'hierarchy')
            or (platform=='iOS' and rows[0]['element'].tag not in ('AppiumAUT','XCUIElementTypeApplication'))):
        raise ValueError('Unknown native hierarchy')
    # A container's accessible label can concatenate the values of its children.
    for row in reversed(rows):
        if row['parent'] is not None and row['private_branch']:
            row['parent']['private_branch'] = True
    controls, handles, text = [], {}, []
    text_length, controls_truncated, text_truncated = 0, False, False
    for row in rows:
        # Child accessibility nodes can expose a field's value in labels or
        # provide another editable handle inside a secure field. Only the
        # containing field is exported; all descendants are still scanned.
        if row['wrapper'] or not row['visible'] or row['private_ancestor']: continue
        label = '' if row['private_branch'] else row['label']
        if label and row['children'] == 0:
            available = max(0, 24000-text_length-(1 if text else 0))
            if len(label)>available: text_truncated = True
            if available:
                text.append(label[:available])
                text_length += min(len(label),available) + (1 if len(text)>1 else 0)
        if not row['interactive'] or row['bounds'] is None: continue
        if len(controls)>=150:
            controls_truncated = True
            continue
        handle = 'c' + str(len(controls)+1)
        role = 'textbox' if row['editable'] else 'button' if row['kind'].endswith('Button') else 'control'
        name = 'Secure field' if row['secure'] else 'Text field' if row['editable'] else label or 'Control'
        control = {'handle':handle,'name':name[:240],'name_truncated':len(name)>240,'tag':row['kind'],
            'type':'password' if row['secure'] else 'text' if row['editable'] else 'button' if role=='button' else 'control',
            'role':role, 'secure':row['secure'],'sensitive':row['secure'], 'editable':row['editable'],
            'can_fill':row['editable'] and not row['secure'] and row['enabled'],
            'can_tap':row['enabled'], 'disabled':not row['enabled'], 'bounds':row['bounds'],
            'value':'[redacted]' if row['editable'] else '', 'value_truncated':False}
        controls.append(control)
        handles[handle] = {'path':row['path'], 'control':control}
    return {'controls':controls,'handles':handles,'text':'\n'.join(text),'text_truncated':text_truncated,
        'controls_truncated':controls_truncated,'control_scan_truncated':False,
        'sensitive':any(r['secure'] for r in rows), 'digest':hashlib.sha256(encoded).digest()}


def _png_dimensions(raw):
    if (not isinstance(raw, bytes) or len(raw)<33 or len(raw)>MAX_IMAGE_BYTES
            or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[8:16] != b'\0\0\0\rIHDR'):
        raise ValueError('Invalid native image')
    width,height = struct.unpack('>II', raw[16:24])
    if not (1<=width<=16384 and 1<=height<=16384) or width*height>48_000_000:
        raise ValueError('Invalid native image size')
    return width,height


class Mobile:
    def __init__(self, settings):
        profiles = getattr(settings, 'mobile_profiles', {})
        validate_mobile_profiles(profiles)
        self._profiles = copy.deepcopy(profiles)
        self._sessions = {}
        self._lock = threading.RLock()
        self._status_lock = threading.Lock()
        self._closed = False
        self._catalog = {row['name']:row for row in _catalog()}
        self._validators = {name:Draft202012Validator(row['inputSchema']) for name,row in self._catalog.items()}
        self._publish_status()

    def catalog(self):
        return copy.deepcopy(list(self._catalog.values()))

    def status(self):
        # Reads never acquire the execution lock or wait for native driver I/O.
        with self._status_lock:
            return copy.deepcopy(self._status_snapshot)

    def _publish_status(self, busy=False):
        # Called at initialization or while the execution lock is held. Never
        # retain private driver IDs, endpoints, capabilities, or native handles.
        snapshot = {'available':bool(self._profiles),
            'profiles':[{'profile':name,'platform':p['platformName'],'automation':p['automationName']}
                        for name,p in self._profiles.items()],
            'sessions':[self._info(s) for s in self._sessions.values()],
            'independent_input':False, 'isolation_notice':INPUT_NOTICE,
            'busy':busy, 'status_stale':busy, 'updated_at':time.time(), 'closed':self._closed}
        with self._status_lock:
            self._status_snapshot = snapshot

    @staticmethod
    def _info(session):
        keys = ('session_id','backend','kind','profile','platform','automation','title','width','height','observation_id','cursor')
        info = {key:copy.deepcopy(session[key]) for key in keys}
        info['input_notice'] = INPUT_NOTICE
        info['privacy_sensitive'] = session['sensitive']
        if session.get('setup_status'):
            info['setup_status'] = session['setup_status']
        return info

    def call(self, name, args):
        try:
            return self._call(name, args)
        except RDCError as exc:
            fail(exc.code if exc.code in MESSAGES else 'mobile_driver_error')
        except Exception:
            fail('mobile_driver_error')

    def _call(self, name, args):
        if name == 'rdc_mobile_list':
            status = self.status()
            if status['closed']: fail('closed')
            if next(self._validators[name].iter_errors(args), None) is not None: fail('invalid_arguments')
            return status
        with self._lock:
            if self._closed: fail('closed')
            if name not in self._catalog: fail('unknown_tool')
            if next(self._validators[name].iter_errors(args), None) is not None: fail('invalid_arguments')
            action = name.removeprefix('rdc_mobile_')
            if action == 'screenshot': return self.snapshot(args['session_id'])
            self._publish_status(busy=True)
            try:
                if action == 'start': return self._start(args['profile'])
                session = self._sessions.get(args['session_id'])
                if session is None: fail('session_not_found')
                if action == 'close':
                    self._destroy(session)
                    del self._sessions[session['session_id']]
                    return {'session_id':session['session_id'],'closed':True}
                if session.get('setup_status'): fail('mobile_cleanup_required')
                if action == 'observe': return self._observe(session)
                return self._act(session, action, args)
            finally:
                self._publish_status()

    def _start(self, profile_name):
        profile = self._profiles.get(profile_name)
        if profile is None: fail('profile_not_found')
        if any(s['profile'] == profile_name or self._device_key(self._profiles[s['profile']]) == self._device_key(profile)
               for s in self._sessions.values()): fail('profile_in_use')
        if len(self._sessions) >= MAX_SESSIONS: fail('session_limit')
        session = {'session_id':'mobile-' + str(uuid.uuid4()), 'backend':'appium', 'kind':'mobile',
            'profile':profile_name, 'platform':profile['platformName'], 'automation':profile['automationName'],
            'title':profile_name, 'width':0, 'height':0, 'observation_id':None, 'cursor':{'x':0,'y':0},
            'handles':{}, 'sensitive':False}
        caps = copy.deepcopy(profile['capabilities'])
        caps.update(platformName=profile['platformName'])
        caps['appium:automationName'] = profile['automationName']
        caps.setdefault('appium:newCommandTimeout', 120)
        caps.setdefault('appium:noReset', True)
        try:
            created = self._http(profile, 'POST', '/session', {'capabilities':{'alwaysMatch':caps}}, timeout=90)
            if (not isinstance(created, dict) or not isinstance(created.get('sessionId'), str)
                    or not 1 <= len(created['sessionId']) <= 256):
                fail('mobile_protocol_error')
            session['driver_id'] = created['sessionId']
        except RDCError:
            session['setup_status'] = 'creation_unknown'
            self._sessions[session['session_id']] = session
            fail('mobile_creation_unknown')
        try:
            if not isinstance(created.get('capabilities'), dict): fail('mobile_protocol_error')
            returned_platform = created['capabilities'].get('platformName', profile['platformName'])
            if not isinstance(returned_platform, str) or returned_platform.casefold() != profile['platformName'].casefold():
                fail('mobile_protocol_error')
            self._wd(session, 'POST', '/timeouts', {'implicit':0})
            self._native(session)
            self._dimensions(session)
        except Exception:
            try: self._destroy(session)
            except RDCError:
                session['setup_status'] = 'cleanup_required'
                self._sessions[session['session_id']] = session
                fail('mobile_cleanup_required')
            raise
        self._sessions[session['session_id']] = session
        return self._info(session)

    @staticmethod
    def _device_key(profile):
        endpoint = urllib.parse.urlsplit(profile['endpoint'])
        return (endpoint.scheme, endpoint.hostname.lower(), endpoint.port or (443 if endpoint.scheme=='https' else 80),
                endpoint.path.rstrip('/'), profile['platformName'], profile['capabilities']['appium:udid'].casefold())

    def _native(self, session):
        if self._wd(session, 'GET', '/context') != 'NATIVE_APP':
            self._invalidate(session)
            fail('mobile_native_required')

    def _dimensions(self, session):
        rect = self._wd(session, 'GET', '/window/rect')
        if not isinstance(rect, dict): fail('mobile_protocol_error')
        for key in ('width','height'):
            value = rect.get(key)
            if type(value) not in (float,int) or not math.isfinite(value) or not 1 <= value <= 16384:
                fail('mobile_protocol_error')
        session.update(width=rect['width'], height=rect['height'])

    def _source(self, session):
        try:
            tree = _native_tree(self._wd(session, 'GET', '/source'), session['platform'])
        except RDCError:
            raise
        except Exception:
            fail('observation_failed')
        if tree['sensitive']: session['sensitive'] = True
        return tree

    def _observe(self, session):
        self._invalidate(session)
        try:
            self._native(session)
            self._dimensions(session)
            tree = self._source(session)
            session.update(observation_id=str(uuid.uuid4()), handles=tree['handles'],
                source_digest=tree['digest'], observation_size=(session['width'],session['height']))
            return self._info(session) | {key:tree[key] for key in (
                'controls','text','text_truncated','controls_truncated','control_scan_truncated')}
        except RDCError as exc:
            self._invalidate(session)
            fail('mobile_session_gone' if exc.code=='mobile_session_gone' else 'observation_failed')
        except Exception:
            self._invalidate(session)
            fail('observation_failed')

    def _current(self, session, observation_id):
        if not observation_id or session['observation_id'] != observation_id: fail('stale_observation')
        self._native(session)
        self._dimensions(session)
        tree = self._source(session)
        if (tree['digest'] != session.get('source_digest')
                or (session['width'],session['height']) != session.get('observation_size')):
            self._invalidate(session)
            fail('stale_observation')

    def _act(self, session, action, args):
        self._current(session, args['observation_id'])
        handle = None
        if action in ('tap','fill'):
            handle = session['handles'].get(args['handle'])
            if handle is None: fail('stale_observation')
            control = handle['control']
            if action=='fill' and control['secure']: fail('secure_input_required')
            if not control['can_tap'] or (action=='fill' and (not control['can_fill'] or '\0' in args['text'])):
                fail('invalid_arguments')
        elif action == 'swipe':
            if any(args[key]>=session['width' if key.endswith('_x') else 'height']
                   for key in ('start_x','start_y','end_x','end_y')):
                fail('invalid_arguments')
        else:
            fail('unknown_tool')
        # The driver can complete an input even when its response is lost.
        self._invalidate(session)
        if action == 'swipe':
            actions = [{'type':'pointer','id':'rdc-touch','parameters':{'pointerType':'touch'},'actions':[
                {'type':'pointerMove','duration':0,'origin':'viewport','x':args['start_x'],'y':args['start_y']},
                {'type':'pointerDown','button':0},{'type':'pause','duration':50},
                {'type':'pointerMove','duration':args.get('duration_ms',400),'origin':'viewport','x':args['end_x'],'y':args['end_y']},
                {'type':'pointerUp','button':0}]}]
            try:
                self._wd(session, 'POST', '/actions', {'actions':actions})
            except RDCError:
                try: self._wd(session, 'DELETE', '/actions')
                except RDCError:
                    session['setup_status'] = 'cleanup_required'
                    fail('mobile_cleanup_required')
                raise
            session['cursor'] = {'x':args['end_x'],'y':args['end_y']}
        else:
            found = self._wd(session, 'POST', '/element', {'using':'xpath','value':handle['path']})
            if not isinstance(found, dict) or not isinstance(found.get(ELEMENT_KEY), str) or not 1<=len(found[ELEMENT_KEY])<=256:
                fail('mobile_protocol_error')
            path = '/element/' + urllib.parse.quote(found[ELEMENT_KEY], safe='')
            if action == 'tap':
                self._wd(session, 'POST', path + '/click', {})
            else:
                self._wd(session, 'POST', path + '/clear', {})
                self._wd(session, 'POST', path + '/value', {'text':args['text']})
            bounds = handle['control']['bounds']
            session['cursor'] = {'x':max(0,min(session['width']-1,bounds['x']+bounds['width']/2)),
                                 'y':max(0,min(session['height']-1,bounds['y']+bounds['height']/2))}
        return self._info(session) | {'performed':action}

    def snapshot(self, session_id):
        with self._lock:
            if self._closed: fail('closed')
            self._publish_status(busy=True)
            try:
                return self._snapshot(session_id)
            finally:
                self._publish_status()

    def _snapshot(self, session_id):
        session = self._sessions.get(session_id)
        if session is None: fail('session_not_found')
        if session.get('setup_status'): fail('mobile_cleanup_required')
        if session['sensitive']: fail('screenshot_redaction_required')
        try:
            self._native(session)
            self._dimensions(session)
            before = self._source(session)
            if session['sensitive']: fail('screenshot_redaction_required')
            encoded = self._wd(session, 'GET', '/screenshot')
            if not isinstance(encoded, str) or len(encoded)>4*((MAX_IMAGE_BYTES+2)//3):
                fail('output_limit')
            raw = base64.b64decode(encoded, validate=True)
            pixel_width,pixel_height = _png_dimensions(raw)
            self._native(session)
            after = self._source(session)
            if session['sensitive']: fail('screenshot_redaction_required')
            if before['digest'] != after['digest']: fail('screenshot_failed')
        except RDCError as exc:
            if exc.code in ('screenshot_redaction_required','output_limit','mobile_session_gone'): raise
            fail('screenshot_failed')
        except Exception:
            fail('screenshot_failed')
        return self._info(session) | {'mime_type':'image/png','data':base64.b64encode(raw).decode('ascii'),
            'source_width':pixel_width,'source_height':pixel_height,
            'input_width':session['width'],'input_height':session['height'],
            'input_scale_x':session['width']/pixel_width,'input_scale_y':session['height']/pixel_height,
            'coordinate_system':'native logical pixels'}

    @staticmethod
    def _invalidate(session):
        session['observation_id'] = None
        session['handles'] = {}

    def _http(self, profile, method, path, body=None, timeout=35):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        try:
            request = urllib.request.Request(profile['endpoint'].rstrip('/') + path,
                data=json.dumps(body, allow_nan=False).encode() if body is not None else None,
                method=method, headers={'Content-Type':'application/json'})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES: fail('output_limit')
        except urllib.error.HTTPError as exc:
            try:
                with exc: raw = exc.read(4096)
                payload = json.loads(raw)
                expired = isinstance(payload,dict) and isinstance(payload.get('value'),dict) and payload['value'].get('error')=='invalid session id'
            except Exception:
                expired = False
            if expired: fail('mobile_session_gone')
            fail('mobile_driver_error')
        except (urllib.error.URLError, OSError, TimeoutError):
            fail('mobile_unavailable')
        except RDCError:
            raise
        except Exception:
            fail('mobile_driver_error')
        try: payload = json.loads(raw)
        except Exception: fail('mobile_protocol_error')
        if not isinstance(payload, dict) or 'value' not in payload: fail('mobile_protocol_error')
        value = payload['value']
        if isinstance(value, dict) and value.get('error'):
            fail('mobile_session_gone' if value['error']=='invalid session id' else 'mobile_driver_error')
        return value

    def _wd(self, session, method, path, body=None):
        return self._http(self._profiles[session['profile']], method,
            '/session/' + urllib.parse.quote(session['driver_id'], safe='') + path, body)

    def _destroy(self, session):
        self._invalidate(session)
        if 'driver_id' not in session: fail('mobile_creation_unknown')
        try: self._wd(session, 'DELETE', '')
        except RDCError as exc:
            if exc.code == 'mobile_session_gone': return
            session['setup_status'] = 'cleanup_required'
            fail('mobile_cleanup_required')

    def close(self):
        with self._lock:
            if self._closed: return
            self._publish_status(busy=True)
            try:
                for session in list(self._sessions.values()):
                    try: self._destroy(session)
                    except RDCError: pass
            finally:
                self._closed = True
                self._sessions.clear()
                self._publish_status()
