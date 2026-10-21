
from __future__ import annotations

import math

from swingbot.config import DEFAULT_SETTINGS, Settings


def calculate_position_size(
    entry: float,
    stop: float,
    settings: Settings = DEFAULT_SETTINGS,
) -> dict:
    """Return a proposed share count under simple risk constraints."""
    if entry <= 0:
        raise ValueError("Entry must be positive.")

    if stop <= 0 or stop >= entry:
        raise ValueError("For a long trade, stop must be below entry.")

    if settings.account_equity <= 0:
        raise ValueError("Account equity must be positive.")

    if not 0 < settings.risk_fraction <= 0.02:
        raise ValueError(
            "Risk fraction must be greater than 0 and at most 2%."
        )

    if not 0 < settings.maximum_position_fraction <= 1:
        raise ValueError("Invalid maximum position fraction.")

    risk_budget = settings.account_equity * settings.risk_fraction
    risk_per_share = entry - stop

    shares_by_risk = math.floor(risk_budget / risk_per_share)

    max_position_value = (
        settings.account_equity * settings.maximum_position_fraction
    )
    shares_by_notional = math.floor(max_position_value / entry)

    shares = max(0, min(shares_by_risk, shares_by_notional))

    return {
        "shares": shares,
        "risk_budget": round(risk_budget, 2),
        "estimated_stop_risk": round(shares * risk_per_share, 2),
        "position_value": round(shares * entry, 2),
        "risk_per_share": round(risk_per_share, 4),
    }


def attach_position_size(
    signal: dict,
    settings: Settings = DEFAULT_SETTINGS,
) -> dict:
    """Enrich a signal with sizing data without modifying the input."""
    result = signal.copy()
    sizing = calculate_position_size(
        entry=float(result["entry"]),
        stop=float(result["stop"]),
        settings=settings,
    )
    result.update(sizing)

    if result["shares"] <= 0:
        result["eligible"] = False
        result["rejection_reason"] = "Position size is zero"
    else:
        result["eligible"] = True
        result["rejection_reason"] = ""

    return result
