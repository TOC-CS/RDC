"""Owner-safe advertised tool catalog for an isolated V2 relay."""
import unittest

from rdc.relay import RelayPermanentError
from rdc.relay_v2 import filter_catalog_for_allowlist


class V2CatalogFilterTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            'rdc_job_run': {'type': 'object', 'properties': {}},
            'rdc_code_context': {'type': 'object', 'properties': {}},
            'rdc_file_write': {'type': 'object', 'properties': {}},
            'rdc_system_status': {'type': 'object', 'properties': {}},
        }

    def test_allowlisted_worker_tools_only_are_advertised(self):
        allowed = ('rdc_code_context', 'rdc_job_run')
        result = filter_catalog_for_allowlist(self.original, allowed)
        self.assertEqual(list(result), ['rdc_job_run', 'rdc_code_context'])
        self.assertNotIn('rdc_file_write', result)
        self.assertNotIn('rdc_system_status', result)
        self.assertEqual(len(self.original), 4)
        self.assertIs(result['rdc_job_run'], self.original['rdc_job_run'])

    def test_unrestricted_relay_preserves_current_catalog(self):
        result = filter_catalog_for_allowlist(self.original, None)
        self.assertEqual(result, self.original)
        self.assertEqual(len(result), 4)

    def test_stale_allowlist_rejects_empty_discovery(self):
        with self.assertRaises(RelayPermanentError):
            filter_catalog_for_allowlist(self.original, ('rdc_nonexistent',))
        with self.assertRaises(RelayPermanentError):
            filter_catalog_for_allowlist({}, ('rdc_job_run',))
