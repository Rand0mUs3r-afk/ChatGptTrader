import copy
import unittest
from paper_exit_safety import verify_protection, patch_source

P = dict(symbol='BKR', qty='320', side='long')
LEG = dict(id='stop', symbol='BKR', side='sell', type='stop', qty='320', filled_qty='0', stop_price='52.36', status='new')
OWNER = dict(id='entry', symbol='BKR', side='buy', legs=[LEG])

class Fake:
    def __init__(self, statuses=('new',), parent=None, position=P, error=False):
        self.statuses, self.parent, self.position, self.error = statuses, copy.deepcopy(parent or OWNER), position, error
        self.reads = 0
        self.calls = []
    def call(self, method, path, **kwargs):
        self.calls.append((method, path))
        if method != 'GET':
            raise AssertionError('Verification attempted a write')
        if self.error:
            raise RuntimeError('Read failed')
        if path == '/v2/positions/BKR':
            return self.position
        if path == '/v2/orders/entry':
            return self.parent
        if path == '/v2/orders/stop':
            leg = dict(LEG, status=self.statuses[min(self.reads, len(self.statuses)-1)])
            self.reads += 1
            return leg
        raise AssertionError(path)

class ProtectionTests(unittest.TestCase):
    def check(self, api, owner=OWNER):
        return verify_protection(api, owner, P, sleep=lambda seconds: None)
    def test_active_stop_preserved(self):
        self.assertTrue(self.check(Fake()))
    def test_list_missing_stop_direct_parent_finds_it(self):
        self.assertTrue(self.check(Fake(), dict(OWNER, legs=[])))
    def test_stale_list_held_direct_stop_active(self):
        self.assertTrue(self.check(Fake(), dict(OWNER, legs=[dict(LEG, status='held')])))
    def test_transitional_stop_retried(self):
        api = Fake(('held', 'pending_cancel', 'new'))
        self.assertTrue(self.check(api))
        self.assertEqual(api.reads, 3)
    def test_persistently_held_not_blindly_trusted(self):
        api = Fake(('held',))
        self.assertFalse(self.check(api))
        self.assertEqual(api.reads, 3)
    def test_canceled_stop_emergency_path_retained(self):
        self.assertFalse(self.check(Fake(('canceled',))))
    def test_missing_stop_emergency_path_retained(self):
        self.assertFalse(self.check(Fake(parent=dict(OWNER, legs=[])), dict(OWNER, legs=[])))
    def test_insufficient_stop_quantity(self):
        api = Fake()
        original = api.call
        def call(method, path, **kwargs):
            result = original(method, path, **kwargs)
            return dict(result, qty='319') if path.endswith('/stop') else result
        api.call = call
        self.assertFalse(self.check(api))
    def test_changed_or_closed_position_aborts(self):
        for position in (None, dict(P, qty='319'), dict(P, side='short')):
            with self.assertRaises(RuntimeError):
                self.check(Fake(position=position))
    def test_read_failure_does_not_authorize_liquidation(self):
        with self.assertRaises(RuntimeError):
            self.check(Fake(error=True))
    def test_wrong_parent_aborts(self):
        with self.assertRaises(RuntimeError):
            self.check(Fake(parent=dict(OWNER, symbol='OTHER')))
    def test_patch_preserves_exit_condition_and_audits(self):
        source = 'def manage():\n    protected=any([])\n    if not protected or time_exit:\n        emergency()\n'
        patched = patch_source(source)
        compile(patched, '<test>', 'exec')
        self.assertIn('protected=verify_protection(api,owner,p)', patched)
        self.assertIn('if not protected or time_exit:', patched)
        self.assertIn('audit_exit(owner,p,protected,time_exit)', patched)
    def test_patch_rejects_changed_base(self):
        with self.assertRaises(RuntimeError):
            patch_source('def manage(): pass')

if __name__ == '__main__':
    unittest.main()
