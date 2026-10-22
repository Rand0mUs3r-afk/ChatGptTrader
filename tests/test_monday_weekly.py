"""Synthetic Monday scheduling and portfolio checks; no downloads."""
import unittest
import pandas as pd
from run_monday_weekly import week_schedule, simulate_weekly


def bars():
    frame = pd.DataFrame(dict(Open=[100.0]*15, High=[102.0]*15, Low=[98.0]*15, Close=[101.0]*15, Volume=[1000]*15), index=pd.bdate_range("2026-08-03", periods=15))
    frame.iloc[3, :4] = [101,102,98,99]
    frame.iloc[4, :4] = [100,104,99,103]
    return frame


class MondayWeeklyTests(unittest.TestCase):
    def test_four_and_five_session_schedules(self):
        frame = bars()
        for day, sessions, days, expected in (("Thursday",4,3,"2026-08-13"),("Friday",5,4,"2026-08-14")):
            journal, summary = simulate_weekly({"TEST":frame}, frame, "reversal2", day, 15)
            self.assertEqual(len(journal),1)
            row = journal.iloc[0]
            self.assertEqual(row.signal_date,"2026-08-07")
            self.assertEqual(row.entry_date,"2026-08-10")
            self.assertEqual(row.exit_date,expected)
            self.assertEqual(row.held_sessions,sessions)
            self.assertEqual(row.held_calendar_days,days)
            self.assertEqual(row.exit_reason,"scheduled_weekday_exit")
            self.assertEqual(row.risk_budget,15)
            self.assertLessEqual(row.position_cost,250)
            self.assertLessEqual(row.planned_stop_risk,15)
            self.assertAlmostEqual(summary["final_equity"],1000+journal.net_pnl.sum())
            self.assertEqual(summary["window_end_exits"],0)

    def test_stop_can_exit_monday_no_reentry_that_week(self):
        frame = bars()
        frame.iloc[5,:4] = [100,120,90,101]
        journal, _ = simulate_weekly({"TEST":frame},frame,"reversal2","Friday",15)
        self.assertEqual(len(journal),1)
        self.assertEqual(journal.iloc[0].exit_reason,"stop")
        self.assertEqual(journal.iloc[0].held_sessions,1)

    def test_missing_holiday_and_incomplete_weeks(self):
        dates = bars().index
        self.assertFalse(week_schedule(dates)[0]["eligible"])
        missing_friday = dates.delete(9)
        second = next(x for x in week_schedule(missing_friday) if x["monday"] == "2026-08-10")
        self.assertFalse(second["eligible"])
        self.assertEqual(second["reason"],"incomplete_or_holiday_week")
        missing_monday = dates.delete(5)
        self.assertNotIn("2026-08-10",[x["monday"] for x in week_schedule(missing_monday)])
        cutoff = next(x for x in week_schedule(dates[:9]) if x["monday"] == "2026-08-10")
        self.assertFalse(cutoff["eligible"])

    def test_no_monday_close_signal_lookahead(self):
        frame = bars()
        altered = frame.copy()
        altered.iloc[5,:4] = [100,105,99,104]
        a, _ = simulate_weekly({"TEST":frame},frame,"reversal2","Friday",15)
        b, _ = simulate_weekly({"TEST":altered},altered,"reversal2","Friday",15)
        for field in ("signal_date","entry_date","entry_fill","shares"):
            self.assertEqual(a.iloc[0][field],b.iloc[0][field])

    def test_cash_and_unaffordable_positions(self):
        frame = bars()
        _, cash = simulate_weekly({"TEST":frame},frame,"cash","Friday",15)
        self.assertEqual(cash["final_equity"],1000)
        self.assertEqual(cash["trades"],0)
        frame.loc[:,["Open","High","Low","Close"]] *= 10
        journal, result = simulate_weekly({"TEST":frame},frame,"reversal2","Friday",15)
        self.assertEqual(len(journal),0)
        self.assertGreater(result["unaffordable_candidate_events"],0)


if __name__ == "__main__":
    unittest.main()
