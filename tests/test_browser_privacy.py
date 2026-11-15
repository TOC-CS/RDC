"""Synthetic credential privacy and bounded browser-observation contracts."""
import base64
import io
import json
import os
import shutil
import subprocess
from types import SimpleNamespace
import unittest

from rdc import adapters
from rdc.errors import RDCError


SECRET = 'synthetic-private-value-8462'


def settings(backend='playwright'):
    return SimpleNamespace(browser_backend=backend, webdriver_url='http://127.0.0.1:4444',
                           webdriver_capabilities={'browserName': 'fixture'})


def session(page=None, backend='playwright'):
    return {'session_id': 'privacy-fixture', 'backend': backend, 'browser': 'fixture',
            'url': 'https://example.test/login', 'width': 800, 'height': 600,
            'observation_id': None, 'document_id': 'document-1', 'cursor': {'x': 0, 'y': 0},
            'handles': {}, 'page': page, 'driver_id': 'fixture'}


class Element:
    def __init__(self, index):
        self.index = index
        self.disposals = 0
    def is_visible(self): return True
    def evaluate(self, script):
        return {'tag': 'input', 'role': '', 'name': str(self.index), 'type': 'text', 'value': '', 'disabled': False}
    def as_element(self): return self
    def dispose(self): self.disposals += 1


class ValueHandle:
    def __init__(self, value):
        self.value = value
        self.disposals = 0
    def json_value(self): return self.value
    def get_properties(self): return self.value
    def get_property(self, name): return self.value[name]
    def dispose(self): self.disposals += 1


class BoundedPage:
    url = 'https://example.test/login'
    def __init__(self):
        self.acquired = []
        self.collections = []
    def title(self): return 'Bounded fixture'
    def evaluate(self, script):
        if '__rdcDocumentId' in script: return 'document-1'
        return {'text': 'x' * 24000, 'width': 800, 'height': 600}
    def acquire(self, count):
        created = [Element(i) for i in range(count)]
        self.acquired.extend(created)
        return created
    def query_selector_all(self, selector):
        return self.acquire(600)
    def evaluate_handle(self, script):
        # The script's traversal itself is exercised by the JavaScript tests.
        # This boundary models the bounded handle collection it exports.
        elements = self.acquire(150)
        data = ValueHandle({'document_id': 'document-1', 'text': 'x' * 24000,
                            'width': 800, 'height': 600, 'text_truncated': True,
                            'controls_truncated': True, 'control_scan_truncated': False,
                            'controls': [e.evaluate('') for e in elements]})
        array = ValueHandle({str(i): e for i, e in enumerate(elements)})
        root = ValueHandle({'data': data, 'elements': array})
        self.collections.extend([data, array, root])
        return root


class BrowserObservationContracts(unittest.TestCase):
    def test_large_page_does_not_acquire_unbounded_or_abandon_unused_handles(self):
        page = BoundedPage()
        browser = adapters._Browsers(settings())
        state = session(page)
        result = browser.observe(state)
        self.assertLessEqual(len(page.acquired), 150)
        self.assertEqual(len(result['controls']), 150)
        self.assertTrue(result['controls_truncated'])
        self.assertTrue(result['text_truncated'])
        self.assertTrue(all(h.disposals == 1 for h in page.collections))
        browser.invalidate(state)
        self.assertTrue(all(h.disposals == 1 for h in page.acquired))

    def test_unused_exported_handles_are_disposed_before_returning_observation(self):
        class Page(BoundedPage):
            def acquire(self, count):
                elements = super().acquire(count)
                elements[0].as_element = lambda: None
                return elements
        page = Page()
        browser = adapters._Browsers(settings())
        state = session(page)
        result = browser.observe(state)
        self.assertEqual(len(result['controls']), 149)
        self.assertEqual(page.acquired[0].disposals, 1)
        browser.invalidate(state)
        self.assertTrue(all(h.disposals == 1 for h in page.acquired))

    def test_failed_observation_disposes_its_handles_and_redacts_exception_text(self):
        page = BoundedPage()
        def private_title_failure(): raise RuntimeError(SECRET)
        page.title = private_title_failure
        browser = adapters._Browsers(settings())
        state = session(page)
        try:
            browser.observe(state)
        except Exception as exc:
            self.assertIsInstance(exc, RDCError)
            self.assertNotIn(SECRET, str(exc))
        else:
            self.fail('The failed observation must return an error')
        self.assertEqual(state['handles'], {})
        self.assertTrue(all(h.disposals == 1 for h in page.acquired))
        self.assertTrue(all(h.disposals == 1 for h in page.collections))

    def test_selected_action_handle_is_disposed_when_detached_or_validation_raises(self):
        for action in ('click', 'fill'):
            for mode in ('detached', 'exception'):
                with self.subTest(action=action, mode=mode):
                    selected, other = Element(0), Element(1)
                    def connected(script):
                        if mode == 'exception': raise RuntimeError('Synthetic detached handle')
                        return False
                    selected.evaluate = connected
                    actions = []
                    selected.click = lambda **kwargs: actions.append('click')
                    selected.fill = lambda *args, **kwargs: actions.append('fill')
                    browser = adapters._Browsers(settings())
                    state = session()
                    state.update(observation_id='observation-1', handles={'1': selected, '2': other})
                    browser.sessions[state['session_id']] = state
                    browser.current = lambda *args: None
                    with self.assertRaises(Exception):
                        browser.call(action, {'session_id': state['session_id'],
                            'observation_id': 'observation-1', 'handle': '1', 'text': 'ordinary input'})
                    self.assertEqual(selected.disposals, 1)
                    self.assertEqual(other.disposals, 1)
                    self.assertEqual(actions, [])
                    self.assertEqual(state['handles'], {})


