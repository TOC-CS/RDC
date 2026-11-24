import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json
import os
from rdc.android_usb import usb_check,write_profile
from rdc.mobile_install import make_profile
from rdc.config import Settings
from rdc.engine import Engine

USB="ABC1234 device usb:1-1 product:fixture model:Fixture transport_id:3\n"
UNTRUSTED="ABC1234 unauthorized usb:1-1 transport_id:3\n"
NET="192.168.1.10:5555 device product:fixture transport_id:9\nemulator-5554 device transport_id:10\n"

class AndroidUsbTests(unittest.TestCase):
    def test_excludes_network_and_emulator(self):
        with patch("rdc.android_usb._adb_binary",return_value="/owner/adb"),patch("rdc.android_usb._run",return_value=NET) as run:
            result=usb_check()
            self.assertEqual(result["status"],"no_unique_usb_device")
            self.assertFalse(result["trust_accepted"])
            run.assert_called_once()

    def test_unauthorized_never_queries_or_enables(self):
        with patch("rdc.android_usb._adb_binary",return_value="/owner/adb"),patch("rdc.android_usb._run",return_value=UNTRUSTED) as run:
            self.assertFalse(usb_check("ABC1234")["trust_accepted"])
            run.assert_called_once()

    def test_unique_usb_and_transport_privacy(self):
        with patch("rdc.android_usb._adb_binary",return_value="/owner/adb"),patch("rdc.android_usb._run",side_effect=[USB+NET,"device\n"]) as run:
            result=usb_check("ABC1234")
            self.assertEqual(result,{"status":"ready","usb_connected":True,"trust_accepted":True})
            self.assertEqual(run.call_args.args,("/owner/adb","-t","3","get-state"))

    def test_private_profile_requires_resolved_component(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"private.json"
            with patch("rdc.android_usb._adb_binary",return_value="/owner/adb"),patch("rdc.android_usb._run",side_effect=[USB,"device\n","com.android.settings/.Settings\n"]):
                write_profile(p,"android","com.android.settings",".Settings")
            fragment=json.loads(p.read_text())
            self.assertEqual(fragment["adb_serial"],"ABC1234")
            self.assertEqual(fragment["mobile_profiles"],make_profile("android","android","ABC1234","com.android.settings",".Settings"))
            if os.name=="posix": self.assertEqual(p.stat().st_mode&0o777,0o600)
            with patch("rdc.android_usb._adb_binary",return_value="/owner/adb"),patch("rdc.android_usb._run",side_effect=[USB,"device\n","No activity found\n"]):
                with self.assertRaises(ValueError): write_profile(Path(d)/"bad.json","android","com.android.settings",".Settings")
            self.assertFalse((Path(d)/"bad.json").exists())

    def test_engine_uses_configured_profile_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            e=Engine(Settings(state_dir=root/"state",roots=[root],browser_backend="disabled",
                mobile_profiles=make_profile("android","android","ABC1234","com.android.settings",".Settings")))
            try:
                with patch("rdc.android_usb.usb_check",return_value={"status":"ready","usb_connected":True,"trust_accepted":True}) as check:
                    self.assertFalse(e.call("rdc_mobile_android_usb_status",{"profile":"unknown"})["ok"])
                    self.assertTrue(e.call("rdc_mobile_android_usb_status",{"profile":"android"})["trust_accepted"])
                    check.assert_called_once_with("ABC1234")
            finally:e.close()
