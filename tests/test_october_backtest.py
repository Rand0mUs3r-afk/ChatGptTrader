import pandas as pd
from backtest_october_2026 import simulate


def fixture():
    dates = pd.bdate_range('2026-08-20','2026-10-06')
    bars = pd.DataFrame({'Open':100.0,'High':101.0,'Low':99.0,'Close':100.0,'Volume':1000},index=dates)
    features = [dict(active={'inside_breakout'},stops={'inside_breakout':95.0},groups=('compression',),close=100.0,span=2.0,quality=0.5) for _ in dates]
    return {'TEST':bars},{'TEST':features}


def test_only_october_entries_and_no_future_training():
    data,cached = fixture()
    seen = []
    def assessor(history,row,features):
        seen.append(history.index[-1])
        return dict(target_status='EXPERIMENTAL_CANDIDATE',assessed_target=104.0,assessed_net_rr=2.0,historical_examples=30,walkforward_examples=12), {}
    summary,journal,daily,decisions = simulate(data,cached,'compression_family',7,assessor=assessor)
    assert journal[0]['entry_date'] == '2026-10-01'
    assert all(r['entry_date'].startswith('2026-10-') for r in journal)
    assert seen == [pd.Timestamp('2026-09-30')]
    assert summary['closed_trades'] == 0
    assert summary['open_positions'] == 1
    assert journal[0]['exit_reason'] == 'OPEN_AT_CUTOFF'
    assert daily[-1]['date'] == '2026-10-06'


def test_stop_first_and_no_same_day_reentry():
    data,cached = fixture()
    data['TEST'].loc['2026-10-01',['High','Low']] = [110.0,94.0]
    def assessor(*args):
        return dict(target_status='EXPERIMENTAL_CANDIDATE',assessed_target=104.0,assessed_net_rr=2.0,historical_examples=30,walkforward_examples=12), {}
    summary,journal,_,_ = simulate(data,cached,'compression_family',5,assessor=assessor)
    assert journal[0]['exit_reason'] == 'stop'
    assert journal[0]['net_pnl'] < 0
    assert sum(r['entry_date'] == '2026-10-01' for r in journal) == 1
    assert journal[1]['entry_date'] == '2026-10-02'
