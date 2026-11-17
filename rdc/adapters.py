"""Optional device adapters. Browser objects live on one dedicated owning thread.

Browser navigation has full network access from the worker. It is not a sandbox.
WebDriver profile/desktop isolation depends on the owner-configured driver.
"""
from __future__ import annotations
import base64
import copy
import io
import json
import math
import os
import queue
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import Future
from .errors import RDCError
from .mobile import Mobile, _native_tree, _png_dimensions, MAX_XML_BYTES, MESSAGES as MOBILE_MESSAGES

MAX_SESSIONS = 8
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ELEMENT_KEY = 'element-6066-11e4-a52e-4f735466cecf'
SELECTOR = 'a,button,input,textarea,select,[role="button"],[contenteditable="true"]'
SENSITIVE_SELECTOR = 'input[type="password"],[data-rdc-private-field]'
DOCUMENT_SCRIPT = "/* RDC_DOCUMENT */ return window.__rdcDocumentId || (window.__rdcDocumentId = crypto.randomUUID ? crypto.randomUUID() : String(Math.random()));"
OBSERVE_BODY = """
const selector='a,button,input,textarea,select,[role="button"],[contenteditable="true"]';
const nodes=[],walkers=[document.createTreeWalker(document,NodeFilter.SHOW_ELEMENT)];
let visited=0,candidates=0,controlsTruncated=false,scanTruncated=false;
while(walkers.length){
 const e=walkers[walkers.length-1].nextNode();
 if(!e){walkers.pop();continue;}
 if(++visited>5000){scanTruncated=true;break;}
 if(e.shadowRoot)walkers.push(document.createTreeWalker(e.shadowRoot,NodeFilter.SHOW_ELEMENT));
 if(!e.matches(selector))continue;
 if(++candidates>300){scanTruncated=true;break;}
 const style=getComputedStyle(e);
 if(style.visibility==='hidden'||style.visibility==='collapse'||
    !Array.from(e.getClientRects()).some(r=>r.width>0&&r.height>0))continue;
 if(nodes.length===150){controlsTruncated=true;break;}
 nodes.push(e);
}
const text=document.body?.innerText||'',sensitive=window.__rdcSensitiveFields;
const data={document_id:window.__rdcDocumentId||(window.__rdcDocumentId=String(Math.random())),
 text:text.slice(0,24000),text_truncated:text.length>24000,width:innerWidth,height:innerHeight,
 controls_truncated:controlsTruncated||scanTruncated,control_scan_truncated:scanTruncated,
 controls:nodes.map(e=>{
  const remembered=!!sensitive?.has(e);
  if(remembered)e.setAttribute('data-rdc-private-field','');
  const privateField=remembered||e.type==='password'||e.getAttribute('data-rdc-private-field')!==null;
  const name=e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.innerText||e.getAttribute('placeholder')||e.name||'';
  const value=privateField?'[redacted]':String(e.value||'');
  return {tag:e.tagName.toLowerCase(),role:e.getAttribute('role')||'',name:name.slice(0,240),
   name_truncated:name.length>240,type:e.type||'',value:value.slice(0,1000),value_truncated:value.length>1000,disabled:!!e.disabled};
 })};
"""
OBSERVE_SCRIPT = '/* RDC_OBSERVE */' + OBSERVE_BODY + 'return {...data,controls:data.controls.map((c,i)=>({...c,element:nodes[i]}))};'
PLAYWRIGHT_OBSERVE_SCRIPT = '()=>{' + OBSERVE_BODY + 'return {data,elements:nodes};}'
SENSITIVE_DOCUMENT_SCRIPT = """/* RDC_PRIVATE_DOCUMENT */
return {document_id:window.__rdcDocumentId||(window.__rdcDocumentId=String(Math.random())),
 sensitive:!!window.__rdcSensitiveFields};
"""

CREDENTIAL_VALIDATE_BODY = """
return {origin:location.origin, form_origin:e?.form ? new URL(e.form.action,location.href).origin : location.origin,
 valid:!!e && e.ownerDocument===document && e.isConnected && e.tagName==='INPUT' && e.type==='password'
       && !e.disabled && !e.readOnly && e.getClientRects().length>0};
"""
CREDENTIAL_FILL_BODY = """
if(location.origin!==expected || window.__rdcDocumentId!==doc || !e || e.ownerDocument!==document ||
 !e.isConnected || e.tagName!=='INPUT' || e.type!=='password' || e.disabled || e.readOnly ||
 !e.getClientRects().length || (e.form && new URL(e.form.action,location.href).origin!==expected)) return false;
// Check and assignment occur in one JavaScript turn, before any input listener.
// Remember the element independently of type so Show Password cannot expose it.
const sensitive=window.__rdcSensitiveFields||(window.__rdcSensitiveFields=new WeakSet());
sensitive.add(e);
e.setAttribute('data-rdc-private-field','');
const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
setter.call(e,secret);
e.dispatchEvent(new Event('input',{bubbles:true}));
e.dispatchEvent(new Event('change',{bubbles:true}));
return true;
"""


def _schema(properties=None, required=()):
    return {'type':'object','properties':properties or {},'required':list(required),'additionalProperties':False}
S={'type':'string'}
SESSION={'session_id':S}
OBS=SESSION | {'observation_id':S}
XY={'x':{'type':'number','minimum':0},'y':{'type':'number','minimum':0}}
POINTER=XY | {'action':{'type':'string','enum':['move','click','wheel']}, 'button':{'type':'string','enum':['left','middle','right']},'delta_y':{'type':'number','minimum':-10000,'maximum':10000}}


