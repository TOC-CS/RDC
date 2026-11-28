import unittest
from unittest.mock import patch
from types import SimpleNamespace
from rdc.ios_developer_probe import primary_display_metadata
from rdc.ios_usb import interaction_preflight, _interaction_receipt
from rdc.mobile import Mobile
from rdc.mobile_install import make_profile
from rdc.errors import RDCError

UDID="00001234-ABCD"
DISPLAY={"primary":True,"external":False,"nativeSize":[1320.0,2868.0],
         "currentOrientation":"rot0","backlightState":"unknown","uniqueId":"PRIVATE"}

class InteractionPreflightTests(unittest.TestCase):
    def test_unique_primary_display_metadata_only(self):
        data=primary_display_metadata({"displays":[DISPLAY,{"primary":False,"external":True}]})
        self.assertEqual(data,{"native_width":1320,"native_height":2868,
                               "orientation":"rot0","backlight_state":"unknown"})
        self.assertNotIn("PRIVATE",str(data))

    def test_malformed_ambiguous_or_external_displays_fail_closed(self):
        for rows in [[DISPLAY,DISPLAY],[{**DISPLAY,"nativeSize":[float("nan"),2]}],
                     [{**DISPLAY,"external":True}],[{**DISPLAY,"nativeSize":[True,2868]}]]:
            self.assertEqual(primary_display_metadata({"displays":rows}),{})

    def test_service_presence_never_grants_input_or_capture(self):
        result=_interaction_receipt({"touch_service_advertised":True,"touch_transport_queried":True,
                 "hid_surface_count":7,"lock_state":"unlocked","native_input_permitted":True,
                 "screen_capture_permitted":True,"raw":"PRIVATE"})
        self.assertEqual(result["hid_surface_count"],7)
        self.assertFalse(result["native_input_permitted"])
        self.assertFalse(result["screen_capture_permitted"])
        self.assertFalse(result["native_input_verified"])
        self.assertNotIn("PRIVATE",str(result))

    def test_helper_privacy_and_unknown_lock(self):
        raw={"developer_status":"tunnel_verified","developer_mode":True,
             "developer_image_mounted":True,"remote_xpc_connected":True,"remote_service_count":82,
             "touch_service_advertised":True,"touch_transport_queried":True,"hid_surface_count":5,
             "native_width":1320,"native_height":2868,"orientation":"rot0",
             "lock_state":"unverified","address":"PRIVATE"}
        with patch("rdc.ios_usb.usb_check",return_value={"trust_accepted":True}),patch("rdc.ios_usb._pmd_python",return_value="/owner/python"),patch("rdc.ios_usb._safe_json_command",return_value=raw) as invoke:
            result=interaction_preflight(UDID)
            self.assertTrue(result["remote_xpc_connected"])
            self.assertEqual(result["lock_state"],"unknown")
            self.assertFalse(result["native_input_permitted"])
            self.assertNotIn("PRIVATE",str(result))
            self.assertEqual(invoke.call_args.args[0][-2:],[UDID,"interaction"])

    def test_worker_uses_exact_owner_profile(self):
        m=Mobile(SimpleNamespace(mobile_profiles=make_profile("iphone","ios",UDID,"com.apple.Preferences")))
        try:
            with patch("rdc.ios_usb.interaction_preflight",return_value={"native_input_permitted":False}) as probe:
                with self.assertRaises(RDCError):
                    m.call("rdc_mobile_ios_interaction_preflight",{"profile":"other"})
                self.assertFalse(m.call("rdc_mobile_ios_interaction_preflight",{"profile":"iphone"})["native_input_permitted"])
                probe.assert_called_once_with(UDID)
        finally: m.close()
