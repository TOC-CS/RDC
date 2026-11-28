"""Bounded build-command tests. No signing, account access or device operations."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "native-mobile/ios/build-xcode.sh"


class XcodeBuildTests(unittest.TestCase):
    def run_build(self, mode="signed", provision=None, team="ABCDEFGHIJ", device="00001234-ABCD"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            developer = root / "Developer"
            binary = developer / "usr/bin/xcodebuild"
            binary.parent.mkdir(parents=True)
            log = root / "arguments.json"
            binary.write_text("#!/usr/bin/env python3\nimport json,os,sys\n"
                "if sys.argv[1:] == ['-checkFirstLaunchStatus']: sys.exit(0)\n"
                "open(os.environ['RDC_TEST_ARGUMENTS'],'w').write(json.dumps(sys.argv[1:]))\n"
                "sys.exit(42)\n")
            binary.chmod(0o700)
            env = dict(os.environ, DEVELOPER_DIR=str(developer),
                       RDC_APPLE_TEAM=team, RDC_IOS_DEVICE=device,
                       RDC_TEST_ARGUMENTS=str(log))
            env.pop("RDC_ALLOW_PROVISIONING", None)
            if provision is not None:
                env["RDC_ALLOW_PROVISIONING"] = provision
            # The generated Xcode project is ignored by Git. Keep this test
            # independent of local XcodeGen and the developer's real checkout.
            script = root / "build-xcode.sh"
            script.write_text(SCRIPT.read_text())
            project = root / "RDCMobile.xcodeproj"
            project.mkdir()
            (project / "project.pbxproj").write_text("// fixture")
            result = subprocess.run(["/bin/bash", str(script), mode, str(root / "output")],
                                    env=env, capture_output=True, text=True, timeout=15)
            return result, json.loads(log.read_text()) if log.exists() else None

    def test_automatic_provisioning_requires_explicit_opt_in(self):
        result, args = self.run_build(provision="1")
        self.assertEqual(result.returncode, 42)
        self.assertIn("-allowProvisioningUpdates", args)
        self.assertIn("-allowProvisioningDeviceRegistration", args)
        self.assertIn("platform=iOS,id=00001234-ABCD", args)
        self.assertIn("DEVELOPMENT_TEAM=ABCDEFGHIJ", args)

    def test_default_signed_build_does_not_contact_provisioning(self):
        result, args = self.run_build()
        self.assertEqual(result.returncode, 42)
        self.assertNotIn("-allowProvisioningUpdates", args)
        self.assertNotIn("-allowProvisioningDeviceRegistration", args)

    def test_invalid_provisioning_value_fails_before_build(self):
        result, args = self.run_build(provision="yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(args)

    def test_invalid_team_or_device_fails_before_build(self):
        result, args = self.run_build(team="invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(args)
        result, args = self.run_build(device="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(args)

    def test_unsigned_build_never_enables_provisioning(self):
        result, args = self.run_build(mode="unsigned", provision="1")
        self.assertEqual(result.returncode, 42)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", args)
        self.assertNotIn("-allowProvisioningUpdates", args)
        self.assertNotIn("-allowProvisioningDeviceRegistration", args)
