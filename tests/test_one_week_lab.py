"""Offline synthetic tests; no market-data requests."""
import unittest
import pandas as pd
from run_one_week import MODES, prepare_window, signals, simulate


def bars():
    return pd.DataFrame(dict(Open=[100,100,101,102,103], High=[102,103,104,105,106], Low=[98,99,100,101,102], Close=[101,102,103,104,105], Volume=[1000]*5), index=pd.bdate_range("2026-10-12", periods=5))


class OneWeekTests(unittest.TestCase):
    def test_trim_before_analysis(self):
        frame = bars()
        extra = frame.iloc[[0]].copy()
        extra.index = [frame.index[0]-pd.Timedelta(days=3)]
        combined = pd.concat([extra, frame])
        actual = prepare_window(combined, "2026-10-17")
        pd.testing.assert_frame_equal(actual, frame)
        with self.assertRaises(ValueError):
            prepare_window(frame, "2026-10-16")

    def test_short_and_original_readiness(self):
        frame = bars()
        self.assertEqual(signals(frame.iloc[:1]), {})
        early = signals(frame.iloc[:2])
        self.assertIn("fast_momentum", early)
        self.assertNotIn("momentum3", early)
        self.assertIn("momentum3", signals(frame.iloc[:4]))
        self.assertEqual(len(MODES), 16)

    def test_all_trials_serializable_and_reconcile(self):
        import json
        for mode in MODES:
            for hold in (1,2,3):
                for bps in (5,15):
                    journal, result = simulate({"TEST": bars()}, mode, hold, bps)
                    self.assertLessEqual(result["trades"], 3)
                    self.assertAlmostEqual(result["net_pnl"], result["window_end_pnl"]+result["normal_exit_pnl"])
                    self.assertAlmostEqual(result["final_equity"], 25000+result["net_pnl"])
                    self.assertTrue(all(journal.signal_date < journal.entry_date))
                    self.assertTrue(all(journal.entry_date <= journal.exit_date))
                    json.dumps(result, allow_nan=False)

    def test_future_bar_does_not_change_entry(self):
        frame = bars()
        altered = frame.copy()
        altered.loc[altered.index[-1], ["Open","High","Low","Close"]] = [120,125,119,123]
        a, _ = simulate({"TEST":frame}, "fast_momentum", 3, 15)
        b, _ = simulate({"TEST":altered}, "fast_momentum", 3, 15)
        self.assertEqual(a.iloc[0].entry_date, b.iloc[0].entry_date)
        self.assertEqual(a.iloc[0].shares, b.iloc[0].shares)
        self.assertEqual(a.iloc[0].entry_fill, b.iloc[0].entry_fill)

    def test_forced_exit_and_no_trade(self):
        frame = bars()
        journal, result = simulate({"TEST":frame}, "momentum3", 3, 15)
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["window_end_exits"], 1)
        self.assertEqual(journal.iloc[0].exit_reason, "window_end")
        _, empty = simulate({"TEST":frame}, "reversal2", 1, 15)
        self.assertEqual(empty["trades"], 0)
        self.assertIsNone(empty["win_rate_pct"])

    def test_stop_first_and_alignment(self):
        frame = bars()
        frame.loc[frame.index[2], ["Open","High","Low","Close"]] = [101,120,90,103]
        journal, _ = simulate({"TEST":frame}, "fast_momentum", 1, 15)
        self.assertEqual(journal.iloc[0].exit_reason, "stop")
        shifted = bars()
        shifted.index = shifted.index+pd.Timedelta(days=1)
        with self.assertRaises(ValueError):
            simulate({"A": bars(), "B":shifted}, "fast_momentum", 1, 15)


if __name__ == "__main__":
    unittest.main()
