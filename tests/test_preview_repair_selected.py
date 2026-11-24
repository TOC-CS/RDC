import unittest
from tests import test_preview_consistency as contracts
class SelectedPreviewTests(unittest.TestCase):
    def test_legacy_user_float(self):
        contracts.PreviewConsistencyContracts().check("legacy-user-float")
    def test_legacy_user_refused(self):
        contracts.PreviewConsistencyContracts().check("legacy-user-refused")
