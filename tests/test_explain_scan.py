import pandas as pd
import pytest
from explain_scan import explain_row

@pytest.fixture
def sample():
    bars = pd.DataFrame({'Open':[9,10,10,11], 'High':[11,12,11,13], 'Low':[8,9,9.5,10], 'Close':[10,11,10.5,12], 'Volume':[100]*4}, index=pd.date_range('2026-10-19', periods=4))
    row = dict(ticker='VET.TO', signal_date='2026-10-22', currency='CAD', votes='inside_breakout', families='compression', strategy='compression_family', eligible_at_reference_price=True, provisional_rank=1, shares=5, stop=9.35, provisional_entry=12, provisional_target=17.3, latest_exit_date='2026-10-29', max_hold_sessions=5)
    return row, bars

def test_explains_ranking_prices_and_limits(sample):
    row, bars = sample
    result = explain_row(row, bars)
    assert 'alphabetically' in result['ranking_explanation']
    assert 'CAD 17.30' in result['upside_scenario']
    assert 'NOT a fair-value' in result['upside_scenario']
    assert 'Not estimated' in result['probability_note']
    assert '2026-10-29' in result['time_exit_scenario']

def test_unaffordable_is_not_a_selected_trade(sample):
    row, bars = sample
    result = explain_row({**row, 'eligible_at_reference_price':False, 'shares':0}, bars)
    assert 'Watchlist signal only' in result['ranking_explanation']

def test_unknown_rule_and_wrong_snapshot_fail(sample):
    row, bars = sample
    with pytest.raises(ValueError):
        explain_row({**row, 'votes':'invented_signal'}, bars)
    with pytest.raises(ValueError):
        explain_row({**row, 'signal_date':'2026-10-21'}, bars)
