import unittest
from portfolio_reconciliation import reconciled_book, ReconciliationError

class ReconciliationTests(unittest.TestCase):
    def run_reads(self, outcomes):
        calls = []
        def read(*args):
            calls.append(1)
            outcome = outcomes[min(len(calls)-1, len(outcomes)-1)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return reconciled_book(read, None, {}, 100000, sleep=lambda seconds: None), len(calls)
    def test_open_order_snapshot_race_recovers(self):
        self.assertEqual(self.run_reads([RuntimeError('Unmanaged open order'), ({'BIIB':[25000,1269]},25000)]), (({'BIIB':[25000,1269]},25000),2))
    def test_fill_snapshot_race_recovers(self):
        self.assertEqual(self.run_reads([RuntimeError('Position ownership mismatch'), RuntimeError('Position ownership mismatch'), ({'BIIB':[25000,1269]},0)])[1],3)
    def test_persistent_unknown_order_not_ignored(self):
        with self.assertRaisesRegex(ReconciliationError,'OPEN_ORDER_SNAPSHOT_MISMATCH'):
            self.run_reads([RuntimeError('Unmanaged open order')])
    def test_persistent_ownership_mismatch_not_ignored(self):
        with self.assertRaisesRegex(ReconciliationError,'POSITION_OWNERSHIP_MISMATCH'):
            self.run_reads([RuntimeError('Position ownership mismatch')])
    def test_hard_safety_failures_do_not_retry(self):
        for message in ('Duplicate pending entries','Invalid portfolio exposure or more than three occupied slots','Unexpected position direction','Incomplete order-history pagination; manual review required'):
            with self.assertRaises(ReconciliationError):
                self.run_reads([RuntimeError(message),({},0)])
    def test_unknown_runtime_error_not_reclassified(self):
        with self.assertRaisesRegex(RuntimeError,'HTTP 403'):
            self.run_reads([RuntimeError('HTTP 403')])
    def test_healthy_snapshot_unchanged(self):
        self.assertEqual(self.run_reads([({},0)]),(({},0),1))
