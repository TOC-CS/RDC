"""Read-only iOS worker status, bounded typed fields and exact owner target."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import subprocess

from rdc.ios_usb import device_metrics
from rdc.mobile import Mobile
from rdc.errors import RDCError

UDID="00001234-ABCD"
PROFILES={"iphone":{"platformName":"iOS","automationName":"XCUITest","endpoint":"http://127.0.0.1:4723","capabilities":{"appium:udid":UDID}},
          "android":{"platformName":"Android","automationName":"UiAutomator2","endpoint":"http://127.0.0.1:4723","capabilities":{"appium:udid":"private-android"}}}
TRUST={"usb_connected":True,"device_service":True,"trust_accepted":True,"product_type":"iPhone18,2","ios_version":"26.6.1"}

class IOSStatus(unittest.TestCase):
    def test_selected_profile_and_readonly_catalog(self):
        m=Mobile(SimpleNamespace(mobile_profiles=PROFILES))
        try:
            descriptor=next(t for t in m.catalog() if t["name"]=="rdc_mobile_ios_status")
            self.assertTrue(descriptor["annotations"]["readOnlyHint"])
            with patch("rdc.ios_usb.device_metrics",return_value=TRUST) as check:
                self.assertEqual(m.call("rdc_mobile_ios_status",{"profile":"iphone"})["trust_accepted"],True)
                check.assert_called_once_with(UDID)
                for alias in ("android","unknown"):
                    with self.assertRaises(RDCError): m.call("rdc_mobile_ios_status",{"profile":alias})
        finally: m.close()

    def test_untrusted_no_command_execution(self):
        with patch("rdc.ios_usb.usb_check",return_value={"usb_connected":True,"trust_accepted":False}), patch("rdc.ios_usb.subprocess.run") as run:
            self.assertEqual(device_metrics(UDID)["metrics_status"],"trust_required")
            run.assert_not_called()

    def test_metrics_allowlist_and_exact_target(self):
        values=["256000000000","202082447360","246883446784","84","true","false"]
        responses=[subprocess.CompletedProcess([],0,x+"\n","") for x in values]
        with patch("rdc.ios_usb.usb_check",return_value=TRUST), patch("rdc.ios_usb._ideviceinfo",return_value="/opt/homebrew/bin/ideviceinfo"), patch("rdc.ios_usb.subprocess.run",side_effect=responses) as run:
            result=device_metrics(UDID)
            self.assertEqual(result["battery_percent"],84)
            self.assertEqual(result["storage_available_bytes"],202082447360)
            self.assertIs(result["developer_mode"],False)
            self.assertNotIn(UDID,str(result))
            self.assertEqual(run.call_count,6)
            for call in run.call_args_list:
                self.assertEqual(call.args[0][:3],["/opt/homebrew/bin/ideviceinfo","-u",UDID])
                self.assertFalse(call.kwargs.get("shell",False))

    def test_invalid_driver_output_redacted(self):
        responses=[subprocess.CompletedProcess([],0,"PRIVATE_DEVICE_DATA","PRIVATE_ERROR")]*6
        with patch("rdc.ios_usb.usb_check",return_value=TRUST), patch("rdc.ios_usb._ideviceinfo",return_value="/opt/homebrew/bin/ideviceinfo"), patch("rdc.ios_usb.subprocess.run",side_effect=responses):
            result=device_metrics(UDID)
            self.assertEqual(result["metrics_status"],"unavailable")
            self.assertNotIn("PRIVATE",str(result))

    def test_missing_library_reports_fixed_status(self):
        with patch("rdc.ios_usb.usb_check",return_value=TRUST),patch("rdc.ios_usb._ideviceinfo",return_value=None):
            self.assertEqual(device_metrics(UDID)["metrics_status"],"library_required")
