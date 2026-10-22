import pytest
from scan_latest_setups import price_plan

def test_allocation_and_risk_caps():
    plan = price_plan(100, 95, 1000)
    assert plan['shares'] == 2
    assert plan['estimated_cost'] <= 250
    assert plan['planned_stop_risk'] <= 15
    assert plan['provisional_target'] == 110

def test_unaffordable_and_risk_limited():
    assert price_plan(300, 290, 1000)['shares'] == 0
    assert price_plan(10, 1, 1000)['shares'] == 1

@pytest.mark.parametrize('values', [(100,100,1000), (0,1,1000), (100,95,float('nan'))])
def test_invalid_inputs(values):
    with pytest.raises(ValueError):
        price_plan(*values)
