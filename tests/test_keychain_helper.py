"""Targeted native selection tests. No real credential store is ever opened."""
import importlib
import ctypes
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rdc.credentials import NativeProvider
from rdc.errors import RDCError

SECRET = b'RDC-synthetic-native-secret\n'
LOCATOR = {'version': 2, 'keychain': '/synthetic/selected.keychain-db',
           'server': 'example.test', 'account': 'synthetic-account'}


class NativeFixture:
    """Replace only the OS API boundary, preserving real selector decisions."""
    def __init__(self, count=1, **metadata):
        self.keychain, self.search_ref = object(), object()
        self.items = [object() for _ in range(count)]
        self.remaining = iter(self.items)
        self.info = {'server': 'example.test', 'account': 'synthetic-account',
                     'protocol': int.from_bytes(b'htps', 'big'), 'port': 443} | metadata
        self.reads, self.released, self.queries = [], [], []
        self.inspected = []
        self.opened, self.next_calls = [], 0

    def open(self, path):
        if path != '/synthetic/selected.keychain-db': raise AssertionError('Unexpected keychain')
        self.opened.append(path)
        return self.keychain

    def search(self, keychain, server, account):
        if keychain is not self.keychain: raise AssertionError('Default search list must never be used')
        self.queries.append((server, account))
        return self.search_ref

    def next(self, search):
        if search is not self.search_ref: raise AssertionError('Unexpected search')
        self.next_calls += 1
        return next(self.remaining, None)

    def metadata(self, item):
        self.inspected.append(item)
        return self.info

    def password(self, item):
        if item is not self.items[0]: raise AssertionError('A different native item was read')
        self.reads.append(item)
        return bytearray(SECRET)

    def release(self, reference): self.released.append(reference)


