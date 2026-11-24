"""USB discovery boundary and owner-only profile selection fixtures."""
import plistlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from rdc.ios_usb import usb_check, write_profile, _choose_usb, _read_packet

class FakeSocket:
    def __init__(self, data): self.data=data
    def recv(self,n): data,self.data=self.data[:n],self.data[n:]; return data

class IosUsb(unittest.TestCase):
    def setUp(self):
        self.dev={"DeviceID":12,"Properties":{"ConnectionType":"USB","SerialNumber":"00001234-ABCD"}}
    def test_exact_selection(self):
        self.assertEqual(_choose_usb([self.dev],None),self.dev)
        self.assertIsNone(_choose_usb([self.dev,dict(self.dev,DeviceID=13)],None))
        self.assertIsNone(_choose_usb([self.dev],"wrong"))
        self.assertIsNone(_choose_usb([{"Properties":{"ConnectionType":"Network","SerialNumber":"00001234-ABCD"}}],None))
    def test_bounded_packet(self):
        self.assertEqual(_read_packet(FakeSocket(b"abc"),3),b"abc")
        with self.assertRaises(ValueError): _read_packet(FakeSocket(b""),2**22)
        with self.assertRaises(EOFError): _read_packet(FakeSocket(b"a"),2)
    def test_untrusted_fails_closed(self):
        with patch("rdc.ios_usb._devices",return_value=[self.dev]), patch("rdc.ios_usb._probe",return_value={"device_service":True,"trust_accepted":False}):
            result=usb_check()
            self.assertFalse(result["trust_accepted"])
            self.assertNotIn("serial",result)
            with tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(ValueError): write_profile(Path(temp)/"private.json","phone")
    def test_private_profile(self):
        with patch("rdc.ios_usb._devices",return_value=[self.dev]), patch("rdc.ios_usb._probe",return_value={"device_service":True,"trust_accepted":True}):
            result=usb_check()
            self.assertNotIn("serial",result)
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/"private.json"
                write_profile(path,"phone")
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
                self.assertIn("00001234-ABCD",path.read_text())
                with self.assertRaises(FileExistsError): write_profile(path,"phone")
    def test_transport_failure_sanitized(self):
        with patch("rdc.ios_usb._devices",side_effect=OSError("private serial or diagnostic")):
            status=usb_check()
            self.assertEqual(status,{"usb_connected":False,"device_service":False,"trust_accepted":False,"status":"unavailable"})
