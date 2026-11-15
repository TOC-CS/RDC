"""Private classic-Keychain helper; stdout is secret bytes on success only.

Run by NativeProvider with isolated Python, private stdin and a bounded timeout.
No default search list, vault enumeration, ACL changes or OS prompt automation.
Apple's classic APIs are deprecated; unavailable symbols fail closed. This is
not an Apple Passwords/iCloud provider. Platform qualification remains separate.

API contracts: SecKeychainSearchCreateFromAttributes / SecKeychainSearchCopyNext
return references, and SecKeychainItemCopyAttributesAndData with NULL data output
reads metadata only. The later data call uses the same retained item reference.
https://developer.apple.com/documentation/security/seckeychainsearchcreatefromattributes
https://developer.apple.com/documentation/security/seckeychainsearchcopynext
https://developer.apple.com/documentation/security/seckeychainitemcopyattributesanddata
"""
from __future__ import annotations

import ctypes
import json
import sys
from urllib.parse import urlsplit

MAX_REQUEST = 65536
MAX_SECRET = 65536
EXIT_ERRORS = {
    20: 'credential_item_not_found',
    21: 'credential_item_ambiguous',
    22: 'credential_item_mismatch',
    23: 'credential_provider_denied',
    24: 'credential_provider_unavailable',
    25: 'credential_provider_failed',
    26: 'credential_reenrollment_required',
}
ERROR_EXITS = {code: status for status, code in EXIT_ERRORS.items()}


class KeychainError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)  # Never attach native messages or locator values.


def _fail(code):
    raise KeychainError(code)


def validate_locator(locator, expected_origin):
    """Validate the private helper contract without opening a Keychain."""
    try:
        if isinstance(locator, dict) and set(locator) == {'server', 'account'}:
            _fail('credential_reenrollment_required')
        if (not isinstance(locator, dict) or set(locator) != {'version', 'keychain', 'server', 'account'}
                or type(locator['version']) is not int or locator['version'] != 2):
            raise ValueError
        for key in ('keychain', 'server', 'account'):
            value = locator[key]
            if (not isinstance(value, str) or not 0 < len(value) <= (4096 if key == 'keychain' else 1024)
                    or any(ord(c) < 32 for c in value)):
                raise ValueError
        if not locator['keychain'].startswith('/') or locator['keychain'].startswith('//'):
            raise ValueError
        if not isinstance(expected_origin, str) or any(ord(c) < 32 for c in expected_origin):
            raise ValueError
        parsed = urlsplit(expected_origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or parsed.hostname.lower().rstrip('.') != locator['server'].lower().rstrip('.')):
            raise ValueError
        port = parsed.port if parsed.port is not None else 443
        if not 1 <= port <= 65535:
            raise ValueError
        return parsed.hostname.lower().rstrip('.'), port
    except (ValueError, TypeError, KeyError, UnicodeError):
        _fail('credential_provider_failed')


def _fourcc(value):
    return int.from_bytes(value, 'big')


INTERNET_PASSWORD = _fourcc(b'inet')
HTTPS = _fourcc(b'htps')
SERVER, ACCOUNT, PROTOCOL, PORT = (_fourcc(tag) for tag in (b'srvr', b'acct', b'ptcl', b'port'))


class Attribute(ctypes.Structure):
    _fields_ = [('tag', ctypes.c_uint32), ('length', ctypes.c_uint32), ('data', ctypes.c_void_p)]


class AttributeList(ctypes.Structure):
    _fields_ = [('count', ctypes.c_uint32), ('attr', ctypes.POINTER(Attribute))]


class AttributeInfo(ctypes.Structure):
    _fields_ = [('count', ctypes.c_uint32), ('tag', ctypes.POINTER(ctypes.c_uint32)),
                ('format', ctypes.POINTER(ctypes.c_uint32))]


