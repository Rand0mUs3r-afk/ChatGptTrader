"""Readable journals based only on accepted, position-sized replay trades."""
import json
import math

import pandas as pd

KEYS = ["ticker", "strategy", "entry_date", "exit_date"]
META = ["entry_reason", "signal_snapshot", "selection_policy"]


def capture_trade(trade, signal, features, market_ok, mode):
    """Record signal-time evidence, not an explanation invented after the outcome."""
    result = trade.copy()
    row = features.iloc[-1]
    fields = ["Close", "EMA20", "SMA50", "SMA200", "ATR14", "RVOL", "PriorHigh20",
              "RelativeStrength20", "ExtensionATR", "EMA20Slope5", "AverageDollarVolume20"]
    snapshot = {}
    for field in fields:
        value = row.get(field)
        snapshot[field] = float(value) if value is not None and math.isfinite(float(value)) else None
    snapshot["benchmark_uptrend"] = bool(market_ok)
    snapshot["signal_score"] = signal.get("score")
    result["entry_reason"] = signal.get("reason") or "Entry reason not recorded by strategy"
    result["signal_snapshot"] = json.dumps(snapshot, sort_keys=True, allow_nan=False)
    result["selection_policy"] = (
        f"Mode: {mode}. One signal per ticker/date; experimental preferred in blend, "
        "otherwise highest score then strategy name. Replay takes first eligible ticker "
        "alphabetically on a date; one position, no exit-day reentry; cash/risk caps apply."
    )
    return result


def enrich_journal(journal, summary, candidates):
    """Add reasons and streaks. Breakeven resets both streaks; ratios use all trades."""
    journal, summary = journal.copy(), summary.copy()
    if not journal.empty:
        if not candidates.empty and set(META).issubset(candidates.columns):
            metadata = candidates[KEYS + META].copy()
            for column in ("entry_date", "exit_date"):
                metadata[column] = pd.to_datetime(metadata[column]).dt.strftime("%Y-%m-%d")
                journal[column] = pd.to_datetime(journal[column]).dt.strftime("%Y-%m-%d")
            if metadata.duplicated(KEYS).any():
                raise ValueError("Ambiguous candidate metadata for a journal trade.")
            journal = journal.merge(metadata, on=KEYS, how="left", validate="one_to_one", sort=False)
        else:
            for column in META:
                journal[column] = "Not recorded; rerun the updated comparison"
    else:
        for column in META:
            journal[column] = pd.Series(dtype=str)
    pnl = pd.to_numeric(journal["net_pnl"], errors="raise").astype(float)
    if not all(math.isfinite(value) for value in pnl):
        raise ValueError("Accepted trade P&L must be finite.")
    wins = losses = best_win = best_loss = 0
    outcomes, win_streaks, loss_streaks = [], [], []
    for value in pnl:
        wins = wins + 1 if value > 0 else 0
        losses = losses + 1 if value < 0 else 0
        best_win, best_loss = max(best_win, wins), max(best_loss, losses)
        outcomes.append("WIN" if value > 0 else "LOSS" if value < 0 else "BREAKEVEN")
        win_streaks.append(wins)
        loss_streaks.append(losses)
    journal["outcome"] = outcomes
    journal["win_streak"] = win_streaks
    journal["loss_streak"] = loss_streaks
    total = len(pnl)
    money_won = float(pnl.clip(lower=0).sum())
    money_lost = float(-pnl.clip(upper=0).sum())
    if not all(math.isfinite(value) for value in (money_won, money_lost)):
        raise ValueError("Aggregate P&L must be finite.")
    summary.update(trades=total, wins=int((pnl > 0).sum()), losses=int((pnl < 0).sum()),
                   breakeven=int((pnl == 0).sum()), total_money_won=money_won,
                   total_money_lost=money_lost, net_pnl=money_won - money_lost,
                   win_rate_pct=float((pnl > 0).sum() / total * 100) if total else 0.0,
                   loss_rate_pct=float((pnl < 0).sum() / total * 100) if total else 0.0,
                   breakeven_rate_pct=float((pnl == 0).sum() / total * 100) if total else 0.0,
                   max_consecutive_wins=best_win, max_consecutive_losses=best_loss,
                   ending_win_streak=wins, ending_loss_streak=losses,
                   streak_basis="Accepted trades in chronological replay order; breakeven resets streaks.")
    return journal, summary


def clean(value):
    return str(value).replace("|", " / ").replace("\n", " ")


def render_journal(journal, summary, title, include_trades=True):
    rows = [
        ("Starting equity", f"{summary['starting_equity']:,.2f}"),
        ("Final equity", f"{summary['final_equity']:,.2f}"),
        ("Total trades taken", str(summary["trades"])),
        ("Winning / losing / breakeven trades", f"{summary['wins']} / {summary['losses']} / {summary['breakeven']}"),
        ("Total money won (winning-trade P&L, after costs)", f"{summary['total_money_won']:,.2f}"),
        ("Total money lost (losing-trade P&L magnitude, after costs)", f"{summary['total_money_lost']:,.2f}"),
        ("Net P&L", f"{summary['net_pnl']:+,.2f}"),
        ("Return", f"{summary['return_pct']:+.2f}%"),
        ("Win / loss / breakeven rates", f"{summary['win_rate_pct']:.2f}% / {summary['loss_rate_pct']:.2f}% / {summary['breakeven_rate_pct']:.2f}%"),
        ("Longest winning streak", str(summary["max_consecutive_wins"])),
        ("Longest losing streak", str(summary["max_consecutive_losses"])),
        ("Ending winning / losing streak", f"{summary['ending_win_streak']} / {summary['ending_loss_streak']}"),
        ("Maximum closed-trade drawdown", f"{summary['max_closed_trade_drawdown_pct']:.2f}%"),
        ("Skipped candidates", str(summary["skipped_candidates"])),
    ]
    text = f"## {clean(title)}\n\n| Metric | Result |\n| :--- | ---: |\n"
    text += "\n".join(f"| {label} | {value} |" for label, value in rows)
    text += "\n\nRates use all accepted trades. Money is in configured account units. "
    text += "Streaks follow closed-trade order; breakeven resets them. Simulation, not actual orders.\n"
    if include_trades:
        text += "\n### Trade-by-trade journal\n"
        if journal.empty:
            text += "\nNo trades were taken in this replay.\n"
        for number, row in enumerate(journal.to_dict("records"), 1):
            text += (f"\n<details>\n<summary>{number}. {clean(row['ticker'])} - {row['outcome']} "
                     f"- P&L {row['net_pnl']:+,.2f}</summary>\n\n"
                     "| Field | Value |\n| :--- | :--- |\n")
            for key in ["strategy", "entry_date", "exit_date", "shares", "entry", "exit", "stop", "target",
                        "net_pnl", "equity_before", "equity_after", "win_streak", "loss_streak", "exit_reason"]:
                text += f"| {key.replace('_', ' ')} | {clean(row.get(key, 'N/A'))} |\n"
            text += f"\nWhy entered: {clean(row.get('entry_reason', 'Not recorded'))}\n"
            text += f"\nWhy selected: {clean(row.get('selection_policy', 'Not recorded'))}\n"
            text += f"\nSignal-time indicators: `{clean(row.get('signal_snapshot', 'Not recorded'))}`\n\n</details>\n"
    return text + "\n"