def _tools():
    rows=[
      ('browser_start','Create a dedicated browser session. Playwright is headless with a fresh context. WebDriver uses the configured driver and capabilities.',True,{'browser':S,'width':{'type':'integer','minimum':320,'maximum':2560},'height':{'type':'integer','minimum':240,'maximum':1600}},()),
      ('browser_start_navigate_observe','Start a browser session, navigate once and return fresh page controls in one request. A post-start failure retains its session ID for inspection without retry.',True,{'url':S,'browser':S,'width':{'type':'integer','minimum':320,'maximum':2560},'height':{'type':'integer','minimum':240,'maximum':1600}},('url',)),
      ('browser_list','List active sessions in this daemon.',False,{},()),
      ('browser_observe','Read visible page text and current observation-bound control handles. Refresh before using stale handles.',False,SESSION,('session_id',)),
      ('browser_navigate','Navigate a session. Has worker network access, including local networks.',True,SESSION|{'url':S},('session_id','url')),
      ('browser_navigate_observe','Navigate once and return a fresh page observation and control handles in the same request. Never retry uncertain navigation.',True,SESSION|{'url':S},('session_id','url')),
      ('browser_click','Click a current observed control once. Uncertain failures are never retried.',True,OBS|{'handle':S},('session_id','observation_id','handle')),
      ('browser_click_observe','Click one observed control once and return a fresh page observation in the same request. Never retry an uncertain click.',True,OBS|{'handle':S},('session_id','observation_id','handle')),
      ('browser_fill','Fill a current observed editable control once.',True,OBS|{'handle':S,'text':S},('session_id','observation_id','handle','text')),
      ('browser_fill_observe','Fill one observed editable control once and return a fresh page observation in the same request. Never retry uncertain input.',True,OBS|{'handle':S,'text':S},('session_id','observation_id','handle','text')),
      ('browser_pointer','Control the workspace pointer by CSS viewport coordinates, with a current observation.',True,OBS|POINTER,('session_id','observation_id','x','y')),
      ('browser_keys','Press a supported key or chord in the session; e.g. Enter, Tab, Control+A.',True,OBS|{'keys':S},('session_id','observation_id','keys')),
      ('browser_screenshot','Capture the viewport. Returns bounded base64 image data.',False,SESSION,('session_id',)),
      ('browser_close','Close and discard one browser session.',True,SESSION,('session_id',)),
      ('desktop_status','Report explicit desktop mode and whether input is shared.',False,{},()),
      ('window_list','List native app windows with short-lived opaque targets. Use the exact task window, never a desktop fallback.',False,{},()),
      ('window_open','Bind a live preview to one previously listed native window. resize_to_view authorizes resizing that exact app window to the preview pane. Does not activate it.',True,{'target_id':S,'resize_to_view':{'type':'boolean'}},('target_id',)),
      ('window_close','Forget one native preview binding. Does not close the app or its window.',True,SESSION,('session_id',)),
      ('desktop_screenshot','Capture the explicitly enabled host desktop.',False,{},()),
      ('desktop_pointer','Control the explicitly enabled host desktop cursor in logical input coordinates. Scale screenshot positions by input_scale_x/y from a fresh desktop_screenshot. Shared mode uses the owner cursor.',True,POINTER,('x','y')),
      ('desktop_keys','Press a key or chord on the explicitly enabled desktop.',True,{'keys':S},('keys',)),
      ('desktop_type','Type ASCII text on the explicitly enabled desktop.',True,{'text':S},('text',)),
      ('android_status','Query the owner-configured authorized ADB serial.',False,{},()),
      ('android_screenshot','Capture the owner-configured authorized Android device.',False,{},()),
      ('android_tap','Tap the owner-configured authorized Android device.',True,XY,('x','y')),
      ('android_input','Type simple ASCII text through authorized ADB. Shell metacharacters are rejected.',True,{'text':S},('text',)),
      ('android_key','Send an Android keycode name or integer through authorized ADB.',True,{'keycode':{'type':'string','pattern':'^(KEYCODE_[A-Z0-9_]+|[0-9]{1,3})$'}},('keycode',)),
      ('android_swipe','Swipe the owner-authorized Android device using native pixel coordinates.',True,
       {k:{'type':'integer','minimum':0,'maximum':10000} for k in ('start_x','start_y','end_x','end_y')}|
       {'duration_ms':{'type':'integer','minimum':50,'maximum':10000}},('start_x','start_y','end_x','end_y')),
      ('android_long_press','Press and hold one point on the owner-authorized Android device.',True,
       XY|{'duration_ms':{'type':'integer','minimum':300,'maximum':10000}},('x','y')),
      ('android_launch_app','Launch an explicit Android package/activity on the owner-authorized device. Does not reset app data or grant permissions.',True,
       {'package':{'type':'string','pattern':r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$'},
        'activity':{'type':'string','pattern':r'^\.?[A-Za-z_][A-Za-z0-9_.]*$'}},('package','activity')),
    ]
    return [{'name':'rdc_'+n,'description':d,'inputSchema':_schema(p,r),'x-rdc-mutating':m,
             'annotations':{'readOnlyHint':not m,'destructiveHint':m,'idempotentHint':not m,'openWorldHint':True}}
            for n,d,m,p,r in rows]


def _validate(schema,args):
    if not isinstance(args,dict): raise RDCError('invalid_arguments','Arguments must be an object')
    unknown=set(args)-set(schema['properties'])
    if unknown: raise RDCError('invalid_arguments','Unknown arguments: '+', '.join(sorted(unknown)))
    for name in schema['required']:
        if name not in args: raise RDCError('invalid_arguments',f'Missing argument: {name}')
    for name,value in args.items():
        p=schema['properties'][name]; t=p['type']
        good = isinstance(value,str) if t=='string' else type(value) is bool if t=='boolean' else type(value) is int if t=='integer' else type(value) in (int,float) and math.isfinite(value)
        if not good: raise RDCError('invalid_arguments',f'Invalid {name} type')
        if isinstance(value,str) and len(value)>32000: raise RDCError('invalid_arguments',f'{name} exceeds 32000 characters')
        if 'enum' in p and value not in p['enum']: raise RDCError('invalid_arguments',f'Invalid {name}')
        if 'minimum' in p and value<p['minimum'] or 'maximum' in p and value>p['maximum']: raise RDCError('invalid_arguments',f'{name} out of bounds')
        if 'pattern' in p and not re.fullmatch(p['pattern'],value): raise RDCError('invalid_arguments',f'Invalid {name}')


class Adapters:
    """Serialize browsers on their owning thread, including calls from MCP workers."""
    def __init__(self,settings):
        self.settings=settings
        self._queue=queue.Queue(); self._thread=None; self._start_lock=threading.Lock()
        self._native_lock=threading.RLock(); self._closed=False
        self._browser_status_lock=threading.Lock()
        self._browser_status={**_Browsers(settings).status(),'busy':False,'status_stale':False,'updated_at':time.time()}
        self.mobile=Mobile(settings); self._adb_sensitive=False
        from .windows import Windows
        self.windows=Windows(settings)
        self._catalog={t['name']:t for t in [*_tools(),*self.mobile.catalog()]}
    def catalog(self): return list(self._catalog.values())
    def _browser(self,method,*args):
        with self._start_lock:
            if self._closed: raise RDCError('closed','Adapters are closed')
            if self._thread is None:
                self._thread=threading.Thread(target=self._run,name='rdc-browser-owner',daemon=True); self._thread.start()
            future=Future(); self._queue.put((future,method,args))
        return future.result()
    def _run(self):
        worker=_Browsers(self.settings)
        while True:
            future,method,args=self._queue.get()
            self._publish_browser_status(worker,busy=True)
            try:
                result=getattr(worker,method)(*args)
            except RDCError as exc:
                self._publish_browser_status(worker,busy=False)
                future.set_exception(exc)
            except Exception as exc:
                self._publish_browser_status(worker,busy=False)
                future.set_exception(_adapter_error(exc))
            else:
                self._publish_browser_status(worker,busy=False)
                future.set_result(result)
            if method=='close': return
    def _publish_browser_status(self,worker,busy):
        with self._browser_status_lock:
            self._browser_status=copy.deepcopy({**worker.status(),'busy':busy,'status_stale':busy,'updated_at':time.time()})
    def activity_status(self):
        # Never join the browser command queue to describe ongoing work.
        with self._browser_status_lock:
            browser=copy.deepcopy(self._browser_status)
        return {'browser':browser,'mobile':self.mobile.status(),'window':self.windows.status(),
                'desktop':self._desktop_status(),'android':{'configured':bool(self.settings.adb_serial)}}
    def call(self,name,args):
        descriptor=self._catalog.get(name)
        if descriptor is None: raise RDCError('unknown_tool',f'Unknown adapter tool: {name}')
        _validate(descriptor['inputSchema'],args)
        if name.startswith('rdc_browser_'): return self._browser('call',name.removeprefix('rdc_browser_'),args)
        if name.startswith('rdc_window_'):
            with self._native_lock:
                if self._closed: raise RDCError('closed','Adapters are closed')
                return getattr(self.windows,name.removeprefix('rdc_window_'))(**args)
        if name == 'rdc_mobile_list':
            if self._closed: raise RDCError('closed','Adapters are closed')
            return self.mobile.call(name,args)
        with self._native_lock:
            if self._closed: raise RDCError('closed','Adapters are closed')
            try:
                if name.startswith('rdc_mobile_'): return self.mobile.call(name,args)
                if name.startswith('rdc_desktop_'): return self._desktop(name.removeprefix('rdc_desktop_'),args)
                return self._android(name.removeprefix('rdc_android_'),args)
            except RDCError:raise
            except Exception as exc:raise _adapter_error(exc) from exc
    def status(self):
        browser=self._browser('status')
        return {'browser':browser,'desktop':self._desktop_status(),'android':{'configured':bool(self.settings.adb_serial),'serial':self.settings.adb_serial},'mobile':self.mobile.status()}
    def snapshot(self,session_id=None):
        if isinstance(session_id,str) and session_id.startswith('window-'):
            with self._native_lock:
                if self._closed: raise RDCError('closed','Adapters are closed')
                return self.windows.snapshot(session_id)
        if session_id in ('desktop','android-adb'):
            name='rdc_desktop_screenshot' if session_id=='desktop' else 'rdc_android_screenshot'
            return {**self.call(name,{}),'session_id':session_id}
        if isinstance(session_id,str) and session_id.startswith('mobile-'):
            with self._native_lock:
                if self._closed: raise RDCError('closed','Adapters are closed')
                return self.mobile.snapshot(session_id)
        return self._browser('snapshot',session_id)
    def credentials_validate(self,target):
        return self._browser('credentials_validate',target)
    def credentials_fill(self,target,expected_origin,deliver):
        return self._browser('credentials_fill',target,expected_origin,deliver)
    def close(self):
        future=None
        with self._start_lock:
            if self._closed: return
            self._closed=True
            if self._thread is not None:
                future=Future(); self._queue.put((future,'close',()))
        self.mobile.close()
        if future is not None:
            future.result();self._thread.join(timeout=5)
    def _desktop_status(self):
        mode=self.settings.desktop_mode
        return {'mode':mode,'available':mode!='disabled','independent_input':False,
                'owner_input_approval_required':mode!='disabled',
                'isolation':'Isolation is not verified by RDC. Each native input requires owner approval.' if mode=='isolated' else 'Uses the owner OS cursor; each native input requires owner approval.' if mode=='shared' else 'Disabled by owner configuration.'}
    def _desktop(self,action,args):
        if action=='status': return self._desktop_status()
        if self.settings.desktop_mode=='disabled': raise RDCError('adapter_disabled','Native desktop control is disabled. Owner must explicitly configure shared or isolated desktop mode.')
        try: import pyautogui as gui
        except Exception as exc: raise RDCError('adapter_unavailable','PyAutoGUI/display unavailable; install the desktop extra and grant OS screen/input permissions.') from exc
        if action=='screenshot':
                im=gui.screenshot(); original_width,original_height=im.size
                input_width,input_height=gui.size()
                im.thumbnail((2560,1600)); data=io.BytesIO();im.convert('RGB').save(data,format='JPEG',quality=70)
                return _image(data.getvalue(),'image/jpeg',width=im.width,height=im.height,mode=self.settings.desktop_mode,
                              source_width=original_width,source_height=original_height,input_width=input_width,input_height=input_height,
                              input_scale_x=input_width/im.width,input_scale_y=input_height/im.height,
                              coordinate_system='desktop logical input pixels')
        if action=='pointer':
            width,height=gui.size();x,y=args['x'],args['y']
            if x>=width or y>=height: raise RDCError('invalid_arguments','Pointer outside desktop')
            gui.moveTo(x,y)
            if args.get('action','click')=='click': gui.click(button=args.get('button','left'))
            elif args.get('action')=='wheel': gui.scroll(-int(args.get('delta_y',0)/100))
        elif action=='keys': gui.hotkey(*_key_parts(args['keys'],desktop=True))
        elif action=='type':
            text=args['text']
            if not text.isascii(): raise RDCError('invalid_arguments','Desktop typing currently supports ASCII; use the application clipboard/API for Unicode.')
            gui.write(text,interval=0.005)
        return {'mode':self.settings.desktop_mode,'performed':action}
    def _android(self,action,args):
        serial=self.settings.adb_serial
        if not serial: raise RDCError('adapter_disabled','No owner-configured authorized ADB serial. Pair and authorize the device first.')
        cmd=['adb','-s',serial]
        if action=='status': cmd+=['get-state']
        elif action=='screenshot': return self._android_snapshot(cmd,serial)
        elif action=='tap':
            if any(type(args[k]) is not int or args[k]>10000 for k in ('x','y')): raise RDCError('invalid_arguments','Android coordinates must be integers from 0 to 10000')
            cmd+=['shell','input','tap',str(args['x']),str(args['y'])]
        elif action=='input':
            if not re.fullmatch(r'[A-Za-z0-9 .,!?@_+:/=-]{0,4000}',args['text']): raise RDCError('invalid_arguments','ADB input accepts simple ASCII text without shell metacharacters')
            cmd+=['shell','input','text',args['text'].replace(' ','%s')]
        elif action=='key': cmd+=['shell','input','keyevent',args['keycode']]
        elif action=='swipe':
            cmd+=['shell','input','swipe',*(str(args[k]) for k in ('start_x','start_y','end_x','end_y')),str(args.get('duration_ms',400))]
        elif action=='long_press':
            if any(type(args[k]) is not int or args[k]>10000 for k in ('x','y')): raise RDCError('invalid_arguments','Android coordinates must be integers from 0 to 10000')
            cmd+=['shell','input','swipe',str(args['x']),str(args['y']),str(args['x']),str(args['y']),str(args.get('duration_ms',800))]
        elif action=='launch_app': cmd+=['shell','am','start','-n',args['package']+'/'+args['activity']]
        else: raise RDCError('unknown_tool','Unknown Android action')
        result=self._adb_run(cmd)
        if action=='status':
            state=result.stdout.decode(errors='replace').strip()
            state=state if state in ('device','offline','unknown','unauthorized') else 'unknown'
            return {'serial':serial,'performed':action,'state':state,'available':state=='device'}
        if action=='launch_app' and (b'Error:' in result.stdout or b'Error:' in result.stderr):
            raise RDCError('adapter_error','Android could not launch that activity. Verify the owner-selected app and inspect the device.')
        return {'serial':serial,'performed':action}

    @staticmethod
    def _adb_run(cmd):
        try: result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,check=False)
        except FileNotFoundError: raise RDCError('adapter_unavailable','adb executable is not installed') from None
        except subprocess.TimeoutExpired: raise RDCError('adapter_timeout','ADB timed out; mutation outcome may be uncertain. Inspect before repeating.') from None
        except Exception: raise RDCError('adapter_error','ADB failed. Inspect the device before repeating an input action.') from None
        if result.returncode: raise RDCError('adapter_error','ADB failed. Inspect the device before repeating an input action.')
        if len(result.stdout)>MAX_IMAGE_BYTES or len(result.stderr)>65536:
            raise RDCError('output_limit','ADB output exceeded the permitted limit')
        return result

    def _android_hierarchy(self,cmd):
        # Stream to the terminal device rather than leaving private XML on storage.
        # Devices without this dump route fail closed; no alternate capture follows.
        raw=self._adb_run(cmd+['shell','-tt','-n','uiautomator','dump','--verbose','/dev/tty']).stdout
        if len(raw)>MAX_XML_BYTES+1024: raise ValueError('Native hierarchy too large')
        text=raw.decode('utf-8')
        if '<!' in text or text.count('<hierarchy')!=1 or text.count('</hierarchy>')!=1:
            raise ValueError('Native hierarchy unavailable')
        start=text.index('<hierarchy');end=text.index('</hierarchy>')+len('</hierarchy>')
        tree=_native_tree(text[start:end],'Android')
        if tree['sensitive']: self._adb_sensitive=True
        return tree

    def _android_snapshot(self,cmd,serial):
        mobile_sessions=self.mobile.status()['sessions']
        if self._adb_sensitive or any(s.get('privacy_sensitive') for s in mobile_sessions):
            self._adb_sensitive=True
            raise RDCError('screenshot_redaction_required',MOBILE_MESSAGES['screenshot_redaction_required'])
        if mobile_sessions:
            # A second UiAutomation client may disrupt a running Appium driver.
            raise RDCError('screenshot_failed','Use the active native mobile session for screenshots. ADB hierarchy capture is disabled while Appium sessions are active.')
        try:
            before=self._android_hierarchy(cmd)
            if self._adb_sensitive:
                raise RDCError('screenshot_redaction_required',MOBILE_MESSAGES['screenshot_redaction_required'])
            raw=self._adb_run(cmd+['exec-out','screencap','-p']).stdout
            width,height=_png_dimensions(raw)
            after=self._android_hierarchy(cmd)
            if self._adb_sensitive:
                raise RDCError('screenshot_redaction_required',MOBILE_MESSAGES['screenshot_redaction_required'])
            if before['digest']!=after['digest']: raise ValueError('Native screen changed during capture')
        except RDCError as exc:
            if exc.code=='screenshot_redaction_required': raise
            raise RDCError('screenshot_failed',MOBILE_MESSAGES['screenshot_failed']) from None
        except Exception:
            raise RDCError('screenshot_failed',MOBILE_MESSAGES['screenshot_failed']) from None
        return _image(raw,'image/png',serial=serial,width=width,height=height,
                      input_width=width,input_height=height,input_scale_x=1,input_scale_y=1,
                      coordinate_system='Android display pixels')


