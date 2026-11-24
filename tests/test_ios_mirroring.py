"""Bounded Apple Mirroring menu route: no screenshot, text or generic input."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from rdc.errors import RDCError
from rdc.ios_mirroring import Mirroring
from rdc.config import Settings
from rdc.engine import Engine

WINDOW={"identity":(123,10,20,354,781,"fixture-start"),"actions":("home","app_switcher","spotlight")}
ON=SimpleNamespace(ios_mirroring_enabled=True,desktop_mode="shared")

class MirrorTests(unittest.TestCase):
    def test_default_disabled_and_desktop_grant(self):
        for settings in (SimpleNamespace(desktop_mode="shared"),
                         SimpleNamespace(ios_mirroring_enabled=True,desktop_mode="disabled")):
            with self.assertRaises(RDCError) as err: Mirroring(settings).observe()
            self.assertEqual(err.exception.code,"mirror_disabled")

    def test_observation_omits_private_window_identity(self):
        with patch("rdc.ios_mirroring._window",return_value=WINDOW):
            result=Mirroring(ON).observe()
            self.assertEqual(result["actions"],list(WINDOW["actions"]))
            self.assertFalse(result["phone_identity_verified"])
            self.assertFalse(result["screen_capture"])
            self.assertNotIn("identity",result)
            self.assertNotIn("fixture-start",str(result))

    def test_changed_window_never_dispatches(self):
        changed={**WINDOW,"identity":(123,10,20,354,781,"new-start")}
        m=Mirroring(ON)
        with patch("rdc.ios_mirroring._window",side_effect=[WINDOW,changed]),patch("rdc.ios_mirroring._script") as invoke:
            token=m.observe()["observation_id"]
            with self.assertRaises(RDCError): m.navigate(token,"home")
            with self.assertRaises(RDCError): m.navigate(token,"home")
            invoke.assert_not_called()

    def test_unknown_outcome_consumes_observation(self):
        m=Mirroring(ON)
        with patch("rdc.ios_mirroring._window",return_value=WINDOW),patch("rdc.ios_mirroring._script",return_value=None) as invoke:
            token=m.observe()["observation_id"]
            with self.assertRaises(RDCError) as err: m.navigate(token,"home")
            self.assertEqual(err.exception.code,"mirror_outcome_unknown")
            with self.assertRaises(RDCError): m.navigate(token,"home")
            invoke.assert_called_once()
            self.assertEqual(invoke.call_args.args[1],["123","10","20","354","781","Home Screen"])

    def test_trusted_worker_requires_owner_approval_and_single_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            e=Engine(Settings(state_dir=root/"state",roots=[root],desktop_mode="shared",
                        ios_mirroring_enabled=True,approval_mode="trusted",browser_backend="disabled"))
            try:
                with patch("rdc.ios_mirroring._window",return_value=WINDOW),patch("rdc.ios_mirroring._script",return_value="dispatched") as invoke:
                    obs=e.call("rdc_mobile_mirror_observe",{})
                    request=e.call("rdc_mobile_mirror_navigate",{"observation_id":obs["observation_id"],"action":"home"})
                    self.assertEqual(request["status"],"pending_approval")
                    invoke.assert_not_called()
                    outcome=e.decide(request["request_id"],True)
                    self.assertEqual(outcome["status"],"dispatched")
                    self.assertTrue(outcome["verification_required"])
                    self.assertFalse(e.decide(request["request_id"],True)["ok"])
                    invoke.assert_called_once()
            finally: e.close()
