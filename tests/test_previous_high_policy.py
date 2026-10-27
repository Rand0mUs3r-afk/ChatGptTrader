import unittest
import pandas as pd
from portfolio_previous_high import confirmed_highs, select_target, size, _replace

class PreviousHighTests(unittest.TestCase):
    def setUp(self):
        self.now = pd.Timestamp('2026-10-27T15:00:00Z')
        self.quote = dict(bp=99.99, ap=100., t=self.now.isoformat())
        self.row = dict(symbol='TEST', reference=100., stop=98., confirmed_highs=[103., 110.])
    def sized(self, **overrides):
        args = dict(row=self.row, quote=self.quote, now=self.now, equity=100000., cash=100000., gross_room=90000., risk_room=5400., cid='test')
        args.update(overrides)
        return size(**args)
    def test_latest_high_not_highest(self):
        self.assertEqual(select_target([103., 110.], 100), '103.00')
    def test_high_below_entry_skipped(self):
        self.assertEqual(select_target([99., 110.], 100), '110.00')
    def test_no_high_no_trade(self):
        self.assertIsNone(self.sized(row=dict(self.row, confirmed_highs=[99.])))
    def test_rounding_cannot_put_target_at_entry(self):
        self.assertIsNone(select_target([100.159], 100.15))
    def test_nonfinite_high_rejected(self):
        self.assertEqual(select_target([float('nan'), float('inf'), 103], 100), '103.00')
    def test_two_right_bars_required(self):
        self.assertEqual(confirmed_highs(pd.DataFrame({'High':[1,2,5,3]})), [])
        self.assertEqual(confirmed_highs(pd.DataFrame({'High':[1,2,5,3,2]})), [5.])
    def test_future_peak_not_used_early(self):
        frame = pd.DataFrame({'High':[1,2,5,3,2,4,8,6,4]})
        self.assertEqual(confirmed_highs(frame.iloc[:7]), [5.])
        self.assertEqual(confirmed_highs(frame), [8.,5.])
    def test_ten_percent_allocation_and_point_six_percent_risk(self):
        body, cost, risk = self.sized()
        self.assertLessEqual(cost, 10000.)
        self.assertLessEqual(risk, 600.)
        self.assertEqual(body['take_profit']['limit_price'], '103.00')
    def test_remaining_portfolio_risk_enforced(self):
        result = self.sized(risk_room=20.)
        self.assertTrue(result is None or result[2] <= 20.)
    def test_cash_and_exposure_limits(self):
        self.assertIsNone(self.sized(cash=0.))
        self.assertIsNone(self.sized(gross_room=0.))
    def test_stale_quote_rejected(self):
        self.assertIsNone(self.sized(now=self.now+pd.Timedelta(seconds=11)))
    def test_stop_unchanged(self):
        self.assertEqual(self.sized()[0]['stop_loss']['stop_price'], '98.00')
    def test_no_minimum_r_filter(self):
        result = self.sized(row=dict(self.row, stop=95., confirmed_highs=[100.5]))
        self.assertIsNotNone(result)
        self.assertEqual(result[0]['take_profit']['limit_price'], '100.50')
    def test_patch_guard(self):
        with self.assertRaises(RuntimeError):
            _replace('missing', 'required', 'new')

class InstalledPolicyTests(unittest.TestCase):
    def test_installed_nine_slot_book(self):
        from portfolio_previous_high import _load
        ns = _load()
        class API:
            def __init__(self, count):
                self.roots = [dict(id=f'root{i}', symbol=f'TEST{i}', client_order_id=f'fp7v1-test{i}', side='buy', status='filled', qty='10', filled_qty='10', legs=[dict(id=f'stop{i}', stop_price='98', filled_qty='0')]) for i in range(count)]
                self.positions = [dict(symbol=f'TEST{i}', side='long', qty='10', avg_entry_price='100', market_value='1000') for i in range(count)]
            def call(self, method, path, **kwargs):
                if method != 'GET':
                    raise AssertionError('Unexpected write')
                if path == '/v2/positions':
                    return self.positions
                return [dict(id=f'stop{i}', symbol=f'TEST{i}') for i in range(len(self.roots))] if kwargs['params']['status']=='open' else self.roots
        engine = {'PREFIX':'fp7v1-', 'OPEN':{'new'}}
        self.assertEqual(len(ns['raw_book'](API(9), engine, 100000.)[0]),9)
        with self.assertRaises(RuntimeError):
            ns['raw_book'](API(10), engine, 100000.)
    def test_installed_report_limits(self):
        from portfolio_previous_high import configure
        engine = configure({})
        constants = engine['main'].__code__.co_consts
        for value in (9, .10, .90, .054, 'PREVIOUS_CONFIRMED_SWING_HIGH'):
            self.assertIn(value, constants)
