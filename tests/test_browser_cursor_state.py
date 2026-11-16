"""Cursor ownership regression: independent browser source never advertises a phantom marker."""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote
from rdc.config import Settings
from rdc.engine import Engine


class BrowserCursorStateTests(unittest.TestCase):
    def test_invisible_until_pointer_action_and_reset_on_navigation(self):
        with tempfile.TemporaryDirectory(prefix="rdc-cursor-state-") as temp:
            root=Path(temp)
            engine=Engine(Settings(state_dir=root/"state",roots=[root],approval_mode="trusted"))
            try:
                start=engine.call("rdc_browser_start",{"browser":"chromium"})
                self.assertTrue(start["ok"],start)
                session=start["session_id"]
                initial=engine.call("rdc_preview_frame",{"session_id":session})
                self.assertTrue(initial["ok"],{k:v for k,v in initial.items() if k!="data"})
                self.assertIs(initial["cursor"].get("visible"),False,
                              "A brand new source must have no visible agent cursor")
                first=engine.call("rdc_browser_navigate",{
                    "session_id":session,"url":"data:text/html,"+quote("<title>RDC cursor A</title><h1>A</h1>")})
                self.assertTrue(first["ok"],first)
                obs=engine.call("rdc_browser_observe",{"session_id":session})
                self.assertTrue(obs["ok"],obs)
                move=engine.call("rdc_browser_pointer",{"session_id":session,
                    "observation_id":obs["observation_id"],"action":"move","x":123,"y":95})
                self.assertTrue(move["ok"],move)
                active=engine.call("rdc_preview_frame",{"session_id":session})
                self.assertTrue(active["ok"],{k:v for k,v in active.items() if k!="data"})
                self.assertEqual(active["cursor"],{"x":123,"y":95,"visible":True})
                second=engine.call("rdc_browser_navigate",{
                    "session_id":session,"url":"data:text/html,"+quote("<title>RDC cursor B</title><h1>B</h1>")})
                self.assertTrue(second["ok"],second)
                inactive=engine.call("rdc_preview_frame",{"session_id":session})
                self.assertTrue(inactive["ok"],{k:v for k,v in inactive.items() if k!="data"})
                self.assertIs(inactive["cursor"].get("visible"),False,
                              "Old pointer state must not leak into a new page")
            finally:
                engine.close()
