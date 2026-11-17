#!/usr/bin/env python3
"""Isolated WebKit mobile viewer acceptance, no physical phone or Safari UI."""
import json
import os
from pathlib import Path
import select
import subprocess
import urllib.request
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
NODE = os.environ.get("PRESENTATION_NODE", "/opt/homebrew/opt/node@24/bin/node")
FIXTURE = ROOT / "scripts/isolated-webkit-fixture.mjs"
OUTPUT = ROOT / "evidence/headless-webkit-mobile.png"
CTRL = "webkit-browser-private-control-fixture"
VIEW = "webkit-browser-viewer-fixture"

def post(base, path, payload):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + CTRL,
            "Content-Type": "application/json"
        },
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.load(response)

def main():
    process = subprocess.Popen(
        [NODE, str(FIXTURE)], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    try:
        ready, _, _ = select.select([process.stdout], [], [], 5)
        if not ready:
            raise RuntimeError("Isolated WebKit fixture did not open a local port")
        row = process.stdout.readline()
        port = json.loads(row)["port"]
        base = "http://127.0.0.1:" + str(port)
        with sync_playwright() as playwright:
            browser = playwright.webkit.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    device_scale_factor=2, is_mobile=True,
                    has_touch=True, reduced_motion="reduce",
                )
                page = context.new_page()
                page.goto(base + "/v1/viewer?key=" + VIEW,
                          wait_until="domcontentloaded", timeout=8000)
                page.wait_for_function(
                    "() => document.body.dataset.connection==='connected' && "
                    "document.querySelector('.slide:not([hidden]) h1')?.textContent==='WebKit Opening'",
                    timeout=5000,
                )
                initial = page.evaluate("""() => ({
                    width: innerWidth,
                    documentWidth: document.documentElement.scrollWidth,
                    activeTitle: document.querySelector('.slide:not([hidden]) h1').textContent,
                    status: document.getElementById('session-status').textContent,
                    connection: document.body.dataset.connection,
                    navigationHidden: document.getElementById('next').hidden
                })""")
                if initial["documentWidth"] > initial["width"] + 2:
                    raise AssertionError("WebKit viewer horizontally overflows mobile viewport")
                if not initial["navigationHidden"]:
                    raise AssertionError("Live WebKit viewer exposes operator navigation controls")
                # Local viewer commands must never desynchronize physical output.
                page.evaluate("document.getElementById('next').click()")
                if page.locator(".slide:not([hidden]) h1").inner_text() != "WebKit Opening":
                    raise AssertionError("Live WebKit viewer accepted a local non-owner command")
                advanced = post(base, "/v1/command", {"action": "next"})
                if not advanced.get("changed"):
                    raise AssertionError("Controller declined independent slide change")
                page.wait_for_function(
                    "() => document.querySelector('.slide:not([hidden]) h1')?.textContent==='WebKit Updated'",
                    timeout=5000,
                )
                final = page.evaluate("""() => ({
                    width: innerWidth,
                    documentWidth: document.documentElement.scrollWidth,
                    activeTitle: document.querySelector('.slide:not([hidden]) h1').textContent,
                    status: document.getElementById('session-status').textContent
                })""")
                if final["documentWidth"] > final["width"] + 2:
                    raise AssertionError("WebKit changed slide overflows viewport")
                OUTPUT.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(OUTPUT), full_page=True)
                # Unload must clear confidential rendered text in this independent browser.
                post(base, "/v1/stop", {})
                post(base, "/v1/unload", {})
                page.wait_for_function(
                    "() => document.getElementById('session-status')?.textContent==='PRESENTATION CLEARED'",
                    timeout=5000,
                )
                cleared = page.evaluate(
                    "() => ({text: document.querySelector('main')?.textContent??'', "
                    "status: document.getElementById('session-status').textContent})"
                )
                if cleared["text"]:
                    raise AssertionError("Private slide content remained in WebKit DOM after unload")
                print(json.dumps({
                    "ok": True, "browser": "WebKit headless",
                    "emulatedViewport": "390x844", "initial": initial,
                    "final": final, "cleared": cleared,
                    "physicalPhoneTested": False,
                    "screenshot": str(OUTPUT),
                }, indent=2))
            finally:
                browser.close()
    finally:
        process.terminate()
        try:
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=3)

if __name__ == "__main__":
    main()