class BrowserScreenshotContracts(unittest.TestCase):
    def test_playwright_uses_native_masks_for_password_and_previously_filled_fields(self):
        class Page:
            def locator(self, selector): return selector
            def screenshot(self, **kwargs):
                mask = ','.join(kwargs.get('mask', []))
                if 'password' in mask and 'data-rdc-private-field' in mask:
                    return b'\xff\xd8masked fixture'
                return b'\xff\xd8' + SECRET.encode()
        browser = adapters._Browsers(settings())
        state = session(Page())
        browser.sessions[state['session_id']] = state
        image = browser.snapshot(state['session_id'])
        self.assertNotIn(SECRET.encode(), base64.b64decode(image['data']))

    def test_direct_preview_after_marker_removal_and_reveal_remains_masked_without_observe(self):
        class Field(Element):
            type = 'password'
            marker = False
            value = ''
            def evaluate(self, script, values):
                self.value = values['password']
                self.marker = True
                return True
        field = Field(0)
        privacy = {'document_id': 'document-1', 'sensitive': True}
        masks = []
        class Page:
            def evaluate(self, script): return dict(privacy)
            def locator(self, selector): return selector
            def screenshot(self, **kwargs):
                selectors = set(','.join(kwargs.get('mask', [])).split(','))
                masks.append(selectors)
                covered = ('input' in selectors or
                           field.type == 'password' and 'input[type="password"]' in selectors or
                           field.marker and '[data-rdc-private-field]' in selectors)
                return b'\xff\xd8' + (b'masked' if covered else field.value.encode())
        browser = adapters._Browsers(settings())
        state = session(Page())
        state.update(observation_id='observation-1', handles={'1': field})
        browser.sessions[state['session_id']] = state
        browser.current = lambda *args: None
        browser.credentials_validate = lambda target: {'origin': 'https://example.test'}
        browser.credentials_fill({'session_id': state['session_id'], 'observation_id': 'observation-1',
                                  'password_handle': '1'}, 'https://example.test', lambda fill: fill(SECRET))
        field.marker = False
        field.type = 'text'
        browser.observe = lambda state: self.fail('Preview must protect the field without another observation')
        image = browser.snapshot(state['session_id'])
        self.assertNotIn(SECRET.encode(), base64.b64decode(image['data']))
        self.assertIn('input', masks[-1])
        privacy.update(document_id='fresh-document', sensitive=False)
        field.value = 'ordinary fresh-page input'
        browser.snapshot(state['session_id'])
        self.assertNotIn('input', masks[-1], 'Broad masking belongs only to a sensitive document')

    def test_sensitive_document_probe_failure_does_not_capture_or_leak_error(self):
        captures = []
        class Page:
            def evaluate(self, script): raise RuntimeError(SECRET)
            def locator(self, selector): return selector
            def screenshot(self, **kwargs):
                captures.append(True)
                return b'\xff\xd8fixture'
        browser = adapters._Browsers(settings())
        state = session(Page())
        state['sensitive_document_id'] = state['document_id']
        browser.sessions[state['session_id']] = state
        with self.assertRaises(RDCError) as error:
            browser.snapshot(state['session_id'])
        self.assertNotIn(SECRET, str(error.exception))
        self.assertEqual(captures, [])

    def test_screenshot_mask_failure_returns_no_image_or_private_exception(self):
        class Page:
            def locator(self, selector): return selector
            def screenshot(self, **kwargs): raise RuntimeError(SECRET)
        browser = adapters._Browsers(settings())
        state = session(Page())
        browser.sessions[state['session_id']] = state
        try:
            browser.snapshot(state['session_id'])
        except Exception as exc:
            self.assertIsInstance(exc, RDCError)
            self.assertNotIn(SECRET, str(exc))
        else:
            self.fail('A failed native mask must not fall back to an unmasked image')

    def test_webdriver_sensitive_document_fails_closed_until_fresh_document(self):
        browser = adapters._Browsers(settings('webdriver'))
        state = session(backend='webdriver')
        state.update(observation_id='observation-1', handles={'1': 'password-element'})
        browser.sessions[state['session_id']] = state
        browser.current = lambda *args: None
        browser.credentials_validate = lambda target: {'origin': 'https://example.test'}
        screenshots = []
        privacy = {'document_id': 'document-1', 'sensitive': True}
        def driver(state, method, path, body=None):
            if path == '/screenshot':
                screenshots.append(True)
                return base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
            if path == '/execute/sync':
                return True if 'RDC_CREDENTIAL_FILL' in body['script'] else dict(privacy)
            raise AssertionError((method, path))
        browser.wd = driver
        browser.credentials_fill({'session_id': state['session_id'], 'observation_id': 'observation-1',
                                  'password_handle': '1'}, 'https://example.test', lambda fill: fill(SECRET))
        with self.assertRaises(RDCError) as error:
            browser.snapshot(state['session_id'])
        self.assertEqual(error.exception.code, 'screenshot_redaction_required')
        self.assertEqual(screenshots, [])
        privacy.update(document_id='document-2', sensitive=False)
        self.assertEqual(browser.snapshot(state['session_id'])['mime_type'], 'image/png')
        self.assertEqual(screenshots, [True])


