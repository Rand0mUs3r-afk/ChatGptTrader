import pandas as pd
import pytest
from backtest_october_2026 import simulate


def fixture(entry=1000.0,stop=950.0):
    dates = pd.bdate_range('2026-08-20','2026-10-06')
    bars = pd.DataFrame({'Open':entry,'High':entry+1,'Low':entry-1,'Close':entry,'Volume':1000},index=dates)
    features = [dict(active={'inside_breakout'},stops={'inside_breakout':stop},groups=('compression',),close=entry,span=2.0,quality=0.5) for _ in dates]
    return {'TEST':bars},{'TEST':features}


def assessor(history,row,features):
    assert history.index[-1] < pd.Timestamp('2026-10-07')
    return dict(target_status='EXPERIMENTAL_CANDIDATE',assessed_target=row['provisional_entry']*1.1,assessed_net_rr=2.0,historical_examples=30,walkforward_examples=12), {}


def test_fractional_position_is_not_rejected_or_truncated():
    data,cached = fixture()
    summary,journal,_,_ = simulate(data,cached,'compression_family',7,assessor=assessor,fractional=True)
    assert summary['entries'] == 1
    assert 0 < journal[0]['shares'] < 1
    assert journal[0]['entry_date'] == '2026-10-01'
    assert summary['unrealized_estimated_liquidation_pnl'] == pytest.approx(-3*journal[0]['shares'])
    assert summary['quantity_model'] == 'fractional_simulation'
    assert summary['closed_trades'] == 0


def test_membership_date_prevents_retroactive_entries():
    data,cached = fixture()
    summary,journal,_,_ = simulate(data,cached,'compression_family',7,assessor=assessor,
        fractional=True,eligibility={'TEST':pd.Timestamp('2026-10-05')})
    assert journal[0]['entry_date'] == '2026-10-05'
    assert all(pd.Timestamp(r['entry_date']) >= pd.Timestamp('2026-10-05') for r in journal)


def test_future_addition_not_used_before_cutoff():
    data,cached = fixture()
    summary,journal,_,_ = simulate(data,cached,'compression_family',7,assessor=assessor,
        fractional=True,eligibility={'TEST':pd.Timestamp('2026-10-23')})
    assert not journal
    assert summary['entries'] == 0
    assert summary['asof'] == '2026-10-06'
