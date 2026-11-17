"""Contract tests for the disposable RDC code-and-terminal benchmark.

Synthetic fixture only. No host AI, Desktop Commander or production work.
"""
import unittest

from benchmarks.coding_workflow import run_local


class CodingWorkflowBenchmarkContract(unittest.TestCase):
    def test_correct_isolated_code_fix_and_durable_terminal(self):
        report = run_local(trials=2, warmups=0, concurrency=())
        self.assertEqual(report['source'], 'isolated RDC Engine')
        self.assertEqual(report['sequential']['runs'], 2)
        self.assertEqual(report['sequential']['correct'], 2)
        self.assertEqual(report['sequential']['failures'], 0)
        for sample in report['sequential']['samples']:
            self.assertTrue(sample['correct'])
            self.assertEqual(sample['initial_test_exit_code'], 1)
            self.assertEqual(sample['corrected_test_exit_code'], 0)
            self.assertEqual(sample['negative_terminal_exit_code'], 23)
            self.assertTrue(sample['stale_sha_conflict_blocked'])
            self.assertTrue(sample['outside_root_blocked'])
            self.assertTrue(sample['idempotent_recovery_same_job'])
            self.assertEqual(sample['read_back_sha256'], sample['expected_sha256'])
            self.assertEqual(sample['patched_source'], 'return a + b')
            self.assertGreater(sample['elapsed_ms'], 0)

    def test_parallel_workers_use_independent_disposable_workspaces(self):
        report = run_local(trials=1, warmups=0, concurrency=(2,), concurrent_tasks_per_worker=1)
        row = report['concurrency'][0]
        self.assertEqual(row['workers'], 2)
        self.assertEqual(row['tasks'], 2)
        self.assertEqual(row['correct'], 2)
        self.assertEqual(row['failures'], 0)
        self.assertGreater(row['throughput_correct_tasks_per_s'], 0)


if __name__ == '__main__':
    unittest.main()