NODE_FIXTURE = r"""
const fs=require('fs'), input=JSON.parse(fs.readFileSync(0,'utf8'));
global.window={__rdcDocumentId:'document-1'};
global.location={origin:'https://example.test',href:'https://example.test/login'};
global.Event=class {constructor(name){this.type=name}};
global.HTMLInputElement=class {};
Object.defineProperty(HTMLInputElement.prototype,'value',{get(){return this._value||''},set(v){this._value=v}});
const nodes=Array.from({length:input.count},(_,i)=>{
 const e=new HTMLInputElement();
 Object.assign(e,{id:String(i),tagName:'INPUT',type:i===0?'password':'text',name:'field-'+i,
  innerText:'',labels:[],isConnected:true,disabled:false,readOnly:false,form:null,attributes:{}});
 e.getClientRects=()=>[{width:100,height:20}];
 e.getAttribute=n=>e.attributes[n]??null;e.setAttribute=(n,v)=>e.attributes[n]=String(v);
 e.matches=()=>true;e.dispatchEvent=()=>true;return e;
});
global.NodeFilter={SHOW_ELEMENT:1};
global.document={body:{innerText:'x'.repeat(input.text_size)},documentElement:{},
 querySelectorAll:()=>nodes,createTreeWalker:()=>{let i=0;return {nextNode:()=>nodes[i++]||null}}};
for(const e of nodes)e.ownerDocument=document;
global.innerWidth=800;global.innerHeight=600;
global.getComputedStyle=e=>({display:'block',visibility:Number(e.id)<(input.hidden_count||0)?'hidden':'visible'});
if(input.fill){
 new Function('e','expected','doc','secret',input.fill)(nodes[0],location.origin,'document-1',input.secret);
 nodes[0].type='text';
 if(input.remove_marker)delete nodes[0].attributes['data-rdc-private-field'];
}
const result=new Function(input.observe)();
const plain=JSON.parse(JSON.stringify(result,(key,value)=>key==='element'?value.id:value));
process.stdout.write(JSON.stringify({result:plain,marked:nodes[0].getAttribute('data-rdc-private-field')!==null}));
"""


