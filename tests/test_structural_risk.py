import pandas as pd
import pytest
from assess_structural_risk import structural_stop, risk_features


def bars(n=30):
    return pd.DataFrame({'Open':[100.0]*n,'High':[103.0]*n,'Low':[97.0]*n,'Close':[101.0]*n},index=pd.bdate_range('2026-09-01',periods=n))


def test_stop_is_below_structure_and_has_volatility_room():
    plan = structural_stop(bars(),'compression_family')
    assert plan['stop'] == pytest.approx(92)
    assert plan['stop'] < plan['pattern_low']
    assert 101-plan['stop'] >= 1.5*plan['stop_atr14']


def test_short_history_rejected():
    with pytest.raises(ValueError):
        structural_stop(bars(10),'balanced_blend')


def test_historical_stops_are_causal_and_do_not_mutate_signals():
    data = bars()
    features = [dict(active={'inside_breakout'},stops={'inside_breakout':95},groups=('compression',),quality=0.5) for _ in range(30)]
    first = risk_features(data,'compression_family',features)
    assert first[-1]['stops']['inside_breakout'] == pytest.approx(92)
    assert features[-1]['stops']['inside_breakout'] == 95
    assert not first[0]['active']
    changed = data.copy()
    changed.iloc[-1,changed.columns.get_loc('Low')] = 90
    second = risk_features(changed,'compression_family',features)
    assert first[20]['stops'] == second[20]['stops']
