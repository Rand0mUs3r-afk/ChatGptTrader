import copy
import unittest
from paper_exit_safety import verify_protection

class HeldBracketTests(unittest.TestCase):
    def setUp(self):
        self.stop = dict(id='stop', symbol='LUV', side='sell', type='stop', status='held', order_class='bracket', qty='10', filled_qty='0', stop_price='20')
        self.parent = dict(id='entry', symbol='LUV', side='buy', status='filled', order_class='bracket', qty='10', filled_qty='10', legs=[copy.deepcopy(self.stop)])
        self.position = dict(symbol='LUV', side='long', qty='10')
    def check(self):
        outer = self
        class API:
            def call(self, method, path, **kwargs):
                if method != 'GET':
                    raise AssertionError('Unexpected broker write')
                if path == '/v2/positions/LUV':
                    return outer.position
                if path == '/v2/orders/entry':
                    return outer.parent
                if path == '/v2/orders/stop':
                    return outer.stop
                raise AssertionError(path)
        return verify_protection(API(), dict(id='entry'), self.position, sleep=lambda seconds: None)
    def test_filled_bracket_held_stop_is_protection(self):
        self.assertTrue(self.check())
    def test_parent_not_bracket_not_accepted(self):
        self.parent['order_class'] = ''
        self.assertFalse(self.check())
    def test_partial_parent_not_accepted(self):
        self.parent.update(status='partially_filled', filled_qty='5')
        self.assertFalse(self.check())
    def test_standalone_held_not_accepted(self):
        self.stop['order_class'] = ''
        self.assertFalse(self.check())
    def test_unlinked_held_not_accepted(self):
        self.parent['legs'] = []
        self.assertFalse(self.check())
    def test_canceled_bracket_stop_not_accepted(self):
        self.stop['status'] = 'canceled'
        self.assertFalse(self.check())
    def test_wrong_symbol_not_accepted(self):
        self.stop['symbol'] = 'OTHER'
        self.assertFalse(self.check())
    def test_insufficient_coverage_not_accepted(self):
        self.stop['qty'] = '9'
        self.assertFalse(self.check())
    def test_invalid_stop_price_not_accepted(self):
        self.stop['stop_price'] = 'nan'
        self.assertFalse(self.check())
