import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rdc.adapters import Adapters


class NativeCoordinates(unittest.TestCase):
    def test_resized_capture_maps_to_logical_desktop_input(self):
        from PIL import Image
        adapter=Adapters(SimpleNamespace(desktop_mode='shared',browser_backend='disabled',adb_serial=None))
        fake=SimpleNamespace(screenshot=lambda:Image.new('RGB',(3840,2160)),size=lambda:(1920,1080))
        try:
            with patch.dict(sys.modules,{'pyautogui':fake}):
                shot=adapter.call('rdc_desktop_screenshot',{})
            self.assertEqual((shot['width'],shot['height']),(2560,1440))
            self.assertEqual((shot['input_width'],shot['input_height']),(1920,1080))
            self.assertEqual(shot['width']/2*shot['input_scale_x'],960)
            self.assertEqual(shot['height']/2*shot['input_scale_y'],540)
        finally:
            adapter.close()
