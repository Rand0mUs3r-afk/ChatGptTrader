import pytest
from scan_latest_setups import price_plan


def test_whole_share_baseline_preserved():
    assert price_plan(100,95,1000,fractional=False)['shares'] == 2
    assert price_plan(1000,950,1000,fractional=False)['shares'] == 0


def test_fractional_share_below_one_is_allowed():
    plan = price_plan(1000,950,1000,fractional=True)
    assert 0 < plan['shares'] < 1
    assert plan['estimated_cost'] <= 250
    assert plan['planned_stop_risk'] <= 15
    assert plan['quantity_model'] == 'fractional_simulation'


@pytest.mark.parametrize('entry,stop', [(100,95),(1000,950),(10,1),(1,0.9),(3000,2900)])
def test_fractional_sizing_preserves_caps(entry,stop):
    plan = price_plan(entry,stop,1000,fractional=True)
    assert plan['estimated_cost'] <= 250+1e-10
    assert plan['planned_stop_risk'] <= 15+1e-10
    assert plan['shares'] == round(plan['shares'],3)


def test_environment_opt_in(monkeypatch):
    monkeypatch.setenv('FRACTIONAL_SHARES','true')
    assert price_plan(1000,950,1000)['shares'] > 0
