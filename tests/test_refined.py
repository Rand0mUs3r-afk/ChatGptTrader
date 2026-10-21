from copy import deepcopy

import pytest

from swingbot.experimental import select_signals as original
from swingbot.refined import select_signals


def signal(strategy, **updates):
    result = dict(ticker="TEST", signal_date="2025-01-02", strategy=strategy,
                  score=75.0, entry=100.0, stop=95.0, target=110.0, reason=strategy + " reason")
    result.update(updates)
    return result


@pytest.mark.parametrize("mode", ["baseline", "experimental", "blend"])
def test_existing_modes_unchanged(mode):
    baseline, experimental = [signal("breakout")], [signal("experimental_ema_pullback")]
    assert select_signals(baseline, experimental, mode) == original(baseline, experimental, mode)


@pytest.mark.parametrize("baseline,experimental", [([], []), ([signal("breakout")], []),
    ([], [signal("experimental_ema_pullback")])])
def test_refined_requires_both_sources(baseline, experimental):
    assert select_signals(baseline, experimental, "refined") == []


def test_confluence_is_one_trade_and_preserves_plan_and_inputs():
    baseline = [signal("breakout", score=95), signal("pullback", score=90)]
    experimental = [signal("experimental_ema_pullback")]
    before = deepcopy((baseline, experimental))
    result = select_signals(baseline, experimental, "refined")
    assert len(result) == 1
    assert result[0]["strategy"] == "refined_confluence"
    for field in ("entry", "stop", "target", "score"):
        assert result[0][field] == experimental[0][field]
    assert "breakout" in result[0]["reason"] and "pullback" in result[0]["reason"]
    assert "experimental_ema_pullback" in result[0]["reason"]
    assert (baseline, experimental) == before


@pytest.mark.parametrize("updates", [dict(ticker="OTHER"), dict(signal_date="2025-01-03")])
def test_no_false_cross_stock_or_cross_date_agreement(updates):
    with pytest.raises(ValueError, match="one ticker and signal date"):
        select_signals([signal("breakout")], [signal("experimental", **updates)], "refined")


def test_missing_identity_rejected():
    with pytest.raises(ValueError, match="requires"):
        select_signals([{}], [signal("experimental")], "refined")


def test_unknown_mode_still_rejected():
    with pytest.raises(ValueError):
        select_signals([], [], "unknown")
