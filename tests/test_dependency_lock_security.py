"""Offline supply-chain regression for patched RDC cloud-gateway lockfile.

Checks only committed version constraints. npm audit remains the authoritative
online vulnerability assessment, and bundled reachability requires review.
"""
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parent.parent
MANIFEST=ROOT/"cloud-gateway/package.json"
LOCK=ROOT/"cloud-gateway/package-lock.json"

def semver(raw):
    match=re.match(r"^(\d+)\.(\d+)\.(\d+)(?:$|-)",str(raw))
    if not match:
        raise AssertionError(f"Unexpected package version syntax: {raw!r}")
    return tuple(map(int,match.groups()))

class DependencyLockSecurityTests(unittest.TestCase):
    def test_patched_high_risk_dependencies_are_pinned_and_resolved(self):
        manifest=json.loads(MANIFEST.read_text())
        lock=json.loads(LOCK.read_text())
        package_records=lock["packages"]
        minimum={
            "next":"16.4.6",
            "zod":"4.6.7",
            "react":"19.3.1",
            "react-dom":"19.3.1",
            "react-server-dom-webpack":"19.3.1",
            "sharp":"0.35.5",
            "baseline-browser-mapping":"2.11.0",
            "fast-uri":"3.1.9",
            "source-map-js":"1.2.2"
        }
        for name,threshold in minimum.items():
            candidates=[
                value["version"] for path,value in package_records.items()
                if (path=="node_modules/"+name or path.endswith("/node_modules/"+name))
                and value.get("version")
            ]
            self.assertTrue(candidates,f"Missing resolved lockfile entry for {name}")
            for version in candidates:
                self.assertGreaterEqual(semver(version),semver(threshold),
                    f"{name}@{version} is below pinned security floor {threshold}")

        self.assertEqual(manifest["dependencies"]["next"],"16.4.6")
        self.assertEqual(manifest["dependencies"]["zod"],"4.6.7")
        for name in ("react","react-dom"):
            self.assertEqual(manifest["dependencies"][name],"19.3.1")
        self.assertEqual(manifest["devDependencies"]["react-server-dom-webpack"],"19.3.1")
        self.assertEqual(manifest["overrides"]["miniflare"]["sharp"],"0.35.5")

    def test_lockfile_root_matches_dependency_manifest(self):
        manifest=json.loads(MANIFEST.read_text())
        lock=json.loads(LOCK.read_text())
        root=lock["packages"][""]
        for category in ("dependencies","devDependencies"):
            self.assertEqual(root.get(category),manifest.get(category),
                             f"{category} differs between package manifest and lockfile")