def _adapter_error(exc):
    message=str(exc).splitlines()[0][:400] if str(exc) else type(exc).__name__
    if 'socket() failed' in str(exc) and 'Operation not permitted' in str(exc):
        message='Host sandbox denies browser socket access (socket() failed: Operation not permitted)'
    return RDCError('adapter_error',f'{type(exc).__name__}: {message}. Inspect state before repeating an input action.')


def _image(raw,mime,**metadata):
    if len(raw)>MAX_IMAGE_BYTES: raise RDCError('output_limit','Screenshot exceeds 8 MiB; reduce the viewport')
    signature=b'\x89PNG\r\n\x1a\n' if mime=='image/png' else b'\xff\xd8'
    if not raw.startswith(signature): raise RDCError('adapter_error','Adapter returned an invalid screenshot')
    return {'mime_type':mime,'data':base64.b64encode(raw).decode('ascii'),**metadata}


KEYS={'Enter':'\ue007','Tab':'\ue004','Escape':'\ue00c','Backspace':'\ue003','Delete':'\ue017','ArrowLeft':'\ue012','ArrowUp':'\ue013','ArrowRight':'\ue014','ArrowDown':'\ue015','Home':'\ue011','End':'\ue010','PageUp':'\ue00e','PageDown':'\ue00f','Control':'\ue009','Shift':'\ue008','Alt':'\ue00a','Meta':'\ue03d','Space':' '}

