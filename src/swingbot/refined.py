"""Confluence hypothesis: baseline AND experimental, not the existing OR blend."""
from swingbot.experimental import select_signals as select_original


def select_signals(baseline, experimental, mode):
    """Keep original modes unchanged; confluence is same ticker and signal date.

    Agreement is correlated evidence, not a probability of profit. No thresholds
    are learned from development or holdout results. One experimental plan is
    retained on agreement; scores are not added across overlapping strategies.
    """
    if mode != "refined":
        return select_original(baseline, experimental, mode)
    if not baseline or not experimental:
        return []
    required = {"ticker", "signal_date", "strategy"}
    if any(not required.issubset(signal) for signal in baseline + experimental):
        raise ValueError("Confluence requires ticker, signal_date, and strategy.")
    identities = {(signal["ticker"], signal["signal_date"]) for signal in baseline + experimental}
    if len(identities) != 1:
        raise ValueError("Confluence inputs must refer to one ticker and signal date.")
    chosen = select_original([], experimental, "experimental")[0].copy()
    baseline_names = ", ".join(sorted({signal["strategy"] for signal in baseline}))
    baseline_reasons = "; ".join(sorted({signal.get("reason", signal["strategy"]) for signal in baseline}))
    experimental_name = chosen["strategy"]
    experimental_reason = chosen.get("reason", experimental_name)
    chosen["strategy"] = "refined_confluence"
    chosen["reason"] = (
        f"Same-date confluence. Baseline ({baseline_names}): {baseline_reasons}. "
        f"Experimental ({experimental_name}): {experimental_reason}. "
        "One experimental entry/stop/target plan retained; no doubled position."
    )
    return [chosen]
