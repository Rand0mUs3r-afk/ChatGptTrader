
import pytest

from swingbot.config import Settings
from swingbot.risk import calculate_position_size


def test_position_size_respects_risk_budget():
    settings = Settings(
        account_equity=25_000,
        risk_fraction=0.005,
        maximum_position_fraction=0.20,
    )

    result = calculate_position_size(
        entry=100,
        stop=95,
        settings=settings,
    )

    assert result["shares"] == 25
    assert result["estimated_stop_risk"] == 125
    assert result["position_value"] == 2500


def test_position_size_respects_notional_cap():
    settings = Settings(
        account_equity=10_000,
        risk_fraction=0.01,
        maximum_position_fraction=0.10,
    )

    result = calculate_position_size(
        entry=100,
        stop=99,
        settings=settings,
    )

    assert result["shares"] == 10
    assert result["position_value"] == 1000


def test_long_trade_stop_must_be_below_entry():
    with pytest.raises(ValueError):
        calculate_position_size(
            entry=100,
            stop=100,
        )


def test_invalid_risk_fraction_is_rejected():
    settings = Settings(risk_fraction=0.05)

    with pytest.raises(ValueError):
        calculate_position_size(
            entry=100,
            stop=95,
            settings=settings,
        )
