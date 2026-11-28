"""Bounded standalone packaging tests. No SDK downloads or signing changes."""
import importlib.util
import hashlib
from datetime import datetime,timezone,timedelta
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"native-mobile/ios/standalone.py"
spec=importlib.util.spec_from_file_location("standalone",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

DEVICE="00001234-ABCD"
CERT=b"test-certificate-fixture"
IDENTITY=hashlib.sha1(CERT).hexdigest()
TEAM="ABCDEFGHIJ"
NOW=datetime(2026,11,23,tzinfo=timezone.utc)

def profile():
    return {"ExpirationDate":NOW+timedelta(days=1),"ProvisionedDevices":[DEVICE],
            "Platform":["iOS"],"TeamIdentifier":[TEAM],"ApplicationIdentifierPrefix":[TEAM],
            "Entitlements":{"application-identifier":TEAM+"."+m.BUNDLE_ID,
                "com.apple.developer.team-identifier":TEAM,"get-task-allow":True,
                "com.apple.developer.networking.networkextension":["unwanted"]},
            "DeveloperCertificates":[CERT]}

class StandaloneTests(unittest.TestCase):
    def test_exact_profile_minimal_entitlements(self):
        result=m.validate_profile(profile(),DEVICE,IDENTITY,NOW)
        self.assertEqual(set(result),{"application-identifier","com.apple.developer.team-identifier","get-task-allow"})
        self.assertEqual(result["application-identifier"],TEAM+"."+m.BUNDLE_ID)

    def test_expired_or_wrong_device_certificate_and_bundle_rejected(self):
        for values in ({"ExpirationDate":NOW},{"ProvisionedDevices":["00005678-ABCD"]},
                       {"DeveloperCertificates":[b"other"]},{"Platform":["macOS"]},
                       {"Entitlements":{**profile()["Entitlements"],"application-identifier":TEAM+".*"}},
                       {"Entitlements":{**profile()["Entitlements"],"get-task-allow":False}}):
            with self.assertRaises(ValueError):
                m.validate_profile({**profile(),**values},DEVICE,IDENTITY,NOW)

    def test_xcode_and_missing_sdk_rejected(self):
        with self.assertRaises(ValueError):
            m.reject_xcode_path(Path("/Applications/Xcode.app/Contents/Developer"))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                m.validate_sdk(Path(temp))

    def test_wrong_platform_and_explicit_device_sdk(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            sdk=Path(temp)
            for framework in ("SwiftUI","Foundation"):
                (sdk/"System/Library/Frameworks"/(framework+".framework")).mkdir(parents=True)
            settings=sdk/"SDKSettings.json"
            settings.write_text(json.dumps({"CanonicalName":"iphonesimulator26.0"}))
            with self.assertRaises(ValueError):
                m.validate_sdk(sdk)
            settings.write_text(json.dumps({"CanonicalName":"iphoneos26.0"}))
            self.assertEqual(m.validate_sdk(sdk),sdk.resolve())

    def test_command_and_manifest_use_no_xcode_or_extra_entitlement(self):
        cmd=m.compile_command(Path("/owner/toolchain/swiftc"),Path("/owner/iPhoneOS.sdk"),Path("/tmp/RDCMobile"))
        self.assertEqual(cmd[0],"/owner/toolchain/swiftc")
        self.assertIn("arm64-apple-ios17.0",cmd)
        self.assertNotIn("xcodebuild"," ".join(cmd).lower())
        self.assertNotIn("NSAppTransportSecurity",m.bundle_info())
        self.assertEqual(m.bundle_info()["CFBundleIdentifier"],m.BUNDLE_ID)

    def test_output_cannot_replace_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"rdc.ipa"
            p.write_text("preserved")
            with self.assertRaises(ValueError):
                m.fresh_output(p,".ipa")
            self.assertEqual(p.read_text(),"preserved")

if __name__=="__main__":
    unittest.main()
