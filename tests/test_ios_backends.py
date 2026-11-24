"""Backend selection remains private, exact-device, bounded and read-only."""
import unittest
from unittest.mock import patch
from rdc.ios_usb import preferred_device_metrics

UDID="00001234-ABCD"
TRUST={"usb_connected":True,"device_service":True,"trust_accepted":True,"product_type":"iPhone18,2","ios_version":"26.6.1"}
METRICS={"storage_total_bytes":256000000000,"storage_available_bytes":202000000000,"storage_data_capacity_bytes":246000000000,"battery_percent":84,"charging":True,"developer_mode":False}

class Backends(unittest.TestCase):
    def test_primary(self):
        with patch("rdc.ios_usb.usb_check",return_value=TRUST),patch("rdc.ios_usb._pmd_python",return_value="/private/python"),patch("rdc.ios_usb._safe_json_command",return_value={**METRICS,"serial":"PRIVATE"}) as cmd,patch("rdc.ios_usb.device_metrics") as fallback:
            result=preferred_device_metrics(UDID)
            self.assertEqual(result["backend"],"pymobiledevice3")
            self.assertEqual(result["metrics_status"],"complete")
            self.assertNotIn("serial",result)
            self.assertEqual(cmd.call_args.args[0][-1],UDID)
            fallback.assert_not_called()
    def test_fallback(self):
        with patch("rdc.ios_usb.usb_check",return_value=TRUST),patch("rdc.ios_usb._pmd_python",return_value=None),patch("rdc.ios_usb.device_metrics",return_value={**TRUST,**METRICS,"metrics_status":"complete"}) as fallback:
            self.assertEqual(preferred_device_metrics(UDID)["backend"],"libimobiledevice")
            fallback.assert_called_once_with(UDID)
    def test_go_identity_only(self):
        with patch("rdc.ios_usb.usb_check",return_value=TRUST),patch("rdc.ios_usb._go_ios_binary",return_value="/private/ios"),patch("rdc.ios_usb._safe_json_command",return_value={"ProductVersion":"26.6.1","ProductType":"iPhone18,2","SerialNumber":"PRIVATE"}) as cmd:
            result=preferred_device_metrics(UDID,"go-ios")
            self.assertEqual(result["metrics_status"],"identity_only")
            self.assertTrue(result["backend_verified"])
            self.assertNotIn("PRIVATE",str(result))
            self.assertEqual(cmd.call_args.args[0][-1],"--udid="+UDID)
    def test_untrusted_no_execution(self):
        with patch("rdc.ios_usb.usb_check",return_value={"trust_accepted":False}),patch("rdc.ios_usb._safe_json_command") as cmd:
            self.assertEqual(preferred_device_metrics(UDID)["metrics_status"],"trust_required")
            cmd.assert_not_called()
    def test_explicit_primary_does_not_fallback(self):
        with patch("rdc.ios_usb.usb_check",return_value=TRUST),patch("rdc.ios_usb._pmd_python",return_value="/private/python"),patch("rdc.ios_usb._safe_json_command",return_value={"battery_percent":101,"charging":1,"private":"secret"}),patch("rdc.ios_usb.device_metrics") as fallback:
            self.assertEqual(preferred_device_metrics(UDID,"pymobiledevice3")["metrics_status"],"unavailable")
            fallback.assert_not_called()
