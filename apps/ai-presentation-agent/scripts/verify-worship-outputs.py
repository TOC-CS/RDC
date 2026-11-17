#!/usr/bin/env python3
"""Isolated worship projector/stage/broadcast visual integration check.

Runs a temporary private Presentation Agent. Does not connect to existing
owner/production presentation sessions, OBS, microphones, cameras or MIDI.
"""
import argparse
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
NODE = os.environ.get("PRESENTATION_NODE", "/opt/homebrew/opt/node@24/bin/node")
SERVICE = ROOT / "skills/ai-presentation-agent/worship/examples/sunday-service.json"
SERVER = ROOT / "scripts/managed-server.mjs"
SENTINEL = "PRIVATE_STAGE_ONLY_PRAYER_AND_CHORD_NOT_FOR_PUBLIC"
TIMEOUT = 8

def request(origin, route, token, value=None):
    args = {"url": origin + route}
    if value is None:
        args["headers"] = {"Authorization": "Bearer " + token}
    else:
        args["data"] = json.dumps(value).encode("utf8")
        args["headers"] = {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        }
        args["method"] = "POST"
    with urllib.request.urlopen(urllib.request.Request(**args)) as response:
        return json.load(response)

def launch_service(state_dir):
    env = dict(os.environ)
    env["PRESENTATION_AGENT_STATE_DIR"] = str(state_dir)
    env.pop("PRESENTATION_ALLOW_EXTERNAL_CONTROL", None)
    process = subprocess.Popen(
        [NODE, str(SERVER)], cwd=ROOT, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    marker = state_dir / "control.json"
    for _ in range(150):
        if marker.exists():
            result = json.loads(marker.read_text())
            if all(result.get(key) for key in ("token", "viewerToken", "stageToken", "streamToken")):
                return process, result
        if process.poll() is not None:
            raise RuntimeError("Isolated worship server exited before it initialized.")
        time.sleep(.03)
    raise RuntimeError("Isolated worship server did not become ready.")

def run(engine):
    with tempfile.TemporaryDirectory(prefix="toc-worship-isolated-") as directory:
        state_dir = Path(directory)
        process, state = launch_service(state_dir)
        url = "http://127.0.0.1:" + str(state["port"])
        browser = None
        try:
            original = json.loads(SERVICE.read_text())
            plan = copy.deepcopy(original)
            plan["items"][0]["notes"] = SENTINEL
            plan["items"][1]["notes"] = SENTINEL
            plan["items"][2]["sections"][0]["notes"] = SENTINEL
            result = request(url, "/v1/worship/load", state["token"], {"plan": plan})
            if SENTINEL in json.dumps(result):
                raise AssertionError("Private notes were included in public load receipt")
            with sync_playwright() as playwright:
                browser = (playwright.webkit if engine == "webkit" else playwright.chromium).launch(headless=True)
                # Separate browser contexts emulate independent viewers.
                audience_context = browser.new_context(viewport={"width": 1280, "height": 720})
                stage_context = browser.new_context(viewport={"width": 1280, "height": 720})
                stream_context = browser.new_context(viewport={"width": 1920, "height": 1080})
                audience = audience_context.new_page()
                stage = stage_context.new_page()
                stream = stream_context.new_page()
                audience.goto(url + "/v1/viewer?key=" + state["viewerToken"])
                stage.goto(url + "/v1/stage?key=" + state["stageToken"])
                stream.goto(url + "/v1/stream-overlay?key=" + state["streamToken"])
                audience.wait_for_function(
                    "() => document.body.dataset.connection === 'connected'", timeout=5000)
                stage.wait_for_function(
                    "() => document.getElementById('private-notes')?.textContent.includes('PRIVATE_STAGE_ONLY')",
                    timeout=5000)
                stream.wait_for_function(
                    "() => document.getElementById('title')?.textContent === 'Service Begins Soon'",
                    timeout=5000)
                assert SENTINEL in stage.content()
                assert SENTINEL not in audience.content()
                assert SENTINEL not in stream.content()
                assert state["stageToken"] not in stream.content()
                assert state["stageToken"] not in audience.content()
                assert stage.locator("#title").inner_text() == "Service Begins Soon"
                assert stream.locator("#title").inner_text() == "Service Begins Soon"
                request(url, "/v1/start", state["token"], {"mode": "manual"})
                change = request(url, "/v1/command", state["token"], {"action": "next"})
                if change.get("changed") is not True:
                    raise AssertionError("Operator control did not advance one slide")
                audience.wait_for_function(
                    "() => document.querySelector('.slide:not([hidden]) h1')?.textContent==='Welcome'",
                    timeout=5000)
                stage.wait_for_function(
                    "() => document.getElementById('title').textContent==='Welcome'",
                    timeout=5000)
                stream.wait_for_function(
                    "() => document.getElementById('title').textContent==='Welcome'",
                    timeout=5000)
                if SENTINEL in stream.content() or SENTINEL in audience.content():
                    raise AssertionError("Stage secret leaked into public output after cue")
                # A transparent overlay must not paint an opaque canvas corner.
                png = stream.screenshot(omit_background=True)
                im = Image.open(io.BytesIO(png)).convert("RGBA")
                alpha = im.getpixel((10,10))[3]
                if alpha != 0:
                    raise AssertionError("Stream overlay background corner is opaque: alpha=" + str(alpha))
                audienceStatus = audience.locator("#session-status").inner_text()
                stageStatus = stage.locator("#status").inner_text()
                request(url, "/v1/stop", state["token"], {})
                request(url, "/v1/unload", state["token"], {})
                audience.wait_for_function(
                    "() => document.getElementById('session-status').textContent==='PRESENTATION CLEARED'",
                    timeout=5000)
                stage.wait_for_function(
                    "() => document.getElementById('private-notes').textContent===''",
                    timeout=5000)
                stream.wait_for_function(
                    "() => document.getElementById('title').textContent===''",
                    timeout=5000)
                if SENTINEL in audience.content() or SENTINEL in stream.content() or SENTINEL in stage.content():
                    raise AssertionError("Private text remains after stage deck unload")
                browser.close()
                browser = None
                return {
                    "ok": True, "browser": engine,
                    "audience": "1280x720", "stage": "1280x720", "stream": "1920x1080",
                    "outputsUpdatedTogether": True,
                    "privateStageDataExcludedFromPublic": True,
                    "publicStreamBackgroundAlpha": alpha,
                    "audienceStatusAfterAdvance": audienceStatus,
                    "stageStatusAfterAdvance": stageStatus,
                    "allViewsClearedOnUnload": True,
                    "physicalProjectorTested": False,
                    "realOBSStreamTested": False,
                    "realCameraOrMicOpened": False,
                    "operatorOutputWritesArmed": False,
                }
        finally:
            if browser:
                browser.close()
            process.terminate()
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("webkit","chromium"), default="webkit")
    args = parser.parse_args()
    result = run(args.engine)
    print(json.dumps(result, indent=2))
