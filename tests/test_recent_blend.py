import unittest
import pandas as pd
from run_recent_blend import prepare,features,monthly_weights,simulate,FAMILIES,candidate


def bars():
    f=pd.DataFrame(dict(Open=[100.0]*40,High=[102.0]*40,Low=[98.0]*40,Close=[101.0]*40,Volume=[1000]*40),index=pd.bdate_range("2025-01-06",periods=40))
    f.iloc[4,:4]=[101,102,98,99]
    f.iloc[5,:4]=[100,104,99,103]
    return f


class RecentBlendTests(unittest.TestCase):
    def test_five_seven_sessions_and_account(self):
        for hold in (5,7):
            f=bars()
            data={"SPY":f,"TEST":f}
            cache={t:features(x) for t,x in data.items()}
            trades,curve,result,_=simulate(data,cache,"reversal2",hold,15,start_index=4)
            self.assertEqual(len(trades),1)
            r=trades[0]
            self.assertEqual(r["entry_date"],str(f.index[6].date()))
            self.assertEqual(r["held_sessions"],hold)
            self.assertLessEqual(r["position_cost"],250)
            self.assertLessEqual(r["planned_stop_risk"],15)
            self.assertAlmostEqual(result["final_equity"],1000+sum(x["net_pnl"] for x in trades))
            self.assertEqual(curve[-1]["equity"],result["final_equity"])

    def test_weights_exclude_future_and_open_trades(self):
        records={g:[] for g in FAMILIES}
        records["trend"]=[dict(exit_index=10,risk_multiple=1)]
        a,audit=monthly_weights(records,20)
        records["trend"].append(dict(exit_index=20,risk_multiple=1000))
        records["trend"].append(dict(exit_index=30,risk_multiple=-1000))
        b,_=monthly_weights(records,20)
        self.assertEqual(a,b)
        self.assertEqual(audit["trend"]["last_exit_index"],10)
        self.assertAlmostEqual(sum(a.values()),1)

    def test_recent_outcomes_have_more_influence(self):
        a={g:[] for g in FAMILIES}
        a["trend"]=[dict(exit_index=10,risk_multiple=1),dict(exit_index=190,risk_multiple=-1)]
        b={g:[] for g in FAMILIES}
        b["trend"]=[dict(exit_index=10,risk_multiple=-1),dict(exit_index=190,risk_multiple=1)]
        wa,_=monthly_weights(a,200)
        wb,_=monthly_weights(b,200)
        self.assertLess(wa["trend"],wb["trend"])

    def test_family_votes_not_raw_vote_count(self):
        f=dict(active={"breakout3","momentum3","fast_breakout","fast_momentum"},groups=("trend",),
            stops={x:98 for x in ("breakout3","momentum3","fast_breakout","fast_momentum")},close=101,span=4,quality=.8)
        self.assertIsNone(candidate(f,"balanced_blend",{g:1/3 for g in FAMILIES},True))

    def test_daily_drawdown_and_stop_first(self):
        f=bars()
        f.iloc[6,:4]=[100,120,90,101]
        data={"SPY":f}
        trades,_,result,_=simulate(data,{"SPY":features(f)},"reversal2",7,15,start_index=4)
        self.assertEqual(trades[0]["exit_reason"],"stop")
        self.assertEqual(trades[0]["held_sessions"],1)
        self.assertGreater(result["daily_mtm_drawdown_pct"],0)

    def test_cutoff_and_prefix_causality(self):
        f=bars()
        retained=prepare(f,f.index[-1])
        self.assertEqual(retained.index[-1],f.index[-2])
        altered=f.copy()
        altered.iloc[-1,:4]=[200,210,190,205]
        self.assertEqual(features(f)[5],features(altered)[5])

    def test_cash_and_monthly_audit(self):
        f=bars()
        data={"SPY":f}
        cache={"SPY":features(f)}
        trades,_,result,_=simulate(data,cache,"cash",5,15,start_index=4)
        self.assertEqual(trades,[])
        self.assertEqual(result["final_equity"],1000)
        _,_,_,updates=simulate(data,cache,"recent_blend",5,15,start_index=4)
        for update in updates:
            for audit in update["audit"].values():
                self.assertTrue(audit["last_exit_index"] is None or audit["last_exit_index"]<update["boundary"])


if __name__=="__main__":
    unittest.main()
