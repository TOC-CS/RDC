"""Focused mobile installation and credential boundary regression."""
import json
from pathlib import Path
import tempfile
import unittest

from starlette.testclient import TestClient
from rdc.gateway_standalone import StandaloneGateway, create_app, initialize

class MobileInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "gateway"
        initialize(self.root)
        self.state = StandaloneGateway(self.root)
        self.client = TestClient(create_app(self.state))

    def tearDown(self):
        self.client.close()
        self.state.db.close()
        self.tmp.cleanup()

    def test_install_assets(self):
        page = self.client.get("/mobile/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("manifest.webmanifest", page.text)
        self.assertIn("Add to Home Screen", page.text)
        self.assertIn("script-src 'self'", page.headers["content-security-policy"])
        manifest = self.client.get("/mobile/manifest.webmanifest").json()
        self.assertEqual(manifest["start_url"], "/mobile/")
        self.assertEqual(manifest["scope"], "/mobile/")
        self.assertEqual(manifest["display"], "standalone")
        for icon in manifest["icons"]:
            self.assertEqual(self.client.get(icon["src"]).status_code, 200)
        self.assertEqual(self.client.get("/mobile/sw.js").status_code, 200)

    def test_disabled_by_default(self):
        self.assertEqual(self.client.post("/mobile/status").status_code, 401)
        self.assertEqual(self.client.post("/mobile/status", headers={"Authorization": "Bearer " + self.state.client_token}).status_code, 401)

    def test_mobile_token_is_read_only(self):
        from rdc.mobile_install import provision_mobile_token
        token_path = provision_mobile_token(self.root)
        self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            provision_mobile_token(self.root)
        header = {"Authorization": "Bearer " + token_path.read_text().strip()}
        self.assertEqual(self.client.post("/mobile/status", headers=header).status_code, 200)
        self.assertFalse(self.client.post("/mobile/status", headers=header).json()["online"])
        self.assertEqual(self.client.post("/v2/mcp", headers=header, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).status_code, 401)
        self.assertEqual(self.client.post("/mobile/status", headers={"Authorization": "Bearer " + self.state.device_token}).status_code, 401)
        token_path.unlink()
        self.assertEqual(self.client.post("/mobile/status", headers=header).status_code, 401)

    def test_profile_factory(self):
        from rdc.mobile_install import make_profile
        a = make_profile("iphone", "ios", "owner-iphone", "com.apple.Preferences")
        b = make_profile("android", "android", "owner-android", "com.android.settings", ".Settings")
        self.assertEqual(a["iphone"]["automationName"], "XCUITest")
        self.assertEqual(b["android"]["automationName"], "UiAutomator2")
        self.assertEqual(a["iphone"]["capabilities"]["appium:udid"], "owner-iphone")
        self.assertTrue(b["android"]["capabilities"]["appium:noReset"])
        with self.assertRaises(Exception):
            make_profile("bad", "ios", "", "com.apple.Preferences")

    def test_no_api_or_credentials_in_offline_cache(self):
        sw = self.client.get("/mobile/sw.js").text
        self.assertIn("request.method !== 'GET'", sw)
        self.assertNotIn("/mobile/status", sw)
        script = self.client.get("/mobile/app.js").text
        self.assertNotIn("localStorage", script)
        self.assertNotIn("sessionStorage", script)
        self.assertIn("credentials: 'omit'", script)
