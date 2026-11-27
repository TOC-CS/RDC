"""Background web work must not silently obtain a foreground adapter."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rdc.config import Settings
from rdc.engine import Engine
from rdc.adapters import _Browsers
from rdc.errors import RDCError

class BackgroundPolicyTests(unittest.TestCase):
    def test_new_install_defaults_to_background_only(self):
        with tempfile.TemporaryDirectory() as d:
            settings=Settings(state_dir=Path(d)/"state",roots=[Path(d)])
            self.assertIs(getattr(settings,"background_only",None), True)

    def test_background_native_input_is_refused_before_approval_or_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            settings=Settings(state_dir=Path(d)/"state", roots=[Path(d)],
                              desktop_mode="shared",approval_mode="trusted")
            settings.background_only=True
            engine=Engine(settings)
            try:
                with patch.object(engine.adapters,"call") as dispatch:
                    result=engine.call("rdc_desktop_type",{"text":"must never type"})
                    self.assertEqual(result.get("error",{}).get("code"),"background_required",result)
                    dispatch.assert_not_called()
                    self.assertEqual(engine.store.approvals(),[])
            finally: engine.close()

    def test_background_webdriver_refused_before_creating_remote_session(self):
        with tempfile.TemporaryDirectory() as d:
            settings=Settings(state_dir=Path(d)/"state",roots=[Path(d)],
                              browser_backend="webdriver",webdriver_url="http://127.0.0.1:4444")
            settings.background_only=True
            browsers=_Browsers(settings)
            with patch.object(browsers,"http",return_value={"sessionId":"would-share-desktop"}) as http:
                try: browsers.start({})
                except RDCError as error: self.assertEqual(error.code,"background_required")
                else: self.fail("Background-only started a potentially shared WebDriver")
                http.assert_not_called()
                self.assertEqual(browsers.sessions,{})

    def test_background_keeps_file_reads_and_job_status_available(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"sample.txt";p.write_text("background read")
            settings=Settings(state_dir=Path(d)/"state",roots=[Path(d)])
            settings.background_only=True
            engine=Engine(settings)
            try:
                result=engine.call("rdc_file_read",{"file_path":str(p)})
                self.assertTrue(result["ok"],result)
                self.assertTrue(engine.call("rdc_job_list",{})["ok"])
            finally: engine.close()