class NativeKeychain:
    """Small read-only binding to one explicitly opened file Keychain."""
    def __init__(self):
        if sys.platform != 'darwin':
            _fail('credential_provider_unavailable')
        try:
            self.security = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
            self.core = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
            pointer = ctypes.c_void_p
            out_pointer = ctypes.POINTER(pointer)
            signatures = {
                'SecKeychainOpen': [ctypes.c_char_p, out_pointer],
                'SecKeychainSearchCreateFromAttributes': [pointer, ctypes.c_uint32, ctypes.POINTER(AttributeList), out_pointer],
                'SecKeychainSearchCopyNext': [pointer, out_pointer],
                'SecKeychainItemCopyAttributesAndData': [pointer, ctypes.POINTER(AttributeInfo),
                    ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.POINTER(AttributeList)),
                    ctypes.POINTER(ctypes.c_uint32), out_pointer],
                'SecKeychainItemFreeAttributesAndData': [ctypes.POINTER(AttributeList), pointer],
            }
            for name, arguments in signatures.items():
                function = getattr(self.security, name)
                function.argtypes, function.restype = arguments, ctypes.c_int32
            self.core.CFRelease.argtypes, self.core.CFRelease.restype = [pointer], None
        except (OSError, AttributeError):
            _fail('credential_provider_unavailable')

    @staticmethod
    def _status(status):
        if status == -25300:  # errSecItemNotFound
            _fail('credential_item_not_found')
        if status:
            _fail('credential_provider_denied')

    def _reference(self, function, *arguments):
        result = ctypes.c_void_p()
        try:
            self._status(function(*arguments, ctypes.byref(result)))
            if not result:
                _fail('credential_provider_failed')
            return result
        except BaseException:
            if result:
                self.release(result)
            raise

    def open(self, path):
        return self._reference(self.security.SecKeychainOpen, path.encode('utf-8'))

    def search(self, keychain, server, account):
        values = [server.encode('utf-8'), account.encode('utf-8')]
        buffers = [ctypes.create_string_buffer(value) for value in values]
        attributes = (Attribute * 2)(*(Attribute(tag, len(value), ctypes.cast(buffer, ctypes.c_void_p))
            for tag, value, buffer in zip((SERVER, ACCOUNT), values, buffers)))
        query = AttributeList(2, attributes)
        return self._reference(self.security.SecKeychainSearchCreateFromAttributes,
                               keychain, INTERNET_PASSWORD, ctypes.byref(query))

    def next(self, search):
        item = ctypes.c_void_p()
        status = self.security.SecKeychainSearchCopyNext(search, ctypes.byref(item))
        if status:
            if item:
                self.release(item)
            if status == -25300:
                return None
            self._status(status)
        if not item:
            _fail('credential_provider_failed')
        return item

    def metadata(self, item):
        tags = (ctypes.c_uint32 * 4)(SERVER, ACCOUNT, PROTOCOL, PORT)
        # CSSM_DB_ATTRIBUTE_FORMAT_STRING=0; UINT32=2 (Apple cssmtype.h).
        formats = (ctypes.c_uint32 * 4)(0, 0, 2, 2)
        info = AttributeInfo(4, tags, formats)
        result = ctypes.POINTER(AttributeList)()
        try:
            # Both secret outputs are NULL: this call must never request data.
            self._status(self.security.SecKeychainItemCopyAttributesAndData(
                item, ctypes.byref(info), None, ctypes.byref(result), None, None))
            if not result or result.contents.count != 4 or not result.contents.attr:
                _fail('credential_item_mismatch')
            values = {}
            for index in range(result.contents.count):
                attribute = result.contents.attr[index]
                if attribute.tag in values or attribute.tag not in (SERVER, ACCOUNT, PROTOCOL, PORT) or not attribute.data:
                    _fail('credential_item_mismatch')
                if attribute.tag in (SERVER, ACCOUNT):
                    if not 0 < attribute.length <= 4096:
                        _fail('credential_item_mismatch')
                    values[attribute.tag] = ctypes.string_at(attribute.data, attribute.length).decode('utf-8')
                else:
                    if attribute.length != ctypes.sizeof(ctypes.c_uint32):
                        _fail('credential_item_mismatch')
                    values[attribute.tag] = ctypes.cast(attribute.data, ctypes.POINTER(ctypes.c_uint32)).contents.value
            return {'server': values[SERVER], 'account': values[ACCOUNT],
                    'protocol': values[PROTOCOL], 'port': values[PORT]}
        except (UnicodeError, KeyError):
            _fail('credential_item_mismatch')
        finally:
            if result:
                self.security.SecKeychainItemFreeAttributesAndData(result, None)

    def password(self, item):
        length, data = ctypes.c_uint32(), ctypes.c_void_p()
        try:
            self._status(self.security.SecKeychainItemCopyAttributesAndData(
                item, None, None, None, ctypes.byref(length), ctypes.byref(data)))
            if not data or not 0 < length.value <= MAX_SECRET:
                _fail('credential_provider_failed')
            return bytearray((ctypes.c_ubyte * length.value).from_address(data.value))
        finally:
            if data:
                if 0 < length.value <= MAX_SECRET:
                    ctypes.memset(data, 0, length.value)
                self.security.SecKeychainItemFreeAttributesAndData(None, data)

    def release(self, reference):
        self.core.CFRelease(reference)


def read_selected(locator, expected_origin, api=None):
    host, port = validate_locator(locator, expected_origin)
    api = api if api is not None else NativeKeychain()
    owned = []
    try:
        keychain = api.open(locator['keychain'])
        owned.append(keychain)
        search = api.search(keychain, locator['server'], locator['account'])
        owned.append(search)
        item = api.next(search)
        if item is None:
            _fail('credential_item_not_found')
        owned.append(item)
        other = api.next(search)
        if other is not None:
            owned.append(other)
            _fail('credential_item_ambiguous')
        metadata = api.metadata(item)
        native_port = metadata.get('port')
        if (metadata.get('server', '').lower().rstrip('.') != host or metadata.get('account') != locator['account']
                or metadata.get('protocol') != HTTPS or type(native_port) is not int
                or not 0 <= native_port <= 65535 or (443 if native_port == 0 else native_port) != port):
            _fail('credential_item_mismatch')
        # Never repeat a server/account lookup after selecting the unique item.
        return api.password(item)
    finally:
        for reference in reversed(owned):
            api.release(reference)


def main(input_stream=None, output_stream=None):
    input_stream = input_stream if input_stream is not None else sys.stdin.buffer
    output_stream = output_stream if output_stream is not None else sys.stdout.buffer
    value = None
    try:
        raw = input_stream.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            _fail('credential_provider_failed')
        request = json.loads(raw)
        if not isinstance(request, dict) or set(request) != {'locator', 'origin'}:
            _fail('credential_provider_failed')
        value = read_selected(request['locator'], request['origin'])
        if not isinstance(value, bytearray) or not 0 < len(value) <= MAX_SECRET:
            _fail('credential_provider_failed')
        if output_stream.write(value) != len(value):
            _fail('credential_provider_failed')
        output_stream.flush()
        return 0
    except KeychainError as exc:
        return ERROR_EXITS.get(exc.code, 25)
    except Exception:
        return 25
    finally:
        if isinstance(value, bytearray):
            value[:] = b'\0' * len(value)


if __name__ == '__main__':
    raise SystemExit(main())
