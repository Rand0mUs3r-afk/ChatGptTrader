"""Synthetic checks of the explicitly configured $1,000 account."""
import unittest
import pandas as pd
from run_reclaim_lab import simulate, portfolio_summary


def bars():
    frame = pd.DataFrame(dict(Open=[100.0]*15, High=[102.0]*15, Low=[98.0]*15, Close=[101.0]*15, Volume=[1000]*15), index=pd.bdate_range("2026-08-31", periods=15))
    frame.iloc[2, :4] = [101, 102, 98, 99]
    frame.iloc[3, :4] = [100, 104, 99, 103]
    return frame


class Portfolio1000Tests(unittest.TestCase):
    def test_budget_risk_and_duration(self):
        frame = bars()
        journal, summary = simulate({"TEST":frame}, frame, "reversal2", 15, starting=1000, allocation=0.25, risk_fraction=0.06)
        self.assertEqual(len(journal), 1)
        trade = journal.iloc[0]
        self.assertEqual(trade.allocation_budget, 250)
        self.assertEqual(trade.risk_budget, 15)
        self.assertLessEqual(trade.position_cost, 250)
        self.assertLessEqual(trade.planned_stop_risk, 15)
        self.assertEqual(trade.held_sessions, 3)
        self.assertEqual(trade.held_calendar_days, 4)
        self.assertAlmostEqual(summary["final_equity"], 1000+journal.net_pnl.sum())
        self.assertEqual(summary["trades"], summary["wins"]+summary["losses"]+summary["breakeven"])
        text = portfolio_summary(pd.DataFrame([summary]))
        self.assertIn("Final equity", text)
        self.assertIn("Won | Lost", text)
        self.assertIn(f"${summary['final_equity']:.2f}", text)

    def test_whole_share_unaffordable_and_cash(self):
        frame = bars()
        frame.loc[:, ["Open", "High", "Low", "Close"]] *= 10
        journal, summary = simulate({"TEST":frame}, frame, "reversal2", 15, starting=1000, allocation=0.25, risk_fraction=0.06)
        self.assertEqual(len(journal), 0)
        self.assertGreater(summary["unaffordable_candidate_events"], 0)
        self.assertEqual(summary["final_equity"], 1000)
        _, cash = simulate({"TEST":frame}, frame, "cash", 15, starting=1000, allocation=0.25, risk_fraction=0.06)
        self.assertIn("N/A", portfolio_summary(pd.DataFrame([cash])))

    def test_same_session_exit_and_legacy_defaults(self):
        frame = bars()
        frame.iloc[4, :4] = [100, 120, 90, 101]
        journal, _ = simulate({"TEST":frame}, frame, "reversal2", 15, starting=1000, allocation=0.25, risk_fraction=0.06)
        self.assertEqual(journal.iloc[0].held_sessions, 1)
        self.assertEqual(journal.iloc[0].held_calendar_days, 0)
        _, old = simulate({"TEST":frame}, frame, "cash", 15)
        self.assertEqual(old["starting_equity"], 25000)


if __name__ == "__main__":
    unittest.main()
