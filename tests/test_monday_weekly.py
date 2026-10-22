"""Regression tests for daily entries and the five-session maximum, replacing Monday-only expectations."""
import json
import unittest
import pandas as pd
from run_monday_weekly import simulate_max_hold


def bars(signal_i=5):
    frame = pd.DataFrame(dict(Open=[100.0]*15, High=[102.0]*15, Low=[98.0]*15, Close=[101.0]*15, Volume=[1000]*15), index=pd.bdate_range("2026-08-03", periods=15))
    frame.iloc[signal_i-1,:4] = [101,102,98,99]
    frame.iloc[signal_i,:4] = [100,104,99,103]
    return frame


class MaxFiveSessionTests(unittest.TestCase):
    def test_entries_any_weekday_and_five_sessions(self):
        for signal_i, entry_date, exit_date in ((4,"2026-08-10","2026-08-14"),(5,"2026-08-11","2026-08-17"),(6,"2026-08-12","2026-08-18")):
            frame = bars(signal_i)
            journal, summary = simulate_max_hold({"TEST":frame},frame,"reversal2",15)
            self.assertEqual(len(journal),1)
            row = journal.iloc[0]
            self.assertEqual(row.entry_date,entry_date)
            self.assertEqual(row.exit_date,exit_date)
            self.assertEqual(row.held_sessions,5)
            self.assertEqual(row.exit_reason,"five_session_exit")
            self.assertEqual(row.risk_budget,15)
            self.assertLessEqual(row.position_cost,250)
            self.assertLessEqual(row.planned_stop_risk,15)
            self.assertAlmostEqual(summary["final_equity"],1000+journal.net_pnl.sum())
            json.dumps(summary,allow_nan=False)

    def test_reentry_later_same_week_after_stop(self):
        frame = bars(4)
        frame.iloc[5,:4] = [100,101,90,99]
        frame.iloc[6,:4] = [100,104,99,103]
        journal, _ = simulate_max_hold({"TEST":frame},frame,"reversal2",15)
        self.assertEqual(len(journal),2)
        self.assertEqual(journal.iloc[0].entry_date,"2026-08-10")
        self.assertEqual(journal.iloc[0].exit_reason,"stop")
        self.assertEqual(journal.iloc[1].entry_date,"2026-08-12")
        self.assertTrue(all(journal.held_sessions <= 5))

    def test_window_end_is_explicit(self):
        frame = bars(13)
        journal, summary = simulate_max_hold({"TEST":frame},frame,"reversal2",15)
        self.assertEqual(journal.iloc[0].exit_reason,"window_end")
        self.assertEqual(journal.iloc[0].held_sessions,1)
        self.assertEqual(summary["window_end_exits"],1)
        self.assertAlmostEqual(summary["net_pnl"],summary["normal_exit_pnl"]+summary["window_end_pnl"])

    def test_future_close_does_not_authorize_entry(self):
        frame = bars(5)
        changed = frame.copy()
        changed.iloc[6,:4] = [100,105,99,104]
        a, _ = simulate_max_hold({"TEST":frame},frame,"reversal2",15)
        b, _ = simulate_max_hold({"TEST":changed},changed,"reversal2",15)
        for field in ("signal_date","entry_date","entry_fill","shares"):
            self.assertEqual(a.iloc[0][field],b.iloc[0][field])

    def test_cash_and_whole_share_limits(self):
        frame = bars(5)
        _, cash = simulate_max_hold({"TEST":frame},frame,"cash",15)
        self.assertEqual(cash["final_equity"],1000)
        self.assertEqual(cash["trades"],0)
        frame.loc[:,["Open","High","Low","Close"]] *= 10
        journal, result = simulate_max_hold({"TEST":frame},frame,"reversal2",15)
        self.assertEqual(len(journal),0)
        self.assertGreater(result["unaffordable_candidate_events"],0)


if __name__ == "__main__":
    unittest.main()
