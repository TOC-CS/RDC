import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rdc.config import Settings
from rdc.engine import Engine
from rdc.errors import RDCError
from rdc.ios_app import IOSAppLaunch,_dispatch
from rdc.mobile_install import make_profile

PROFILE=make_profile("iphone","ios","00001234-ABCD","com.apple.Preferences")
READY={"status":"ready","app_installed":True}
RUNNING={"status":"running_verified","launch_acknowledged":True,"process_running":True}
ON=SimpleNamespace(ios_coredevice_launch_enabled=True)

class IOSAppTests(unittest.TestCase):
    def test_default_disabled(self):
        with patch("rdc.ios_app._dispatch") as dispatch:
            with self.assertRaises(RDCError) as err: IOSAppLaunch(SimpleNamespace(),PROFILE).prepare("iphone")
            self.assertEqual(err.exception.code,"ios_app_launch_disabled")
            dispatch.assert_not_called()

    def test_invalid_profile_cannot_dispatch(self):
        with patch("rdc.ios_app._dispatch") as dispatch:
            with self.assertRaises(RDCError): IOSAppLaunch(ON,PROFILE).prepare("other")
            dispatch.assert_not_called()

    def test_token_single_use_and_exact_bundle(self):
        launch=IOSAppLaunch(ON,PROFILE)
        with patch("rdc.ios_app._dispatch",side_effect=[READY,RUNNING]) as dispatch:
            token=launch.prepare("iphone")["observation_id"]
            with self.assertRaises(RDCError): launch.launch("iphone","stale")
            result=launch.launch("iphone",token)
            self.assertTrue(result["process_running"])
            self.assertFalse(result["foreground_verified"])
            with self.assertRaises(RDCError): launch.launch("iphone",token)
            self.assertEqual(dispatch.call_count,2)
            self.assertEqual(dispatch.call_args.args,("00001234-ABCD","com.apple.Preferences","launch"))

    def test_unknown_never_replays(self):
        launch=IOSAppLaunch(ON,PROFILE)
        with patch("rdc.ios_app._dispatch",side_effect=[READY,{"status":"outcome_unknown"}]) as dispatch:
            token=launch.prepare("iphone")["observation_id"]
            with self.assertRaises(RDCError) as err: launch.launch("iphone",token)
            self.assertEqual(err.exception.code,"ios_app_outcome_unknown")
            with self.assertRaises(RDCError): launch.launch("iphone",token)
            self.assertEqual(dispatch.call_count,2)

    def test_receipt_privacy_and_inconsistent_confirmation(self):
        with patch("rdc.ios_app.usb_check",return_value={"trust_accepted":True}),patch("rdc.ios_app._pmd_python",return_value="/owner/python"),patch("rdc.ios_app._safe_json_command") as invoke:
            invoke.return_value={**RUNNING,"pid":12345,"raw":"PRIVATE"}
            result=_dispatch("00001234-ABCD","com.apple.Preferences","launch")
            self.assertEqual(result,RUNNING)
            invoke.return_value={**RUNNING,"process_running":False}
            self.assertEqual(_dispatch("00001234-ABCD","com.apple.Preferences","launch")["status"],"outcome_unknown")

    def test_engine_always_queues_owner_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            e=Engine(Settings(state_dir=root/"state",roots=[root],mobile_profiles=PROFILE,
                    ios_coredevice_launch_enabled=True,approval_mode="trusted",browser_backend="disabled"))
            try:
                with patch("rdc.ios_app._dispatch",side_effect=[READY,RUNNING]) as dispatch:
                    result=e.call("rdc_mobile_ios_app_prepare",{"profile":"iphone"})
                    req=e.call("rdc_mobile_ios_app_launch",{"profile":"iphone","observation_id":result["observation_id"]})
                    self.assertEqual(req["status"],"pending_approval")
                    self.assertEqual(dispatch.call_count,1)
                    self.assertTrue(e.decide(req["request_id"],True)["process_running"])
                    self.assertFalse(e.decide(req["request_id"],True)["ok"])
                    self.assertEqual(dispatch.call_count,2)
            finally:e.close()
