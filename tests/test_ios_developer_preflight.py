import unittest
from unittest.mock import patch
from rdc.ios_usb import developer_preflight

UDID="00001234-ABCD"
TRUST={"usb_connected":True,"device_service":True,"trust_accepted":True,"product_type":"iPhone18,2","ios_version":"26.6.1"}

class DeveloperPreflightTests(unittest.TestCase):
    def test_untrusted_never_opens_helper(self):
        with patch("rdc.ios_usb.usb_check",return_value={"trust_accepted":False}),patch("rdc.ios_usb._safe_json_command") as invoke:
            self.assertEqual(developer_preflight(UDID)["developer_status"],"trust_required")
            invoke.assert_not_called()

    def test_allowlisted_verified_receipt(self):
        payload={"developer_status":"tunnel_verified","developer_mode":True,
                 "developer_image_mounted":False,"remote_xpc_connected":True,
                 "remote_service_count":61,"application_service_advertised":False,
                 "instruments_service_advertised":True,"address":"PRIVATE",
                 "raw_services":{"secret":"PRIVATE"}}
        with patch("rdc.ios_usb.usb_check",return_value=TRUST),patch("rdc.ios_usb._pmd_python",return_value="/owner/python"),patch("rdc.ios_usb._safe_json_command",return_value=payload) as invoke:
            result=developer_preflight(UDID)
            self.assertTrue(result["remote_xpc_connected"])
            self.assertFalse(result["developer_image_mounted"])
            self.assertFalse(result["native_ui_verified"])
            self.assertNotIn("PRIVATE",str(result))
            self.assertEqual(invoke.call_args.args[0][-1],UDID)

    def test_malformed_or_unverified_tunnel_is_not_promoted(self):
        payload={"developer_status":"tunnel_verified","developer_mode":False,
                 "remote_xpc_connected":True,"remote_service_count":61}
        with patch("rdc.ios_usb.usb_check",return_value=TRUST),patch("rdc.ios_usb._pmd_python",return_value="/owner/python"),patch("rdc.ios_usb._safe_json_command",return_value=payload):
            result=developer_preflight(UDID)
            self.assertEqual(result["developer_status"],"unavailable")
            self.assertFalse(result["remote_xpc_connected"])
            self.assertNotIn("remote_service_count",result)