def _key_parts(keys,desktop=False):
    parts=keys.split('+')
    if len(parts)>4 or any(p not in KEYS and not (len(p)==1 and p.isascii() and p.isalnum()) for p in parts): raise RDCError('invalid_arguments','Unsupported key/chord')
    if desktop:
        aliases={'Control':'ctrl','Meta':'command','Escape':'esc','ArrowLeft':'left','ArrowRight':'right','ArrowUp':'up','ArrowDown':'down','Space':'space','PageUp':'pageup','PageDown':'pagedown'}
        return [aliases.get(p,p.lower()) for p in parts]
    return parts


class _Browsers:
    def __init__(self,settings): self.settings=settings;self.sessions={};self.playwright=None
    def status(self):
        return {'backend':self.settings.browser_backend,'available':self.settings.browser_backend=='playwright' or bool(getattr(self.settings,'webdriver_url',None)),
                'sessions':[self.info(s) for s in self.sessions.values()],
                'independent_input':self.settings.browser_backend=='playwright','isolation_notice':'Dedicated headless context' if self.settings.browser_backend=='playwright' else 'Driver-controlled browser windows may share or interfere with the owner desktop; provision a VM for isolation.','profile_isolation': 'fresh contexts' if self.settings.browser_backend=='playwright' else 'depends on configured driver',
                'persistence':'Browser sessions end when the daemon exits.'}
    def info(self,s):
        result={k:s[k] for k in ('session_id','backend','browser','url','width','height','observation_id','cursor')}|{'title':s.get('title','')}
        if s.get('setup_status'): result['setup_status']=s['setup_status']
        return result
    def credentials_validate(self,target):
        from .credentials import fail, origin
        s=self.sessions.get(target['session_id'])
        if s is None: fail('session_not_found')
        self.current(s,target['observation_id'])
        handle=s['handles'].get(target['password_handle'])
        if handle is None: fail('stale_observation')
        if s['backend']=='playwright':
            data=handle.evaluate('(e)=>{'+CREDENTIAL_VALIDATE_BODY+'}')
        else:
            endpoint=urllib.parse.urlsplit(self.settings.webdriver_url)
            if endpoint.scheme!='https' and not (endpoint.scheme=='http' and endpoint.hostname in ('127.0.0.1','localhost','::1')):
                fail('credential_transport_unsafe')
            data=self.wd(s,'POST','/execute/sync',{'script':'/* RDC_CREDENTIAL_VALIDATE */ const e=arguments[0];'+CREDENTIAL_VALIDATE_BODY,
                                                 'args':[{ELEMENT_KEY:handle}]})
        if not isinstance(data,dict) or data.get('valid') is not True: fail('credential_target_invalid')
        actual=origin(self.url(s))
        if origin(data.get('origin'))!=actual or origin(data.get('form_origin'))!=actual:
            fail('credential_origin_mismatch')
        return {'origin':actual}
    def credentials_fill(self,target,expected_origin,deliver):
        from .credentials import fail, MESSAGES
        try:
            if self.credentials_validate(target)['origin']!=expected_origin:
                fail('credential_origin_mismatch')
            s=self.sessions[target['session_id']]
            handle=s['handles'][target['password_handle']]
            def fill(secret):
                self.current(s,target['observation_id'])
                # Keep the document sensitive even if a fill response is lost.
                s['sensitive_document_id']=s['document_id']
                if s['backend']=='playwright': s['handles'].pop(target['password_handle'])
                self.invalidate(s)
                try:
                    if s['backend']=='playwright':
                        result=handle.evaluate('(e,v)=>{const expected=v.origin,doc=v.document_id,secret=v.password;'+CREDENTIAL_FILL_BODY+'}',
                                               {'origin':expected_origin,'document_id':s['document_id'],'password':secret})
                    else:
                        result=self.wd(s,'POST','/execute/sync',{'script':'/* RDC_CREDENTIAL_FILL */ const e=arguments[0],expected=arguments[1],doc=arguments[2],secret=arguments[3];'+CREDENTIAL_FILL_BODY,
                                                              'args':[{ELEMENT_KEY:handle},expected_origin,s['document_id'],secret]})
                    if result is not True: fail('credential_target_invalid')
                finally:
                    if s['backend']=='playwright': handle.dispose()
            deliver(fill)
            return {'session_id':s['session_id'],'filled':True}
        except Exception as exc:
            # Driver/Playwright exception text can contain evaluation arguments.
            # Preserve only our stable codes with fixed, non-secret messages.
            code=exc.code if isinstance(exc,RDCError) and exc.code in MESSAGES else 'credential_fill_failed'
            raise RDCError(code,MESSAGES[code]) from None
    def call(self,action,args):
        if action=='start': return self.start(args)
        if action=='start_navigate_observe':
            # Reject unsupported URLs before creating any browser process.
            url=args['url']
            scheme=urllib.parse.urlsplit(url).scheme.lower()
            if scheme not in ('http','https','data','about') or scheme=='about' and url!='about:blank':
                raise RDCError('invalid_arguments','Browser URL must use http, https, data, or about:blank')
            # This is one mutation for the cloud journal. Any failure after
            # startup preserves its exact session ID for readback; no replay.
            started=self.start({k:args[k] for k in ('browser','width','height') if k in args})
            session_id=started['session_id']
            try:
                self.call('navigate',{'session_id':session_id,'url':url})
            except Exception:
                return {'ok':False,'session_id':session_id,'failure_stage':'navigation',
                        'error_code':'navigation_failed','recover_with':'rdc_browser_list'}
            try:
                return {'ok':True,**self.observe(self.sessions[session_id])}
            except Exception:
                return {'ok':False,'session_id':session_id,'failure_stage':'observation',
                        'error_code':'observation_failed','recover_with':'rdc_browser_list'}
        if action=='list': return {'sessions':[self.info(s) for s in self.sessions.values()]}
        s=self.sessions.get(args['session_id'])
        if s is None: raise RDCError('session_not_found','Browser session does not exist in this daemon')
        if action!='close' and s.get('setup_status')=='cleanup_required':
            raise RDCError('webdriver_cleanup_required','This driver session did not finish setup. Close it before starting a replacement.')
        if action=='observe': return self.observe(s)
        if action in ('navigate_observe','click_observe','fill_observe'):
            # Execute the existing guarded mutation, then observe on the same
            # serialized browser-owner thread. A failed observation must never
            # dispatch the mutation again; the cloud request ID stays authoritative.
            self.call(action.removesuffix('_observe'), args)
            return self.observe(s)
        if action=='screenshot': return self.snapshot(s['session_id'])
        if action=='close':
            self.destroy(s);self.sessions.pop(s['session_id']);return {'session_id':s['session_id'],'closed':True}
        if action=='navigate':
            url=args['url'];scheme=urllib.parse.urlsplit(url).scheme.lower()
            if scheme not in ('http','https','data','about') or scheme=='about' and url!='about:blank': raise RDCError('invalid_arguments','Browser URL must use http, https, data, or about:blank')
            self.invalidate(s)
            # Navigation may replace the rendered source before the next pointer
            # command. A former page's cursor must not linger in the new page.
            s['cursor']={**s['cursor'],'visible':False}
            if s['backend']=='playwright': s['page'].goto(url,wait_until='domcontentloaded',timeout=30000)
            else: self.wd(s,'POST','/url',{'url':url})
            s['url']=self.url(s); return self.info(s)
        self.current(s,args['observation_id'])
        # Invalidate before sending any mutation: failures can have uncertain outcomes.
        handle=None
        if action in ('click','fill'):
            handle=s['handles'].get(args['handle'])
            if handle is None: raise RDCError('stale_observation','Unknown handle. Observe the page again.')
        if action=='pointer':
            if args['x']>=s['width'] or args['y']>=s['height']: raise RDCError('invalid_arguments','Pointer outside viewport')
            pointer_action=args.get('action','click')
            if pointer_action!='move': self.invalidate(s)
            if s['backend']=='playwright':
                mouse=s['page'].mouse;mouse.move(args['x'],args['y'])
                if pointer_action=='click':mouse.click(args['x'],args['y'],button=args.get('button','left'))
                elif pointer_action=='wheel':mouse.wheel(0,args.get('delta_y',0))
            else:
                if pointer_action=='wheel':
                    sequence={'type':'wheel','id':'rdc-wheel','actions':[{'type':'scroll','x':int(args['x']),'y':int(args['y']),'deltaX':0,'deltaY':int(args.get('delta_y',0)),'duration':0,'origin':'viewport'}]}
                else:
                    acts=[{'type':'pointerMove','duration':0,'origin':'viewport','x':int(args['x']),'y':int(args['y'])}]
                    if pointer_action=='click':
                        b={'left':0,'middle':1,'right':2}[args.get('button','left')];acts += [{'type':'pointerDown','button':b},{'type':'pointerUp','button':b}]
                    sequence={'type':'pointer','id':'rdc-pointer','parameters':{'pointerType':'mouse'},'actions':acts}
                self.wd(s,'POST','/actions',{'actions':[sequence]})
            # Only a successful source-bound pointer action produces a visible marker.
            s['cursor']={'x':args['x'],'y':args['y'],'visible':True}
        elif action=='keys':
            parts=_key_parts(args['keys']);self.invalidate(s)
            if s['backend']=='playwright': s['page'].keyboard.press(args['keys'])
            else:
                values=[KEYS.get(p,p) for p in parts]
                acts=[{'type':'keyDown','value':v} for v in values]+[{'type':'keyUp','value':v} for v in reversed(values)]
                self.wd(s,'POST','/actions',{'actions':[{'type':'key','id':'rdc-keyboard','actions':acts}]})
        elif action in ('click','fill'):
            if s['backend']=='playwright':
                # Keep the chosen live handle until its one action finishes.
                s['handles'].pop(args['handle'])
            self.invalidate(s)
            if s['backend']=='playwright':
                try:
                    if not handle.evaluate('(e)=>e.isConnected'): raise RDCError('stale_observation','Control detached. Observe again.')
                    if action=='click':
                        handle.scroll_into_view_if_needed(timeout=10000)
                        box = handle.bounding_box()
                        handle.click(timeout=10000)
                        if box:
                            s['cursor']={'x':box['x']+box['width']/2,'y':box['y']+box['height']/2,'visible':True}
                        else:
                            s['cursor']={**s['cursor'],'visible':False}
                    else: handle.fill(args['text'],timeout=10000)
                finally:handle.dispose()
            else:
                path='/element/'+urllib.parse.quote(handle,safe='')
                if action=='click':
                    self.wd(s,'POST',path+'/click',{})
                    # WebDriver does not return click coordinates. Suppress the
                    # earlier marker rather than drawing it at a stale position.
                    s['cursor']={**s['cursor'],'visible':False}
                else:
                    self.wd(s,'POST',path+'/clear',{})
                    self.wd(s,'POST',path+'/value',{'text':args['text'],'value':list(args['text'])})
        s['url']=self.url(s);return self.info(s)
    def start(self,args):
        if len(self.sessions)>=MAX_SESSIONS: raise RDCError('session_limit','At most 8 browser sessions may run; close an existing session')
        backend=self.settings.browser_backend
        if backend=='disabled': raise RDCError('adapter_disabled','Browser control is disabled by owner configuration')
        browser=args.get('browser') or ('chromium' if backend=='playwright' else (self.settings.webdriver_capabilities or {}).get('browserName',''))
        width,height=args.get('width',1280),args.get('height',800)
        s={'session_id':str(uuid.uuid4()),'backend':backend,'browser':browser,'url':'about:blank','width':width,'height':height,'observation_id':None,'cursor':{'x':0,'y':0,'visible':False},'handles':{}}
        if backend=='playwright':
            if browser not in ('chromium','firefox','webkit'): raise RDCError('invalid_arguments','Playwright supports chromium, firefox, webkit. Actual Safari requires owner-configured WebDriver.')
            try:
                if self.playwright is None:
                    from playwright.sync_api import sync_playwright
                    self.playwright=sync_playwright().start()
                launch_options={'headless':True}
                # Owner process environment only; never an agent tool argument.
                if browser=='chromium' and os.environ.get('RDC_CHROMIUM_EXECUTABLE'):
                    launch_options['executable_path']=os.environ['RDC_CHROMIUM_EXECUTABLE']
                instance=getattr(self.playwright,browser).launch(**launch_options)
                try:
                    context=instance.new_context(viewport={'width':width,'height':height},accept_downloads=False)
                    page=context.new_page();page.set_default_timeout(10000)
                except Exception:
                    instance.close();raise
                s.update(instance=instance,context=context,page=page)
            except ImportError as exc: raise RDCError('adapter_unavailable','Playwright is not installed. Install the browser extra and run playwright install.') from exc
        else:
            if not self.settings.webdriver_url: raise RDCError('adapter_disabled','Owner must configure webdriver_url and capabilities before starting WebDriver sessions')
            caps=dict(self.settings.webdriver_capabilities or {})
            if browser and caps.get('browserName') and browser!=caps['browserName']: raise RDCError('invalid_arguments','Browser must match owner-configured WebDriver browserName')
            value=self.http('POST','/session',{'capabilities':{'alwaysMatch':caps}})
            if not isinstance(value,dict) or not isinstance(value.get('sessionId'),str) or not value['sessionId']:
                raise RDCError('adapter_error','Driver did not return a W3C sessionId')
            s['driver_id']=value['sessionId']
            try:
                returned_caps=value.get('capabilities',{})
                if not isinstance(returned_caps,dict): raise RDCError('webdriver_error','Driver returned invalid session capabilities')
                s['browser']=returned_caps.get('browserName',browser) or 'configured-appium'
                self.wd(s,'POST','/timeouts',{'implicit':0,'pageLoad':30000,'script':10000})
                # Appium native contexts can reject window sizing; browser observation will
                # clearly report unsupported commands rather than claiming native iOS support.
                try:self.wd(s,'POST','/window/rect',{'width':width,'height':height})
                except RDCError:pass
            except Exception:
                # Creation has already succeeded. Release that exact session, or
                # retain it for an explicit close if the outcome is uncertain.
                try:self.destroy(s)
                except Exception:
                    s['setup_status']='cleanup_required'
                    self.sessions[s['session_id']]=s
                    raise RDCError('webdriver_cleanup_required',
                        'Driver setup failed and cleanup could not be confirmed. List browser sessions and close the session marked cleanup_required.') from None
                raise
        self.sessions[s['session_id']]=s;return self.info(s)
    def url(self,s): return s['page'].url if s['backend']=='playwright' else self.wd(s,'GET','/url')
    def invalidate(self,s):
        if s['backend']=='playwright':
            for handle in s['handles'].values():
                try:handle.dispose()
                except Exception:pass
        s['observation_id']=None;s['handles']={}
    def current(self,s,observation):
        if not observation or observation!=s['observation_id']: raise RDCError('stale_observation','Observation is stale. Observe the page before acting.')
        doc=s['page'].evaluate('()=>window.__rdcDocumentId') if s['backend']=='playwright' else self.wd(s,'POST','/execute/sync',{'script':DOCUMENT_SCRIPT,'args':[]})
        if doc!=s['document_id'] or self.url(s)!=s['url']:
            self.invalidate(s);raise RDCError('stale_observation','Page navigated. Observe again.')
    def observe(self,s):
        self.invalidate(s)
        try:
            if s['backend']=='playwright':
                page=s['page'];collections=[];pending={}
                try:
                    # Filter and bound inside the page before creating remote
                    # handles. Only the selected controls cross this boundary.
                    root=page.evaluate_handle(PLAYWRIGHT_OBSERVE_SCRIPT);collections.append(root)
                    metadata=root.get_property('data');collections.append(metadata)
                    data=metadata.json_value()
                    elements=root.get_property('elements');collections.append(elements)
                    pending=elements.get_properties();controls=[]
                    for index,item in enumerate(data.get('controls',[])[:150]):
                        element=pending.get(str(index))
                        if element is None:continue
                        live=element.as_element()
                        if live is None:continue
                        handle=str(len(controls)+1);s['handles'][handle]=live
                        pending.pop(str(index));controls.append(dict(item)|{'handle':handle})
                finally:
                    for handle in [*pending.values(),*reversed(collections)]:
                        try:handle.dispose()
                        except Exception:pass
                title=page.title()
            else:
                data=self.wd(s,'POST','/execute/sync',{'script':OBSERVE_SCRIPT,'args':[]});controls=[]
                for item in data.get('controls',[])[:150]:
                    item=dict(item);element=item.pop('element',{});eid=element.get(ELEMENT_KEY)
                    if not eid:continue
                    handle=str(len(controls)+1);s['handles'][handle]=eid;controls.append(item|{'handle':handle})
                title=self.wd(s,'GET','/title')
            s['document_id']=data['document_id']
            s.update(url=self.url(s),title=str(title)[:1000],width=data['width'],height=data['height'],observation_id=str(uuid.uuid4()))
            text=str(data.get('text',''))
            return self.info(s)|{'title':str(title)[:1000],'text':text[:24000],'controls':controls,
                'text_truncated':bool(data.get('text_truncated') or len(text)>24000),
                'controls_truncated':bool(data.get('controls_truncated') or len(controls)<len(data.get('controls',[]))),
                'control_scan_truncated':bool(data.get('control_scan_truncated'))}
        except Exception:
            self.invalidate(s)
            raise RDCError('observation_failed','Browser observation failed. No page content was returned; observe the current document again.') from None
    def snapshot(self,session_id=None):
        if session_id is None: session_id=next(iter(self.sessions),None)
        s=self.sessions.get(session_id)
        if s is None: raise RDCError('session_not_found','No active browser session. Start a session first.')
        if s.get('setup_status')=='cleanup_required':
            raise RDCError('webdriver_cleanup_required','This driver session did not finish setup. Close it before starting a replacement.')
        try:
            sensitive=False
            if s.get('sensitive_document_id'):
                privacy=(s['page'].evaluate('()=>{'+SENSITIVE_DOCUMENT_SCRIPT+'}') if s['backend']=='playwright' else
                         self.wd(s,'POST','/execute/sync',{'script':SENSITIVE_DOCUMENT_SCRIPT,'args':[]}))
                if (not isinstance(privacy,dict) or not isinstance(privacy.get('document_id'),str) or
                        not privacy['document_id'] or type(privacy.get('sensitive')) is not bool):
                    raise ValueError('Sensitive document state could not be verified')
                sensitive=privacy['document_id']==s['sensitive_document_id'] or privacy['sensitive']
            if s['backend']=='playwright':
                # A preview may follow a Show Password toggle and marker removal
                # before any new observation. Mask every input in this sensitive
                # document, independently of its current type or marker.
                selector=('input,' if sensitive else '')+SENSITIVE_SELECTOR
                raw=s['page'].screenshot(type='jpeg',quality=70,timeout=10000,
                    mask=[s['page'].locator(selector)],mask_color='#000000');mime='image/jpeg'
            else:
                if sensitive:
                    raise RDCError('screenshot_redaction_required',
                        'This WebDriver document received a private credential. Safe screenshot masking is unavailable; navigate to a fresh document or use Playwright.')
                encoded=self.wd(s,'GET','/screenshot')
                if len(encoded)>MAX_IMAGE_BYTES*1.4: raise RDCError('output_limit','Screenshot exceeds 8 MiB')
                raw=base64.b64decode(encoded,validate=True);mime='image/png'
        except Exception as exc:
            if isinstance(exc,RDCError) and exc.code in ('screenshot_redaction_required','output_limit'):raise
            raise RDCError('screenshot_failed','Browser screenshot failed. No image was returned; safe masking could not be confirmed.') from None
        return _image(raw,mime,**self.info(s))
    def http(self,method,path,body=None):
        endpoint=self.settings.webdriver_url.rstrip('/')+path
        data=json.dumps(body).encode() if body is not None else None
        request=urllib.request.Request(endpoint,data=data,method=method,headers={'Content-Type':'application/json'})
        # Do not use ambient proxies or follow redirects to unrelated services.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        try:
            with opener.open(request,timeout=35) as response:
                raw=response.read(12*1024*1024+1)
                if len(raw)>12*1024*1024: raise RDCError('output_limit','Driver response exceeds 12 MiB')
        except urllib.error.HTTPError as exc:
            with exc: raw=exc.read(4096)
            try:message=json.loads(raw).get('value',{}).get('message','Driver request failed')
            except Exception:message='Driver request failed'
            raise RDCError('webdriver_error',str(message)[:1000]) from exc
        except (urllib.error.URLError,TimeoutError) as exc:raise RDCError('adapter_unavailable','WebDriver unavailable or timed out; inspect session before repeating a mutation.') from exc
        try:payload=json.loads(raw)
        except Exception as exc:raise RDCError('webdriver_error','Driver response is not JSON') from exc
        value=payload.get('value')
        if isinstance(value,dict) and value.get('error'): raise RDCError('webdriver_error',str(value.get('message',value['error']))[:1000])
        return value
    def wd(self,s,method,path,body=None):return self.http(method,'/session/'+urllib.parse.quote(s['driver_id'],safe='')+path,body)
    def destroy(self,s):
        self.invalidate(s)
        if s['backend']=='playwright':s['instance'].close()
        else:self.wd(s,'DELETE','')
    def close(self):
        for s in list(self.sessions.values()):
            try:self.destroy(s)
            except Exception:pass
        self.sessions.clear()
        if self.playwright:self.playwright.stop();self.playwright=None
