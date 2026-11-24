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
    'ios_app_launch_disabled': 'The owner must explicitly enable direct CoreDevice iOS app launch.',
    'ios_app_outcome_unknown': 'The app launch may have occurred. Inspect the device; do not replay it.',
    'ios_app_launch_unavailable': 'The exact app launch could not proceed. Prepare the owner-configured application again after inspecting the device.',
    'mirror_disabled': 'Owner opt-in and a desktop grant are required for Apple iPhone Mirroring.',
    'mirror_unavailable': 'The exact Apple iPhone Mirroring window or menu is unavailable. No other window was selected.',
    'mirror_outcome_unknown': 'Mirroring menu dispatch could not be confirmed. Inspect the phone; do not replay the action.',
    'developer_preflight_conflict': 'Close native mobile sessions before running developer-service diagnostics.',
    'mirror_conflict': 'Close native mobile sessions before using the separate owner-mediated mirroring route.',
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
    'mobile_app_outcome_unknown': 'Application lifecycle outcome could not be verified. Inspect the exact configured app state; do not replay the action.',
    'mobile_app_scope_required': 'Choose an authorized app profile and verify its foreground state before native input.',
    'mobile_native_required': 'This profile must remain in the native NATIVE_APP context. Webviews belong in a separately configured browser workflow.',
    'output_limit': 'The native driver response exceeds the permitted output size.',
    'observation_failed': 'Native observation failed. No hierarchy or control content was returned.',
    'stale_observation': 'The native observation is stale. Observe the current screen before acting.',
    'secure_input_required': 'This is a native secure field. The owner must enter the value on the device; native credential-provider filling is not available.',
    'screenshot_redaction_required': 'This native session contains or previously exposed a secure field. Safe image masking is unavailable, so no screenshot was returned. Do not bypass this refusal with another capture route.',
    'screenshot_failed': 'Native screenshot privacy or capture could not be verified. No image was returned.',
    'mobile_app_discovery_disabled': 'Installed application discovery requires an owner-enabled iOS device profile.',
    'visual_frame_required': 'Visual input requires a fresh privacy-verified frame of one unambiguous full-screen iOS window. Inspect a new frame; never replay uncertain input.',
    'compact_preview_unavailable': 'Compact mobile previews require the optional Pillow mobile extra. No image was returned.',
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
            for key in (COMPLETE_SOURCE_OPT_IN,INSTALLED_APP_OPT_IN):
                if key in caps:
                    if type(caps[key]) is not bool:
                        fail('invalid_config')
                    if caps[key] and (profile['platformName']!='iOS'
                            or not isinstance(caps.get('appium:bundleId'),str)
                            or not re.fullmatch(APP_BUNDLE_PATTERN,caps['appium:bundleId'])
                            or len(caps['appium:bundleId'])>255):
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
        ('android_usb_status', 'Read only the exact owner-configured Android USB transport and existing debugging authorization. Never automatically pairs, connects over Wi-Fi, exposes device identifiers or launches apps.', False,
         {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'}}, ('profile',)),
        ('ios_status', 'Read battery, storage, Developer Mode and trusted USB connectivity for an owner-configured iOS profile on this Mac. Auto prefers PyMobileDevice3, with libimobiledevice fallback. Go-iOS verifies identity only. Does not start automation or expose identifiers.', False,
         {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'},'backend':{'type':'string','enum':['auto','pymobiledevice3','libimobiledevice','go-ios']}}, ('profile',)),
        ('ios_developer_preflight', 'Verify the owner-configured iOS USB Developer Mode, personalized developer image and a temporary no-root RemoteXPC tunnel. Does not mount images, install apps, pair devices, start UI automation, or expose service addresses.', False,
         {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'}}, ('profile',)),
        ('ios_interaction_preflight', 'Inspect the exact iOS USB profile for native display, touch, hardware-button and accessibility service readiness. Does not capture screens, send input, read app content or grant input authority. Unknown lock or privacy state remains blocked.', False,
         {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'}}, ('profile',)),
        ('ios_app_prepare', 'Verify the exact installed app and direct CoreDevice launch support for an opted-in owner-defined iOS profile. Returns a short-lived launch observation, never private app data or identifiers.', False,
         {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'}}, ('profile',)),
        ('ios_app_launch', 'Request one owner-reviewed launch of the prepared iOS profile app without Xcode or Appium. No termination, installation, launch arguments, screen capture, or retry. Process readback does not imply foreground or native UI control.', True,
         {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'},'observation_id':string}, ('profile','observation_id')),
        ('mirror_observe', 'Read only the exact Apple iPhone Mirroring window and available fixed navigation commands. Requires owner opt-in. No phone contents or device identity are returned.', False, {}, ()),
        ('mirror_navigate', 'Request one owner-reviewed Apple iPhone Mirroring menu action with a fresh observation. The owner must verify the Apple-selected phone. No arbitrary input, capture or retry.', True,
         {'observation_id':string,'action':{'type':'string','enum':['home','app_switcher','spotlight']}}, ('observation_id','action')),
        ('start', 'Start one native Appium session using an owner-configured profile. This may launch the configured app. Optional include_observation returns fresh controls and launch-to-ready timing in the same response.', True,
         {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'},'include_observation':{'type':'boolean'}}, ('profile',)),
        ('app_discover', 'List user-installed applications on this exact owner-enabled iOS session. Returns bounded names and opaque session-scoped app selectors, never bundle IDs or arbitrary execution authority.', False, session, ('session_id',)),
        ('app_state', 'Read the exact configured or discovered iOS app state and issue a fresh single-use lifecycle observation. Same device and driver endpoint only; no private bundle or process identifiers.', False, session | {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'}}, ('session_id','profile')),
        ('app_open', 'Open or switch to one authorized iOS app on this native session. Verify foreground and invalidate old controls. Optional include_observation returns fresh controls immediately. Never retry uncertain input.', True, session | {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'},'app_observation_id':string,'include_observation':{'type':'boolean'}}, ('session_id','profile','app_observation_id')),
        ('app_terminate', 'Close one exact owner-configured iOS app and verify it stopped. Keeps the native driver session; no automatic replay.', True, session | {'profile':{'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'},'app_observation_id':string}, ('session_id','profile','app_observation_id')),
        ('observe', 'Read bounded native labels and fresh control handles. Editable values and secure field labels are redacted.', False, session, ('session_id',)),
        ('tap', 'Tap a current observed native control once. No automatic retry follows an uncertain outcome.', True, control, ('session_id','observation_id','handle')),
        ('fill', 'Replace text in a current nonsecure editable native control. Secure fields require owner input on the device.', True,
         control | {'text':{'type':'string','maxLength':4000}}, ('session_id','observation_id','handle','text')),
        ('swipe', 'Swipe in native logical coordinates from a current observation. On iOS, optionally use a freshly observed noneditable control as an explicit coordinate anchor. Refresh after input; never retry an uncertain gesture.', True,
         observed | coordinates | {'duration_ms':{'type':'integer','minimum':50,'maximum':10000}, 'anchor_handle':control['handle']},
         ('session_id','observation_id','start_x','start_y','end_x','end_y')),
        ('gesture', 'Perform one bounded simultaneous one- or two-finger iOS gesture in a freshly observed noneditable anchor. Each contact can override the common hold_ms. Optional post_frame_max_edge (320–1600) returns one verified compact frame with fresh redacted controls after the acknowledged gesture. Frame refusal preserves the input acknowledgement; never replay input. Uses logical screen coordinates.', True,
         observed | {'anchor_handle':control['handle'], 'touches':{'type':'array','minItems':1,'maxItems':2,
                      'items':{'type':'object','properties':coordinates | {'hold_ms':{'type':'integer','minimum':0,'maximum':2000}},'required':list(coordinates),'additionalProperties':False}},
                     'move_ms':{'type':'integer','minimum':50,'maximum':2000},'hold_ms':{'type':'integer','minimum':0,'maximum':2000},
                     'post_frame_max_edge':{'type':'integer','minimum':320,'maximum':1600}},
         ('session_id','observation_id','anchor_handle','touches')),
        ('visual_gesture', 'Use logical screen coordinates from a fresh privacy-verified iOS frame with one unambiguous full-screen window. Tap, scroll, swipe, drag, or perform two simultaneous contacts with independent bounded holds. Inspect each frame before acting; never replay uncertain input.', True,
         observed | {'touches':{'type':'array','minItems':1,'maxItems':2,
                      'items':{'type':'object','properties':coordinates | {'hold_ms':{'type':'integer','minimum':0,'maximum':2000}},'required':list(coordinates),'additionalProperties':False}},
                     'move_ms':{'type':'integer','minimum':50,'maximum':2000},'hold_ms':{'type':'integer','minimum':0,'maximum':2000},
                     'post_frame_max_edge':{'type':'integer','minimum':320,'maximum':1600}},
         ('session_id','observation_id','touches')),
        ('screenshot', 'Capture the native screen only after privacy checks. Optional max_edge (320–1600) returns a compact JPEG without changing logical touch coordinates. include_observation returns fresh redacted controls from the same verified capture. Secure or unverifiable screens fail closed.', False, session | {'max_edge':{'type':'integer','minimum':320,'maximum':1600},'include_observation':{'type':'boolean'}}, ('session_id',)),
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
            # Appium adds this source-only wrapper; WDA XPath starts at the app.
            path = '' if platform == 'iOS' and element.tag == 'AppiumAUT' else '/*[1]'
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
            visible = _flag(a, 'visible', parent['visible'] if parent else True)
            label = a.get('label') or a.get('name') or ''
        else:
            raise ValueError('Unsupported native platform')
        # SwiftUI Form may report a nonaccessible collection container as
        # invisible while its on-screen children are explicitly visible.
        # Only that structural container is transparent to visibility;
        # hidden apps, windows, controls and unspecified children stay hidden.
        collection_container = (platform == 'iOS'
            and kind == 'XCUIElementTypeCollectionView' and not interactive)
        visibility_blocked = ((parent is not None and parent['visibility_blocked'])
            or (not visible and not collection_container))
        row = {'element':element,'path':path,'parent':parent,'children':0,'wrapper':wrapper,'kind':kind,
            'editable':editable or secure,'secure':secure,'interactive':interactive,
            'visible':visible and not visibility_blocked, 'visibility_blocked':visibility_blocked,
            'enabled':_flag(a,'enabled', True),
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
    # Window selectors remain internal. A visible overlay, ambiguous window,
    # or non-fullscreen window must not authorize visual coordinate input.
    windows = [{'path':r['path'],'bounds':r['bounds'],'enabled':r['enabled'],
                'direct_app_child':r['parent'] is not None and r['parent']['kind']=='XCUIElementTypeApplication'}
               for r in rows if platform=='iOS' and r['kind']=='XCUIElementTypeWindow' and r['visible']]
    return {'controls':controls,'handles':handles,'visual_windows':windows,'text':'\n'.join(text),'text_truncated':text_truncated,
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


def compact_preview_available():
    try:
        from PIL import Image
        return Image is not None
    except ImportError:
        return False


def _compact_preview(raw, max_edge):
    # This function is only called after the full native privacy/capture checks.
    # Decode bounded PNG, never write an intermediate image or retain metadata.
    try:
        from PIL import Image
    except ImportError:
        fail('compact_preview_unavailable')
    expected = _png_dimensions(raw)
    with Image.open(io.BytesIO(raw), formats=['PNG']) as im:
        if im.size != expected or getattr(im,'n_frames',1) != 1:
            raise ValueError('Invalid image geometry')
        im.load()
        im.thumbnail((max_edge,max_edge), Image.Resampling.BILINEAR, reducing_gap=2.0)
        rgb = im.convert('RGB')
        rgb.info.clear()
        data = io.BytesIO()
        rgb.save(data, format='JPEG', quality=70, optimize=False)
        encoded = data.getvalue()
        if len(encoded)>MAX_IMAGE_BYTES:
            fail('output_limit')
        return encoded,rgb.width,rgb.height


def touch_actions(paths, origin, center, move_ms, hold_ms=None):
    # One dispatch with aligned ticks; independently release contacts after
    # their requested holds, without forcing the shorter hold to wait.
    actions = []
    indexed_paths = list(enumerate(paths))
    if isinstance(origin,dict) and hold_ms is not None and len(paths)>1:
        # Keep native contact indices stable as shorter contacts release.
        # Stable ordering preserves equal holds and each original logical ID.
        indexed_paths.sort(key=lambda item:item[1].get('hold_ms',hold_ms),reverse=True)
    for i, path in indexed_paths:
        sx,sy,ex,ey = (path[k] for k in ('start_x','start_y','end_x','end_y'))
        cx,cy = center
        # Resolve the observed anchor once per contact. Subsequent moves
        # retain its coordinate space and preserve the requested displacement
        # without independently rounding both endpoints around the center.
        anchored = isinstance(origin,dict)
        settle = ({'type':'pointerMove','duration':50,'origin':'pointer','x':0,'y':0}
                  if anchored else {'type':'pause','duration':50})
        destination = ({'type':'pointerMove','duration':move_ms,'origin':'pointer',
                        'x':round(ex-sx),'y':round(ey-sy)} if anchored else
                       {'type':'pointerMove','duration':move_ms,'origin':origin,
                        'x':round(ex-cx),'y':round(ey-cy)})
        seq = [{'type':'pointerMove','duration':0,'origin':origin,'x':round(sx-cx),'y':round(sy-cy)},
               {'type':'pointerDown','button':0},settle,destination]
        actions.append({'type':'pointer','id':'rdc-touch' if len(paths)==1 else 'rdc-touch-'+str(i+1),
                        'parameters':{'pointerType':'touch'},'actions':seq})
    if hold_ms is None:
        for source in actions:
            source['actions'].append({'type':'pointerUp','button':0})
        return actions
    holds = [path.get('hold_ms',hold_ms) for _,path in indexed_paths]
    previous = 0
    for boundary in sorted(set(holds)):
        active = [i for i, hold in enumerate(holds) if hold >= boundary]
        for i in active:
            actions[i]['actions'].append({'type':'pause','duration':boundary-previous})
        for i in active:
            if holds[i] == boundary:
                actions[i]['actions'].append({'type':'pointerUp','button':0})
            else:
                actions[i]['actions'].append({'type':'pause','duration':0})
        previous = boundary
    return actions


COMPLETE_SOURCE_OPT_IN = 'rdc:completeSource'
COMPLETE_SOURCE_MAX_SEQUENCE = 2147483647
COMPLETE_SOURCE_RESULT_KEYS = {
    'schema', 'request_id', 'sequence', 'outcome', 'refusal_code', 'recovery_required',
    'privacy_latched', 'xml', 'xml_sha256', 'parameters_sha256', 'metrics',
}
COMPLETE_SOURCE_COUNT_LIMITS = {
    'bulk_snapshot_calls': 1, 'source_single_calls': 10000, 'source_batch_calls': 10000,
    'source_batch_fallbacks': 10000, 'xml_bytes': MAX_XML_BYTES + 1, 'xml_nodes': 5000,
    'xml_max_depth': 64, 'tree_nodes': 4999, 'tree_max_depth': 63, 'snapshot_parameter_count': 256,
}
COMPLETE_SOURCE_DURATION_KEYS = {
    'total_ms', 'foreground_before_ms', 'wait_ms', 'snapshot_ms',
    'validate_ms', 'serialize_ms', 'foreground_after_ms',
}


def _complete_source_settings(settings):
    """Accept the actual native settings readback, without reducing source scope."""
    flags = ('includeHittableInPageSource', 'includeNativeFrameInPageSource',
             'includeNativeAccessibilityElementInPageSource', 'includeMinMaxValueInPageSource',
             'includeCustomActionsInPageSource', 'enforceCustomSnapshots', 'rdcBatchVisibilityAttributes')
    if (not isinstance(settings, dict) or settings.get('rdcCompleteSourceEnabled') is not True
            or settings.get('useJSONSource', False) is not False
            or settings.get('pageSourceExcludedAttributes', '') != ''
            or any(settings.get(key) is not False for key in flags)
            or type(settings.get('snapshotMaxDepth')) is not int
            or not 2 <= settings['snapshotMaxDepth'] <= 64
            or type(settings.get('snapshotMaxChildren')) is not int
            or settings['snapshotMaxChildren'] != 2147483647
            or settings.get('autoClickAlertSelector') not in (None, '')
            or settings.get('defaultAlertAction') != ''):
        fail('mobile_protocol_error')
    # currentDisplayId's getter reports the effective primary display even when
    # the internal explicit display selection is nil. The native route checks nil.
    return settings['snapshotMaxDepth']


def _complete_source_tree(result, spec, session):
    """Validate a private complete-source reply through the unchanged Core parser."""
    # Apply the conservative privacy signal before validating any other field.
    if isinstance(result, dict) and result.get('privacy_latched') is True:
        session['sensitive'] = True
    if (not isinstance(result, dict) or set(result) != COMPLETE_SOURCE_RESULT_KEYS
            or type(result.get('schema')) is not int or result['schema'] != 1
            or result.get('request_id') != spec['request_id']
            or type(result.get('sequence')) is not int or result['sequence'] != spec['sequence']
            or result.get('outcome') not in ('complete', 'refused')
            or type(result.get('recovery_required')) is not bool
            or type(result.get('privacy_latched')) is not bool):
        fail('observation_failed')
    for key in ('xml_sha256', 'parameters_sha256'):
        value = result[key]
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)):
            fail('observation_failed')
    refusal = result['refusal_code']
    if refusal is not None and (not isinstance(refusal, str) or not re.fullmatch(r'[a-z_]{1,64}', refusal)):
        fail('observation_failed')
    metrics = result['metrics']
    if not isinstance(metrics, dict) or set(metrics) != set(COMPLETE_SOURCE_COUNT_LIMITS) | COMPLETE_SOURCE_DURATION_KEYS:
        fail('observation_failed')
    for key, maximum in COMPLETE_SOURCE_COUNT_LIMITS.items():
        if type(metrics[key]) is not int or not 0 <= metrics[key] <= maximum:
            fail('observation_failed')
    for key in COMPLETE_SOURCE_DURATION_KEYS:
        value = metrics[key]
        if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 120000:
            fail('observation_failed')
    if result['outcome'] == 'refused':
        if refusal is None or result['xml'] is not None or result['xml_sha256'] is not None:
            fail('observation_failed')
        fail('screenshot_redaction_required' if session['sensitive'] else 'observation_failed')
    if (refusal is not None or result['recovery_required'] or result['privacy_latched']
            or result['xml_sha256'] is None or result['parameters_sha256'] is None):
        fail('observation_failed')
    # The complete-source mode never substitutes its own redaction/parser rules.
    source = result['xml']
    tree = _native_tree(source, 'iOS')
    if tree['sensitive']:
        session['sensitive'] = True
        fail('screenshot_redaction_required')
    if tree['control_scan_truncated']:
        fail('observation_failed')
    raw = source.encode('utf-8')
    if tree['digest'].hex() != result['xml_sha256'] or len(raw) != metrics['xml_bytes']:
        fail('observation_failed')
    # Read only the identity and shape of the same already bounded XML. No new
    # driver source request occurs, and no XML is saved or returned to tool users.
    root = ET.fromstring(raw)
    if root.tag != 'AppiumAUT' or len(root) != 1:
        fail('observation_failed')
    app = root[0]
    if (app.tag != 'XCUIElementTypeApplication' or app.get('type') != app.tag
            or app.get('bundleId') != spec['expected_bundle_id']
            or app.get('processId') != str(spec['expected_pid'])):
        fail('observation_failed')
    nodes, depth = 0, 0
    pending = [(root, 1)]
    while pending:
        node, level = pending.pop()
        nodes += 1
        depth = max(depth, level)
        if nodes > 5000 or level > 64 or (node is not app and node.tag == 'XCUIElementTypeApplication'):
            fail('observation_failed')
        pending.extend((child, level + 1) for child in node)
    if (nodes != metrics['xml_nodes'] or depth != metrics['xml_max_depth']
            or metrics['tree_nodes'] + 1 != nodes or metrics['tree_max_depth'] + 1 != depth
            or not metrics['tree_max_depth'] < spec['snapshot_max_depth']
            or metrics['bulk_snapshot_calls'] != 1 or metrics['source_single_calls'] != 0
            or metrics['source_batch_calls'] != 0 or metrics['source_batch_fallbacks'] != 0
            or not 2 <= metrics['snapshot_parameter_count'] <= 256
            or metrics['total_ms'] >= 5000
            or any(metrics[key] > metrics['total_ms'] for key in COMPLETE_SOURCE_DURATION_KEYS)):
        fail('observation_failed')
    previous_parameters = session.get('complete_source_parameters')
    if previous_parameters is not None and previous_parameters != result['parameters_sha256']:
        fail('observation_failed')
    session['complete_source_parameters'] = result['parameters_sha256']
    return tree


INSTALLED_APP_OPT_IN = 'rdc:installedAppDiscovery'
APP_BUNDLE_PATTERN = r'[A-Za-z][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)+'
MAX_DISCOVERED_APPS = 256


class Mobile:
    def __init__(self, settings):
        profiles = getattr(settings, 'mobile_profiles', {})
        validate_mobile_profiles(profiles)
        self._profiles = copy.deepcopy(profiles)
        self._sessions = {}
        from .ios_mirroring import Mirroring
        self._mirroring = Mirroring(settings)
        from .ios_app import IOSAppLaunch
        self._ios_app = IOSAppLaunch(settings,self._profiles)
        self._lock = threading.RLock()
        self._status_lock = threading.Lock()
        self._closed = False
        from .mobile_command_engine import descriptors
        self._catalog = {row['name']:row for row in [*_catalog(),*descriptors()]}
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
        if 'active_profile' in session:
            info['active_profile'] = session['active_profile']
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
            if name in ('rdc_mobile_command_read','rdc_mobile_command_execute'):
                from .mobile_command_engine import dispatch
                return dispatch(self,name,args)
            action = name.removeprefix('rdc_mobile_')
            if action == 'screenshot': return self.snapshot(args['session_id'],max_edge=args.get('max_edge'),
                include_observation=args.get('include_observation',False))
            self._publish_status(busy=True)
            try:
                if action in ('ios_app_prepare','ios_app_launch'):
                    if self._sessions: fail('developer_preflight_conflict')
                    self._mirroring.observation = None
                    if action == 'ios_app_prepare': return self._ios_app.prepare(args['profile'])
                    return self._ios_app.launch(args['profile'],args['observation_id'])
                if action in ('mirror_observe','mirror_navigate'):
                    if self._sessions: fail('mirror_conflict')
                    self._ios_app.invalidate()
                    if action == 'mirror_observe': return self._mirroring.observe()
                    return self._mirroring.navigate(args['observation_id'],args['action'])
                if action == 'start':
                    self._ios_app.invalidate()
                    self._mirroring.observation = None
                    return self._start(args['profile'],args.get('include_observation',False))
                if action in ('ios_developer_preflight','ios_interaction_preflight'):
                    if self._sessions: fail('developer_preflight_conflict')
                    profile = self._profiles.get(args['profile'])
                    if profile is None or profile['platformName'] != 'iOS':
                        fail('profile_not_found')
                    from .ios_usb import developer_preflight, interaction_preflight
                    operation = interaction_preflight if action == 'ios_interaction_preflight' else developer_preflight
                    return operation(profile['capabilities']['appium:udid'])
                if action == 'android_usb_status':
                    profile = self._profiles.get(args['profile'])
                    if profile is None or profile['platformName'] != 'Android':
                        fail('profile_not_found')
                    from .android_usb import usb_check
                    return usb_check(profile['capabilities']['appium:udid'])
                if action == 'ios_status':
                    profile = self._profiles.get(args['profile'])
                    if profile is None or profile['platformName'] != 'iOS':
                        fail('profile_not_found')
                    from .ios_usb import preferred_device_metrics
                    return preferred_device_metrics(profile['capabilities']['appium:udid'], args.get('backend','auto'))

                session = self._sessions.get(args['session_id'])
                if session is None: fail('session_not_found')
                if action == 'close':
                    self._destroy(session)
                    del self._sessions[session['session_id']]
                    return {'session_id':session['session_id'],'closed':True}
                if session.get('setup_status'): fail('mobile_cleanup_required')
                if action == 'app_discover': return self._app_discover(session)
                if action == 'app_state': return self._app_state(session, args['profile'])
                if action in ('app_open','app_terminate'): return self._app_lifecycle(session, action, args)
                if action == 'observe': return self._observe(session)
                result = self._act(session, action, args)
                if 'post_frame_max_edge' not in args:
                    return result
                # Dispatch exactly once. A subsequent frame is a separate
                # read outcome, not evidence that input failed or can be replayed.
                try:
                    frame = self._snapshot(session['session_id'],
                        max_edge=args['post_frame_max_edge'],include_observation=True)
                except RDCError as exc:
                    self._invalidate(session)
                    code = exc.code if exc.code in MESSAGES else 'screenshot_failed'
                    return result | self._info(session) | {'frame_status':'unavailable','frame_error':code}
                except Exception:
                    self._invalidate(session)
                    return result | self._info(session) | {'frame_status':'unavailable','frame_error':'screenshot_failed'}
                return result | frame | {'frame_status':'captured'}
            finally:
                self._publish_status()

    def _start(self, profile_name, include_observation=False):
        started=time.perf_counter()
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
        complete_source=caps.pop(COMPLETE_SOURCE_OPT_IN,False)
        session['installed_app_discovery']=caps.pop(INSTALLED_APP_OPT_IN,False)
        if complete_source:
            session.update(complete_source_enabled=True,complete_source_sequence=1,
                           complete_source_nonce=str(uuid.uuid4()),complete_source_blocked=False)
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
            identity=self._native(session)
            self._dimensions(session)
            if complete_source:
                if identity is None: fail('mobile_native_required')
                self._wd(session,'POST','/appium/settings',{'settings':{'rdcCompleteSourceEnabled':True}})
                session['complete_source_depth']=_complete_source_settings(self._wd(session,'GET','/appium/settings'))
        except Exception:
            try: self._destroy(session)
            except RDCError:
                session['setup_status'] = 'cleanup_required'
                self._sessions[session['session_id']] = session
                fail('mobile_cleanup_required')
            raise
        self._sessions[session['session_id']] = session
        result=self._info(session)
        return self._ready(session,identity,result,started) if include_observation else result

    @staticmethod
    def _device_key(profile):
        endpoint = urllib.parse.urlsplit(profile['endpoint'])
        return (endpoint.scheme, endpoint.hostname.lower(), endpoint.port or (443 if endpoint.scheme=='https' else 80),
                endpoint.path.rstrip('/'), profile['platformName'], profile['capabilities']['appium:udid'].casefold())

    def _native(self, session):
        try:
            if self._wd(session, 'GET', '/context') != 'NATIVE_APP':
                fail('mobile_native_required')
            active_profile = session.get('active_profile', session['profile'])
            if active_profile is None: fail('mobile_app_scope_required')
            capabilities = self._profiles[session['profile']]['capabilities']
            # Explicitly configured iOS applications are the observation and
            # input boundary. A context name alone cannot establish foreground
            # application identity. Only this fixed read-only driver operation
            # is permitted; callers cannot supply a driver script.
            if session['platform'] == 'iOS' and 'appium:bundleId' in capabilities:
                expected = self._app_target(session,active_profile)
                if not isinstance(expected, str) or not expected.strip():
                    fail('mobile_native_required')
                actual = self._wd(session, 'POST', '/execute/sync',
                    {'script':'mobile: activeAppInfo','args':[]})
                if not isinstance(actual, dict) or actual.get('bundleId') != expected:
                    fail('mobile_native_required')
                identity = session.get('active_identity')
                if identity is not None and (actual.get('bundleId'), actual.get('pid')) != identity:
                    fail('mobile_app_scope_required')
                if type(actual.get('pid')) is int and actual['pid'] > 0:
                    return (expected,actual['pid'])
        except Exception:
            self._invalidate(session)
            raise

    def _app_target(self, session, alias):
        profile = self._profiles.get(alias)
        original = self._profiles[session['profile']]
        if session['platform']!='iOS': fail('profile_not_found')
        if profile is None:
            bundle=session.get('discovered_apps',{}).get(alias) if session.get('installed_app_discovery') else None
            if bundle is None: fail('profile_not_found')
        else:
            if profile['platformName']!='iOS' or self._device_key(profile)!=self._device_key(original):
                fail('profile_not_found')
            bundle=profile['capabilities'].get('appium:bundleId')
        base = original['capabilities'].get('appium:bundleId')
        if (not isinstance(bundle,str) or len(bundle)>256
                or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)+',bundle)
                or not isinstance(base,str) or not base):
            fail('mobile_app_scope_required')
        return bundle

    def _app_discover(self,session):
        if session['platform']!='iOS' or not session.get('installed_app_discovery'):
            fail('mobile_app_discovery_disabled')
        session.pop('app_ticket',None)
        started=time.perf_counter()
        # The driver endpoint and physical identity are bound by the existing
        # owner-defined session. Do not request any app data or raw identifiers.
        value=self._wd(session,'POST','/execute/sync',{'script':'mobile: listApps','args':[{
            'applicationType':'User','returnAttributes':['CFBundleIdentifier','CFBundleDisplayName','CFBundleName','ApplicationType']}]})
        if not isinstance(value,dict) or len(value)>2048: fail('mobile_protocol_error')
        old=session.get('discovered_apps',{})
        prior={bundle:alias for alias,bundle in old.items()}
        original=self._profiles[session['profile']]
        configured={}
        for alias,profile in self._profiles.items():
            if self._device_key(profile)==self._device_key(original):
                bundle=profile['capabilities'].get('appium:bundleId')
                if isinstance(bundle,str): configured.setdefault(bundle,alias)
        selected={}; public=[]
        for bundle,entry in value.items():
            if (not isinstance(bundle,str) or len(bundle)>255 or not re.fullmatch(APP_BUNDLE_PATTERN,bundle)
                    or bundle.casefold().endswith('.xctrunner') or bundle=='com.apple.springboard'
                    or not isinstance(entry,dict) or entry.get('ApplicationType')!='User'
                    or entry.get('CFBundleIdentifier',bundle)!=bundle): continue
            name=entry.get('CFBundleDisplayName') or entry.get('CFBundleName')
            if not isinstance(name,str) or not name.strip(): continue
            name=''.join(ch for ch in name if ch.isprintable()).strip()[:120]
            if not name: continue
            alias=configured.get(bundle)
            if alias is None:
                alias=prior.get(bundle)
                if alias is None:
                    alias='app-'+uuid.uuid4().hex
                    while alias in self._profiles or alias in selected: alias='app-'+uuid.uuid4().hex
                selected[alias]=bundle
            public.append({'profile':alias,'name':name})
        if len(public)>MAX_DISCOVERED_APPS: fail('output_limit')
        session['discovered_apps']=selected
        active=session.get('active_profile',session['profile'])
        if active in old and active not in selected:
            self._invalidate(session)
            session.update(active_profile=None,active_identity=None)
        return {'session_id':session['session_id'],'apps':sorted(public,key=lambda row:(row['name'].casefold(),row['profile'])),
                'scope':'installed_user_apps','discovery_ms':round((time.perf_counter()-started)*1000,3)}

    def _app_context(self, session):
        if self._wd(session,'GET','/context') != 'NATIVE_APP': fail('mobile_native_required')
        actual = self._wd(session,'POST','/execute/sync',{'script':'mobile: activeAppInfo','args':[]})
        if (not isinstance(actual,dict) or not isinstance(actual.get('bundleId'),str)
                or not 1 <= len(actual['bundleId']) <= 256
                or type(actual.get('pid')) is not int or actual['pid'] <= 0):
            fail('mobile_protocol_error')
        return (actual['bundleId'],actual['pid'])

    def _app_read_state(self, session, bundle):
        state = self._wd(session,'POST','/execute/sync',{'script':'mobile: queryAppState','args':[{'bundleId':bundle}]})
        if type(state) is not int or state not in (1,2,3,4): fail('mobile_protocol_error')
        return state

    @staticmethod
    def _app_public_state(state):
        return {1:'not_running',2:'background_suspended',3:'background',4:'foreground'}[state]

    def _app_state(self, session, alias):
        session.pop('app_ticket',None)
        bundle = self._app_target(session,alias)
        try:
            identity = self._app_context(session)
            state = self._app_read_state(session,bundle)
            if (state == 4) != (identity[0] == bundle): fail('mobile_app_scope_required')
            current = session.get('active_profile',session['profile'])
            if current is not None:
                current_bundle = self._app_target(session,current)
                if current_bundle != identity[0] or (session.get('active_identity') is not None and session['active_identity'] != identity):
                    self._invalidate(session)
                    session.update(active_profile=None,active_identity=None)
            if state == 4 and (session.get('active_profile',session['profile']) != alias or session.get('active_identity') != identity):
                self._invalidate(session)
                session.update(active_profile=alias,active_identity=identity)
        except Exception:
            self._invalidate(session)
            session.update(active_profile=None,active_identity=None)
            raise
        token = str(uuid.uuid4())
        session['app_ticket'] = (token,alias,bundle,state,identity,time.monotonic()+30)
        return {'session_id':session['session_id'],'profile':alias,'app_observation_id':token,
                'app_state':self._app_public_state(state),'foreground_verified':state==4,
                'active_profile':session.get('active_profile',session['profile'])}

    def _app_lifecycle(self, session, action, args):
        started=time.perf_counter()
        alias = args['profile']
        bundle = self._app_target(session,alias)
        ticket = session.pop('app_ticket',None)
        if (not ticket or ticket[:3] != (args['app_observation_id'],alias,bundle)
                or ticket[5] < time.monotonic()): fail('stale_observation')
        try:
            identity = self._app_context(session)
            state = self._app_read_state(session,bundle)
            if identity != ticket[4] or state != ticket[3] or (state==4)!=(identity[0]==bundle):
                fail('stale_observation')
        except Exception:
            self._invalidate(session)
            session.update(active_profile=None,active_identity=None)
            raise
        self._invalidate(session)
        session.update(active_profile=None,active_identity=None)
        try:
            if action == 'app_open':
                if state != 4:
                    self._wd(session,'POST','/execute/sync',{'script':'mobile: launchApp','args':[{'bundleId':bundle}]})
                current = self._app_context(session)
                if current[0] != bundle or self._app_read_state(session,bundle) != 4:
                    fail('mobile_app_outcome_unknown')
                self._dimensions(session)
                session.update(active_profile=alias,active_identity=current)
                result=self._info(session) | {'performed':action,'foreground_verified':True,'app_state':'foreground'}
                return self._ready(session,current,result,started) if args.get('include_observation',False) else result
            if state != 1:
                acknowledged = self._wd(session,'POST','/execute/sync',{'script':'mobile: terminateApp','args':[{'bundleId':bundle}]})
                if acknowledged is not True: fail('mobile_app_outcome_unknown')
            if self._app_read_state(session,bundle) != 1: fail('mobile_app_outcome_unknown')
            return self._info(session) | {'performed':action,'terminated_verified':True,'app_state':'not_running'}
        except Exception:
            # A dispatched app operation may have succeeded even on a lost response.
            # Only a new exact state observation can recover UI scope; never replay.
            fail('mobile_app_outcome_unknown')

    def _dimensions(self, session):
        rect = self._wd(session, 'GET', '/window/rect')
        if not isinstance(rect, dict): fail('mobile_protocol_error')
        for key in ('width','height'):
            value = rect.get(key)
            if type(value) not in (float,int) or not math.isfinite(value) or not 1 <= value <= 16384:
                fail('mobile_protocol_error')
        session.update(width=rect['width'], height=rect['height'])

    def _complete_source(self, session, identity):
        """One exact fixed read; any failure permanently requires session cleanup."""
        if session.get('complete_source_blocked') or session.get('setup_status'):
            self._invalidate(session)
            fail('mobile_cleanup_required')
        session['complete_source_blocked'] = True  # Close before metadata or dispatch.
        try:
            sequence = session.get('complete_source_sequence')
            expected_pid = identity[1] if identity is not None else None
            nonce = session.get('complete_source_nonce')
            depth = session.get('complete_source_depth')
            if (type(sequence) is not int or not 1 <= sequence <= COMPLETE_SOURCE_MAX_SEQUENCE
                    or type(expected_pid) is not int or not 1 <= expected_pid <= 2147483647
                    or not isinstance(nonce, str)
                    or not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', nonce)
                    or type(depth) is not int or not 2 <= depth <= 64):
                fail('mobile_protocol_error')
            profile = self._profiles[session['profile']]
            if identity is None or identity[0]!=self._app_target(session,session.get('active_profile',session['profile'])):
                fail('mobile_native_required')
            spec = {'schema': 1, 'request_id': nonce + ':' + str(sequence),
                    'sequence': sequence, 'expected_bundle_id': identity[0],
                    'expected_pid': expected_pid, 'snapshot_max_depth': depth}
            session['complete_source_sequence'] += 1  # Consume before the one dispatch.
            path = '/session/' + urllib.parse.quote(session['driver_id'], safe='') + '/execute/sync'
            result = self._http(profile, 'POST', path,
                {'script': 'mobile: rdcCompleteSource', 'args': [{'spec': spec}]}, timeout=10)
            tree = _complete_source_tree(result, spec, session)
        except BaseException as exc:
            session['setup_status'] = 'cleanup_required'
            self._invalidate(session)
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, RDCError) and exc.code in ('screenshot_redaction_required', 'mobile_session_gone'):
                raise
            fail('observation_failed')
        session['complete_source_blocked'] = False
        return tree

    def _source(self, session, identity=None):
        if session.get('complete_source_enabled'):
            return self._complete_source(session,identity)
        try:
            tree = _native_tree(self._wd(session, 'GET', '/source'), session['platform'])
        except RDCError:
            raise
        except Exception:
            fail('observation_failed')
        if tree['sensitive']: session['sensitive'] = True
        return tree

    def _ready(self,session,identity,result,started):
        # The app has already passed foreground and geometry checks. Reuse them,
        # but only the guarded native route can certify both ends of source read.
        launch_ms=round((time.perf_counter()-started)*1000,3)
        source_started=time.perf_counter()
        try:
            tree=self._source(session,identity)
            if identity is not None and not session.get('complete_source_enabled'):
                if self._native(session)!=identity: fail('observation_failed')
            observed=self._commit_observation(session,tree)
            return result | observed | {'ready':True,'timings_ms':{
                'launch_verified':launch_ms,'control_discovery':round((time.perf_counter()-source_started)*1000,3),
                'launch_to_ready':round((time.perf_counter()-started)*1000,3)}}
        except Exception as exc:
            self._invalidate(session)
            code=exc.code if isinstance(exc,RDCError) and exc.code in MESSAGES else 'observation_failed'
            # Launch may have succeeded. Keep its acknowledgement and session,
            # even when the read fails; never cause a second launch.
            return result | self._info(session) | {'ready':False,'ready_error':code,'timings_ms':{
                'launch_verified':launch_ms,'control_discovery':round((time.perf_counter()-source_started)*1000,3),
                'launch_to_ready':round((time.perf_counter()-started)*1000,3)}}

    def _observe(self, session):
        self._invalidate(session)
        try:
            identity=self._native(session)
            self._dimensions(session)
            tree = self._source(session,identity)
            return self._commit_observation(session,tree)
        except RDCError as exc:
            self._invalidate(session)
            fail('mobile_session_gone' if exc.code=='mobile_session_gone' else 'observation_failed')
        except Exception:
            self._invalidate(session)
            fail('observation_failed')

    def _commit_observation(self, session, tree):
        session.update(observation_id=str(uuid.uuid4()), handles=tree['handles'],
            source_digest=tree['digest'], observation_size=(session['width'],session['height']))
        result=self._info(session) | {key:tree[key] for key in (
            'controls','text','text_truncated','controls_truncated','control_scan_truncated')}
        from .mobile_command_engine import record_terminal_observation
        record_terminal_observation(session,result)
        return result

    @staticmethod
    def _visual_window(tree, size):
        windows = tree.get('visual_windows',[])
        if len(windows)!=1 or tree['sensitive']: return None
        window=windows[0]
        if (not window['enabled'] or not window['direct_app_child'] or window['bounds'] is None): return None
        b=window['bounds']
        if any(abs(b[k]-v)>0.5 for k,v in zip(('x','y','width','height'),(0,0,*size))): return None
        return {'path':window['path'],'control':{'bounds':b}}

    def _current(self, session, observation_id):
        if not observation_id or session['observation_id'] != observation_id: fail('stale_observation')
        identity=self._native(session)
        self._dimensions(session)
        tree = self._source(session,identity)
        if (tree['digest'] != session.get('source_digest')
                or (session['width'],session['height']) != session.get('observation_size')):
            self._invalidate(session)
            fail('stale_observation')
        return identity,tree

    def _act(self, session, action, args):
        visual = None
        if action=='visual_gesture':
            visual=session.pop('visual_frame',None)
            if (visual is None or visual['observation_id']!=args['observation_id']
                    or visual['deadline']<time.monotonic() or session['sensitive']):
                fail('visual_frame_required')
        identity,tree=self._current(session, args['observation_id'])
        handle = None
        anchor = None
        if action in ('tap','fill'):
            handle = session['handles'].get(args['handle'])
            if handle is None: fail('stale_observation')
            control = handle['control']
            if action=='fill' and control['secure']: fail('secure_input_required')
            if not control['can_tap'] or (action=='fill' and (not control['can_fill'] or '\0' in args['text'])):
                fail('invalid_arguments')
        elif action in ('swipe','gesture','visual_gesture'):
            paths = [args] if action=='swipe' else args['touches']
            if any(path[key]>=session['width' if key.endswith('_x') else 'height']
                   for path in paths for key in ('start_x','start_y','end_x','end_y')):
                fail('invalid_arguments')
            if visual is not None:
                if session['sensitive'] or identity!=visual['identity']:
                    self._invalidate(session)
                    fail('visual_frame_required')
                anchor=self._visual_window(tree,(session['width'],session['height']))
                if anchor is None or anchor!=visual['anchor'] or len({(p['start_x'],p['start_y']) for p in paths})!=len(paths):
                    self._invalidate(session)
                    fail('visual_frame_required')
            if 'anchor_handle' in args:
                if session['platform'] != 'iOS': fail('invalid_arguments')
                if session['sensitive']: fail('secure_input_required')
                if len({(p['start_x'],p['start_y']) for p in paths})!=len(paths): fail('invalid_arguments')
                anchor = session['handles'].get(args['anchor_handle'])
                if anchor is None: fail('stale_observation')
                control = anchor['control']
                if control['editable'] or control['secure'] or not control['can_tap']:
                    fail('invalid_arguments')
                b = control['bounds']
                if (b['x'] < 0 or b['y'] < 0 or b['x']+b['width'] > session['width']
                        or b['y']+b['height'] > session['height']):
                    fail('invalid_arguments')
                if any(not (b['x'] <= path[k+'_x'] < b['x']+b['width']
                            and b['y'] <= path[k+'_y'] < b['y']+b['height'])
                       for path in paths for k in ('start','end')):
                    fail('invalid_arguments')
        else:
            fail('unknown_tool')
        # The driver can complete an input even when its response is lost.
        self._invalidate(session)
        if action in ('swipe','gesture','visual_gesture'):
            origin = 'viewport'
            center = (0,0)
            if anchor is not None:
                found = self._wd(session, 'POST', '/element', {'using':'xpath','value':anchor['path']})
                if not isinstance(found, dict) or not isinstance(found.get(ELEMENT_KEY), str) or not 1<=len(found[ELEMENT_KEY])<=256:
                    fail('mobile_protocol_error')
                element_id = found[ELEMENT_KEY]
                rect = self._wd(session, 'GET', '/element/' + urllib.parse.quote(element_id,safe='') + '/rect')
                b = anchor['control']['bounds']
                if not isinstance(rect,dict) or any(type(rect.get(k)) not in (float,int) or not math.isfinite(rect[k])
                        or abs(rect[k]-b[k])>0.5 for k in ('x','y','width','height')):
                    fail('stale_observation')
                center = (rect['x']+rect['width']/2,rect['y']+rect['height']/2)
                origin = {ELEMENT_KEY:element_id}
            if visual is not None and (self._native(session)!=visual['identity'] or time.monotonic()>visual['deadline']):
                fail('visual_frame_required')
            move_ms = args.get('duration_ms',400) if action=='swipe' else args.get('move_ms',200)
            hold_ms = None if action=='swipe' else args.get('hold_ms',0)
            actions = touch_actions(paths,origin,center,move_ms,hold_ms)
            try:
                self._wd(session, 'POST', '/actions', {'actions':actions})
            except RDCError:
                try: self._wd(session, 'DELETE', '/actions')
                except RDCError:
                    session['setup_status'] = 'cleanup_required'
                    fail('mobile_cleanup_required')
                raise
            session['cursor'] = {'x':paths[0]['end_x'],'y':paths[0]['end_y']}
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

    def snapshot(self, session_id, max_edge=None, include_observation=False):
        if type(include_observation) is not bool: fail('invalid_arguments')
        if max_edge is not None and (type(max_edge) is not int or not 320<=max_edge<=1600):
            fail('invalid_arguments')
        with self._lock:
            if self._closed: fail('closed')
            self._publish_status(busy=True)
            try:
                return self._snapshot(session_id,max_edge=max_edge,include_observation=include_observation)
            finally:
                self._publish_status()

    def _snapshot(self, session_id, max_edge=None, include_observation=False):
        session = self._sessions.get(session_id)
        if session is None: fail('session_not_found')
        if session.get('setup_status'): fail('mobile_cleanup_required')
        session.pop('visual_frame',None)
        if include_observation:
            self._invalidate(session)
        if session['sensitive']:
            self._invalidate(session)
            fail('screenshot_redaction_required')
        try:
            before_identity=self._native(session)
            self._dimensions(session)
            capture_size = (session['width'],session['height'])
            before = self._source(session,before_identity)
            if session['sensitive']: fail('screenshot_redaction_required')
            encoded = self._wd(session, 'GET', '/screenshot')
            captured_at_ms = int(time.time()*1000)
            captured_monotonic = time.monotonic()
            if not isinstance(encoded, str) or len(encoded)>4*((MAX_IMAGE_BYTES+2)//3):
                fail('output_limit')
            raw = base64.b64decode(encoded, validate=True)
            pixel_width,pixel_height = _png_dimensions(raw)
            after_identity=self._native(session)
            self._dimensions(session)
            after = self._source(session,after_identity)
            if session['sensitive']: fail('screenshot_redaction_required')
            if (before_identity != after_identity or capture_size != (session['width'],session['height']) or before['digest'] != after['digest']
                    or (pixel_width > pixel_height) != (capture_size[0] > capture_size[1])
                    or abs((pixel_width/pixel_height)/(capture_size[0]/capture_size[1])-1) > .03):
                self._invalidate(session)
                fail('screenshot_failed')
        except RDCError as exc:
            self._invalidate(session)
            if exc.code in ('screenshot_redaction_required','output_limit','mobile_session_gone'): raise
            fail('screenshot_failed')
        except Exception:
            self._invalidate(session)
            fail('screenshot_failed')
        # A plain preview never rotates a valid observation ID. However, if
        # the verified frame belongs to a changed hierarchy or geometry,
        # the previously issued control handles must no longer be usable.
        if (session.get('observation_id') and (after['digest'] != session.get('source_digest')
                or capture_size != session.get('observation_size'))):
            self._invalidate(session)
        mime_type = 'image/png'
        extra = {}
        if max_edge is not None:
            extra = {'capture_width':pixel_width,'capture_height':pixel_height}
            try:
                raw,pixel_width,pixel_height = _compact_preview(raw,max_edge)
            except RDCError:
                self._invalidate(session)
                raise
            except Exception:
                self._invalidate(session)
                fail('screenshot_failed')
            mime_type = 'image/jpeg'
        data = base64.b64encode(raw).decode('ascii')
        # Publish handles only after both privacy probes and image conversion
        # succeed. Reuse the already verified hierarchy, avoiding an extra
        # native observation roundtrip. This does not certify dynamic pixels.
        observation = self._commit_observation(session,after) if include_observation else self._info(session)
        if include_observation:
            anchor=self._visual_window(after,capture_size) if before_identity is not None else None
            if anchor is not None and captured_monotonic+30>=time.monotonic():
                session['visual_frame']={'observation_id':observation['observation_id'],
                    'identity':after_identity,'anchor':anchor,'deadline':captured_monotonic+30}
            extra.update(observation_source='verified_frame',captured_at_ms=captured_at_ms,
                         capture_time_source='host_receive',visual_gesture_available='visual_frame' in session)
        return observation | extra | {'mime_type':mime_type,'data':data,
            'source_width':pixel_width,'source_height':pixel_height,
            'input_width':session['width'],'input_height':session['height'],
            'input_scale_x':session['width']/pixel_width,'input_scale_y':session['height']/pixel_height,
            'coordinate_system':'native logical pixels'}

    @staticmethod
    def _invalidate(session):
        session['observation_id'] = None
        session['handles'] = {}
        session.pop('app_ticket',None)
        session.pop('visual_frame',None)
        session.pop('terminal_observation',None)

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
                self._ios_app.invalidate()
                self._publish_status()
