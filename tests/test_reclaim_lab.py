"""Offline tests for frozen hypotheses and execution mechanics."""
import json
import unittest
import pandas as pd
from run_reclaim_lab import TRIALS, setup, simulate


def bars(n=15):
    return pd.DataFrame(dict(Open=[100.0]*n, High=[102.0]*n, Low=[98.0]*n, Close=[101.0]*n, Volume=[1000]*n), index=pd.bdate_range("2026-09-01", periods=n))


def reversal():
    frame = bars()
    frame.iloc[2, :4] = [101, 102, 98, 99]
    frame.iloc[3, :4] = [100, 104, 99, 103]
    return frame


class ReclaimLabTests(unittest.TestCase):
    def test_reclaim_signal_and_readiness(self):
        frame = bars(5)
        frame.iloc[3, :4] = [99, 103, 97, 102]
        signal = setup(frame.iloc[:4], "failed_reclaim", frame.iloc[:4])
        self.assertIsNotNone(signal)
        self.assertAlmostEqual(signal["stop"], 96.4)
        self.assertIsNone(setup(frame.iloc[:3], "failed_reclaim", frame.iloc[:3]))
        frame.iloc[3, 2] = 98
        self.assertIsNone(setup(frame.iloc[:4], "failed_reclaim", frame.iloc[:4]))

    def test_compression_and_original_inside_are_distinct(self):
        frame = bars(5)
        frame.iloc[2, :4] = [100, 103, 100, 101]
        frame.iloc[3, :4] = [102, 105, 101, 104]
        self.assertIsNotNone(setup(frame.iloc[:4], "compression_breakout", frame.iloc[:4]))
        self.assertIsNone(setup(frame.iloc[:4], "inside_breakout", frame.iloc[:4]))

    def test_no_chase_filter_and_market_gate(self):
        frame = reversal()
        frame.iloc[4, :4] = [107, 108, 100, 107]
        normal, _ = simulate({"TEST":frame}, frame, "reversal2", 15)
        filtered, _ = simulate({"TEST":frame}, frame, "reversal_no_chase", 15)
        self.assertEqual(len(normal), 1)
        self.assertEqual(len(filtered), 0)
        history = frame.iloc[:4]
        falling = history.copy()
        falling.loc[falling.index[-1], "Close"] = 99
        self.assertIsNotNone(setup(history, "reversal_compression_union", falling))
        self.assertIsNone(setup(history, "market_gated_union", falling))
        rising = falling.copy()
        rising.loc[rising.index[-1], "Close"] = 103
        self.assertIsNotNone(setup(history, "market_gated_union", rising))

    def test_all_32_trials_accounting_and_dates(self):
        for n in (15, 5):
            frame = bars(n)
            for mode in TRIALS:
                for cost in (5, 15):
                    journal, summary = simulate({"TEST":frame}, frame, mode, cost)
                    self.assertAlmostEqual(summary["net_pnl"], summary["normal_exit_pnl"]+summary["window_end_pnl"])
                    self.assertAlmostEqual(summary["final_equity"], 25000+summary["net_pnl"])
                    self.assertTrue(all(journal.signal_date < journal.entry_date))
                    self.assertTrue(all(journal.entry_date <= journal.exit_date))
                    json.dumps(summary, allow_nan=False)
            _, cash = simulate({"TEST":frame}, frame, "cash", 15)
            self.assertEqual(cash["trades"], 0)
            self.assertEqual(cash["net_pnl"], 0)
            self.assertIsNone(cash["win_rate_pct"])

    def test_stop_first_and_forced_exit(self):
        frame = reversal().iloc[:5].copy()
        frame.iloc[4, :4] = [100, 120, 90, 101]
        journal, _ = simulate({"TEST":frame}, frame, "reversal2", 15)
        self.assertEqual(journal.iloc[0].exit_reason, "stop")
        frame.iloc[4, :4] = [100, 102, 99, 101]
        journal, summary = simulate({"TEST":frame}, frame, "reversal2", 15)
        self.assertEqual(summary["window_end_exits"], 1)
        self.assertEqual(journal.iloc[0].exit_reason, "window_end")

    def test_future_prices_do_not_change_first_entry(self):
        frame = reversal()
        other = frame.copy()
        other.iloc[-1, :4] = [120, 125, 119, 123]
        a, _ = simulate({"TEST":frame}, frame, "reversal2", 15)
        b, _ = simulate({"TEST":other}, other, "reversal2", 15)
        for field in ("signal_date", "entry_date", "entry_fill", "shares"):
            self.assertEqual(a.iloc[0][field], b.iloc[0][field])

    def test_alignment_validation(self):
        frame = bars()
        shifted = frame.copy()
        shifted.index += pd.Timedelta(days=1)
        with self.assertRaises(ValueError):
            simulate({"TEST":frame}, shifted, "reversal2", 15)


if __name__ == "__main__":
    unittest.main()