@unittest.skipUnless(shutil.which('node'), 'JavaScript fixture needs Node')
class BrowserScriptContracts(unittest.TestCase):
    def script(self, count=1, text_size=10, fill=True, hidden_count=0, remove_marker=False):
        result = subprocess.run([shutil.which('node'), '-e', NODE_FIXTURE], input=json.dumps({
            'count': count, 'text_size': text_size, 'fill': adapters.CREDENTIAL_FILL_BODY if fill else None,
            'hidden_count': hidden_count, 'remove_marker': remove_marker,
            'secret': SECRET, 'observe': adapters.OBSERVE_SCRIPT}), text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_show_password_toggle_cannot_expose_broker_value_in_observation(self):
        # A harmless DOM attribute refresh must not forget the filled element.
        result = self.script(remove_marker=True)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(result['result']['controls'][0]['type'], 'text')
        self.assertEqual(result['result']['controls'][0]['value'], '[redacted]')
        self.assertTrue(result['marked'])
        self.assertFalse(result['result']['controls_truncated'])
        self.assertFalse(result['result']['text_truncated'])

    def test_browser_script_reports_bounded_controls_and_text(self):
        result = self.script(count=600, text_size=25000, fill=False)['result']
        self.assertEqual(len(result['controls']), 150)
        self.assertTrue(result['controls_truncated'])
        self.assertEqual(len(result['text']), 24000)
        self.assertTrue(result['text_truncated'])

    def test_hidden_control_scan_stops_at_its_bound_and_reports_incomplete_coverage(self):
        result = self.script(count=600, hidden_count=400, fill=False)['result']
        self.assertEqual(result['controls'], [])
        self.assertTrue(result['controls_truncated'])
        self.assertTrue(result['control_scan_truncated'])


class RealBrowserPrivacyTests(unittest.TestCase):
    def test_show_password_observation_and_screenshot_remain_redacted(self):
        from unittest.mock import patch
        environment = {'RDC_CHROMIUM_EXECUTABLE': '/usr/bin/chromium'} if os.path.exists('/usr/bin/chromium') else {}
        browser = adapters._Browsers(settings())
        try:
            with patch.dict(os.environ, environment):
                try: info = browser.start({})
                except Exception as exc:
                    if 'socket() failed' in str(exc) and 'Operation not permitted' in str(exc):
                        self.skipTest('Host sandbox denies Chromium socket access')
                    if 'Executable doesn' in str(exc) or 'playwright install' in str(exc):
                        self.skipTest('Playwright browser runtime is unavailable')
                    raise
            state = browser.sessions[info['session_id']]
            page = state['page']
            page.route('https://example.test/login', lambda route: route.fulfill(content_type='text/html', body='''
                <style>input {width:280px;height:40px;background:white;color:red}</style>
                <label>Password<input id="password" type="password"></label>
                <button onclick="const e=document.querySelector('#password');e.removeAttribute('data-rdc-private-field');e.type='text'">Show password</button>'''))
            page.goto('https://example.test/login')
            observed = browser.observe(state)
            field = next(c for c in observed['controls'] if c['type'] == 'password')
            browser.credentials_fill({'session_id': state['session_id'], 'observation_id': observed['observation_id'],
                'password_handle': field['handle']}, 'https://example.test', lambda fill: fill(SECRET))
            page.get_by_role('button', name='Show password').click()
            # Preview can be the very next call after the page changes. It must
            # not depend on observe restoring the field's screenshot marker.
            image = browser.snapshot(state['session_id'])
            from PIL import Image
            picture = Image.open(io.BytesIO(base64.b64decode(image['data']))).convert('RGB')
            box = page.locator('#password').bounding_box()
            crop = picture.crop((int(box['x'] + 8), int(box['y'] + 8),
                                 int(box['x'] + box['width'] - 8), int(box['y'] + box['height'] - 8)))
            self.assertLess(max(crop.tobytes()), 15, 'The revealed input must be covered by the native black mask')
            result = browser.observe(state)
            self.assertNotIn(SECRET, json.dumps(result))
            self.assertEqual(next(c for c in result['controls'] if c['tag'] == 'input')['value'], '[redacted]')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main()