class TargetedKeychainTests(unittest.TestCase):
    def helper(self):
        try:
            return importlib.import_module('rdc._keychain_helper')
        except ImportError:
            self.fail('Targeted item-reference selection has not been implemented')

    def test_missing_or_ambiguous_selection_never_reads_a_secret(self):
        helper = self.helper()
        for count, code in ((0, 'credential_item_not_found'), (2, 'credential_item_ambiguous')):
            with self.subTest(count=count):
                fixture = NativeFixture(count)
                with self.assertRaises(helper.KeychainError) as caught:
                    helper.read_selected(LOCATOR, 'https://example.test', fixture)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(fixture.reads, [])
                self.assertEqual(fixture.queries, [('example.test', 'synthetic-account')])
                self.assertEqual(set(fixture.released), set([fixture.keychain, fixture.search_ref, *fixture.items]))

    def test_ambiguity_inspection_stops_after_two_matching_references(self):
        helper = self.helper()
        fixture = NativeFixture(3)
        with self.assertRaises(helper.KeychainError) as caught:
            helper.read_selected(LOCATOR, 'https://example.test', fixture)
        self.assertEqual(caught.exception.code, 'credential_item_ambiguous')
        self.assertEqual(fixture.next_calls, 2)
        self.assertEqual(fixture.inspected, [])
        self.assertEqual(fixture.reads, [])
        self.assertNotIn(fixture.items[2], fixture.released)

    def test_invalid_or_legacy_helper_input_never_opens_a_keychain(self):
        helper = self.helper()
        cases = [({'server': 'example.test', 'account': 'synthetic-account'}, 'https://example.test'),
                 (LOCATOR | {'keychain': '~/Library/Keychains/login.keychain-db'}, 'https://example.test'),
                 (LOCATOR | {'keychain': 'relative.keychain'}, 'https://example.test'),
                 (LOCATOR | {'account': ''}, 'https://example.test'),
                 (LOCATOR, 'http://example.test'), (LOCATOR, 'https://other.test'),
                 (LOCATOR, 'https://example.test/login')]
        for locator, origin in cases:
            with self.subTest(locator_keys=tuple(locator), origin=origin):
                fixture = NativeFixture()
                with self.assertRaises(helper.KeychainError):
                    helper.read_selected(locator, origin, fixture)
                self.assertEqual(fixture.opened, [])

    def test_wrong_native_origin_or_account_never_reads_a_secret(self):
        helper = self.helper()
        cases = [{'protocol': int.from_bytes(b'http', 'big')}, {'protocol': 0},
                 {'port': 8443}, {'server': 'other.test'}, {'account': 'other-account'},
                 {'port': '443'}, {'port': -1}]
        for metadata in cases:
            with self.subTest(metadata=metadata):
                fixture = NativeFixture(**metadata)
                with self.assertRaises(helper.KeychainError) as caught:
                    helper.read_selected(LOCATOR, 'https://example.test', fixture)
                self.assertEqual(caught.exception.code, 'credential_item_mismatch')
                self.assertEqual(fixture.reads, [])

    def test_password_is_read_from_same_unique_reference_with_exact_effective_port(self):
        helper = self.helper()
        for native_port, origin in ((0, 'https://example.test'), (443, 'https://example.test'),
                                    (8443, 'https://example.test:8443')):
            with self.subTest(native_port=native_port):
                fixture = NativeFixture(port=native_port)
                value = helper.read_selected(LOCATOR, origin, fixture)
                self.assertEqual(value, SECRET)
                self.assertEqual(fixture.inspected, [fixture.items[0]])
                self.assertEqual(fixture.reads, [fixture.items[0]])
        fixture = NativeFixture(port=0)
        with self.assertRaises(helper.KeychainError):
            helper.read_selected(LOCATOR, 'https://example.test:8443', fixture)
        self.assertEqual(fixture.reads, [])

    def test_helper_emits_no_diagnostics_and_clears_its_password_buffer(self):
        helper = self.helper()
        output = io.BytesIO()
        value = bytearray(SECRET)
        request = io.BytesIO(json.dumps({'locator': LOCATOR, 'origin': 'https://example.test'}).encode())
        with patch.object(helper, 'read_selected', return_value=value):
            self.assertEqual(helper.main(request, output), 0)
        self.assertEqual(output.getvalue(), SECRET)
        self.assertEqual(value, b'\0' * len(SECRET))
        output = io.BytesIO()
        request.seek(0)
        with patch.object(helper, 'read_selected', side_effect=RuntimeError(SECRET.decode())):
            self.assertNotEqual(helper.main(request, output), 0)
        self.assertEqual(output.getvalue(), b'')

    def test_parent_uses_private_isolated_helper_and_preserves_password_bytes(self):
        entry = {'provider': 'macos-keychain', 'locator': LOCATOR, 'origins': ['https://example.test:8443']}
        with patch('rdc.credentials.sys.platform', 'darwin'), patch('rdc.credentials.subprocess.run',
                return_value=SimpleNamespace(returncode=0, stdout=SECRET)) as run:
            value = NativeProvider().read(entry)
        self.assertEqual(value.text(), SECRET.decode())
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], [sys.executable, '-I'])
        self.assertEqual(Path(argv[2]).name, '_keychain_helper.py')
        self.assertNotIn(LOCATOR['keychain'], argv)
        payload = json.loads(run.call_args.kwargs['input'])
        self.assertEqual(payload, {'locator': LOCATOR, 'origin': 'https://example.test:8443'})
        self.assertEqual(run.call_args.kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs['timeout'], 90)
        value.clear()

    def test_helper_failures_are_fixed_and_legacy_provider_never_dispatches(self):
        helper = self.helper()
        entry = {'provider': 'macos-keychain', 'locator': LOCATOR, 'origins': ['https://example.test']}
        for status, code in helper.EXIT_ERRORS.items():
            with self.subTest(code=code), patch('rdc.credentials.sys.platform', 'darwin'), \
                    patch('rdc.credentials.subprocess.run', return_value=SimpleNamespace(returncode=status, stdout=SECRET)):
                with self.assertRaises(RDCError) as caught:
                    NativeProvider().read(entry)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn(SECRET.decode(), str(caught.exception))
        with patch('rdc.credentials.sys.platform', 'darwin'), patch('rdc.credentials.subprocess.run') as run:
            with self.assertRaises(RDCError) as caught:
                NativeProvider().read(entry | {'locator': {'server': 'example.test', 'account': 'synthetic-account'}})
            self.assertEqual(caught.exception.code, 'credential_reenrollment_required')
            self.assertFalse(run.called)

    def test_helper_timeout_is_redacted_without_retry(self):
        entry = {'provider': 'macos-keychain', 'locator': LOCATOR, 'origins': ['https://example.test']}
        failure = subprocess.TimeoutExpired('synthetic-helper', 90, output=SECRET, stderr=SECRET)
        with patch('rdc.credentials.sys.platform', 'darwin'), patch('rdc.credentials.subprocess.run', side_effect=failure) as run:
            with self.assertRaises(RDCError) as caught:
                NativeProvider().read(entry)
        self.assertEqual(caught.exception.code, 'credential_provider_timeout')
        self.assertNotIn(SECRET.decode(), str(caught.exception))
        self.assertEqual(run.call_count, 1)

    def test_isolated_helper_entrypoint_rejects_legacy_before_any_native_access(self):
        helper = self.helper()
        request = {'locator': {'server': 'example.test', 'account': 'synthetic-account'}, 'origin': 'https://example.test'}
        result = subprocess.run([sys.executable, '-I', str(Path(helper.__file__).resolve())],
            input=json.dumps(request).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, 26)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'')

    def test_native_binding_requests_metadata_without_data_and_zeroes_secret_before_free(self):
        helper = self.helper()
        retained, events, released = [], [], []
        hits = iter((303, None))

        class Function:
            def __init__(self, call): self.call = call
            def __call__(self, *args): return self.call(*args)

        def reference(output, value):
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.c_void_p(value)

        def open_keychain(path, output):
            self.assertEqual(path, b'/synthetic/selected.keychain-db')
            reference(output, 101)
            return 0

        def search(keychain, item_class, attributes, output):
            self.assertEqual(keychain.value, 101)
            self.assertEqual(item_class, int.from_bytes(b'inet', 'big'))
            selected = ctypes.cast(attributes, ctypes.POINTER(helper.AttributeList)).contents
            query = {selected.attr[i].tag: ctypes.string_at(selected.attr[i].data, selected.attr[i].length)
                     for i in range(selected.count)}
            self.assertEqual(query, {int.from_bytes(b'srvr', 'big'): b'example.test',
                                     int.from_bytes(b'acct', 'big'): b'synthetic-account'})
            reference(output, 202)
            return 0

        def next_item(search_ref, output):
            self.assertEqual(search_ref.value, 202)
            item = next(hits)
            if item is None: return -25300
            reference(output, item)
            return 0

        def copy(item, info, item_class, attribute_output, length, data_output):
            self.assertEqual(item.value, 303)
            if data_output is None:
                self.assertIsNone(length, 'Metadata inspection must not ask for secret data or its length')
                selected = ctypes.cast(info, ctypes.POINTER(helper.AttributeInfo)).contents
                self.assertEqual([selected.tag[i] for i in range(selected.count)],
                                 [int.from_bytes(t, 'big') for t in (b'srvr', b'acct', b'ptcl', b'port')])
                self.assertEqual([selected.format[i] for i in range(selected.count)], [0, 0, 2, 2])
                values = [ctypes.create_string_buffer(b'example.test'), ctypes.create_string_buffer(b'synthetic-account'),
                          ctypes.c_uint32(int.from_bytes(b'htps', 'big')), ctypes.c_uint32(443)]
                lengths = [12, 17, 4, 4]
                attributes = (helper.Attribute * 4)(*(helper.Attribute(selected.tag[i], lengths[i],
                    ctypes.cast(ctypes.pointer(values[i]), ctypes.c_void_p)) for i in range(4)))
                result = helper.AttributeList(4, attributes)
                retained.extend([*values, attributes, result])
                ctypes.cast(attribute_output, ctypes.POINTER(ctypes.POINTER(helper.AttributeList)))[0] = ctypes.pointer(result)
                events.append('metadata')
            else:
                self.assertIsNone(info)
                self.assertIsNone(attribute_output)
                password = ctypes.create_string_buffer(SECRET)
                retained.append(password)
                ctypes.cast(length, ctypes.POINTER(ctypes.c_uint32))[0] = len(SECRET)
                reference(data_output, ctypes.addressof(password))
                events.append('password')
            return 0

        def free(attributes, data):
            if data:
                self.assertEqual(ctypes.string_at(data, len(SECRET)), b'\0' * len(SECRET))
                events.append('secret-cleared')
            return 0

        security = SimpleNamespace(SecKeychainOpen=Function(open_keychain),
            SecKeychainSearchCreateFromAttributes=Function(search), SecKeychainSearchCopyNext=Function(next_item),
            SecKeychainItemCopyAttributesAndData=Function(copy), SecKeychainItemFreeAttributesAndData=Function(free))
        core = SimpleNamespace(CFRelease=Function(lambda item: released.append(item.value)))
        with patch.object(helper.sys, 'platform', 'darwin'), patch.object(helper.ctypes, 'CDLL',
                side_effect=lambda name: security if name.endswith('/Security') else core):
            value = helper.read_selected(LOCATOR, 'https://example.test')
        self.assertEqual(value, SECRET)
        self.assertEqual(events, ['metadata', 'password', 'secret-cleared'])
        self.assertEqual(set(released), {101, 202, 303})


if __name__ == '__main__': unittest.main()
