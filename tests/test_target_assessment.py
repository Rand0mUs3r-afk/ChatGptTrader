import pandas as pd
import pytest
from assess_targets import propose, trial, assess


def flat_bars(n=20):
    return pd.DataFrame({'Open':[100.0]*n,'High':[102.0]*n,'Low':[98.0]*n,'Close':[100.0]*n})


def test_target_uses_excursion_not_forced_two_r():
    result = propose(flat_bars(),100,95,[{'mfe_r':1.6}]*20)
    assert result['assessed_target'] == pytest.approx(108)
    assert result['assessed_net_rr'] < 1.6
    assert propose(flat_bars(),100,95,[{'mfe_r':1.6}]*19)['assessed_target'] is None


def test_confirmed_high_caps_target():
    bars = flat_bars()
    bars.loc[15,'High'] = 103
    result = propose(bars,100,95,[{'mfe_r':3.0}]*20)
    assert result['nearest_confirmed_high'] == 103
    assert 100 < result['assessed_target'] < 103


def test_stop_first_and_unfinished_horizon():
    bars = pd.DataFrame({'Open':[100,100,100],'High':[101,120,101],'Low':[99,90,99],'Close':[100,100,100]})
    result = trial(bars,0,95,2,110)
    assert not result['target_hit']
    assert result['net_r'] <= -1
    assert trial(bars,0,95,2)['mfe_r'] == 0
    with pytest.raises(ValueError):
        trial(bars,1,95,2)


def test_walkforward_waits_for_prior_examples(monkeypatch):
    import run_recent_blend
    monkeypatch.setattr(run_recent_blend,'candidate',lambda *args: {'stop':98.0})
    bars = pd.DataFrame({'Open':[100.0]*260,'High':[104.0]*260,'Low':[99.0]*260,'Close':[101.0]*260},index=pd.bdate_range('2025-01-01',periods=260))
    row = dict(max_hold_sessions=5,strategy='balanced_blend',provisional_entry=101.0,stop=98.0)
    result,audit = assess(bars,row,[{}]*len(bars))
    assert result['historical_examples'] == 47
    assert result['walkforward_examples'] == 27
    assert result['target_status'] == 'EXPERIMENTAL_CANDIDATE'
    examples = audit['completed_nonoverlapping_examples']
    assert all(examples[i]['end_date'] <= examples[i+1]['signal_date'] for i in range(len(examples)-1))
