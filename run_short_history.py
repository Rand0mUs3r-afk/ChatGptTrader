"""Manual 15-session sandbox; never reads older bars for strategy calculations."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

from swingbot.scanner import load_tickers
from swingbot.short_history import MODES, prepare_window, simulate


def main():
    output = Path("reports/short_history_15")
    output.mkdir(parents=True, exist_ok=True)
    asof = pd.Timestamp.now(tz="America/New_York").normalize()
    windows, coverage = {}, {}
    for ticker in load_tickers("config/tickers.txt"):
        raw = yf.Ticker(ticker).history(period="1mo", interval="1d", auto_adjust=True, actions=False, raise_errors=True)
        window = prepare_window(raw, asof, sessions=15)
        windows[ticker] = window
        snapshot = window.to_csv(index_label="Date")
        name = "".join(c if c.isalnum() or c in "._-" else "_" for c in ticker)
        (output/f"{name}.csv").write_text(snapshot, encoding="utf-8")
        coverage[ticker] = dict(start=str(window.index[0].date()), end=str(window.index[-1].date()), bars=15,
                               sha256=hashlib.sha256(snapshot.encode()).hexdigest())
    if not windows:
        raise ValueError("Ticker list is empty")
    results = []
    text = "# 15 completed trading-session sandbox\n\n"
    text += "Analysis uses only the 15 retained bars, NOT older warmup data. First three bars initialize short rules. "
    text += "No independent holdout. One position, next-open entries, 0.5% modeled risk and 20% notional cap. "
    text += "2R targets, stop below recent three lows, zero commission, per-side slippage. "
    text += "Window-end forced exits are explicit hypothetical sales, not normal strategy exits. "
    text += "Closed-trade drawdown is NOT daily mark-to-market. These tiny samples do not establish an edge.\n\n"
    text += "| Strategy | Hold | Cost bps/side | Trades | Net P&L | Win rate | Longest loss streak | Forced end exits |\n| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    for mode in MODES:
        for hold in (1,2,3):
            for cost in (5.0,15.0):
                journal, summary = simulate(windows, mode, hold, cost)
                trial = f"{mode}_h{hold}_bps{int(cost)}"
                journal.to_csv(output/f"{trial}_journal.csv", index=False)
                results.append(summary)
                rate = "N/A" if summary["win_rate_pct"] is None else f"{summary['win_rate_pct']:.1f}%"
                text += f"| {mode} | {hold} | {cost:g} | {summary['trades']} | {summary['net_pnl']:+,.2f} | {rate} | {summary['max_consecutive_losses']} | {summary['window_end_exits']} |\n"
    manifest = dict(analysis_sessions=15, asof=str(asof), coverage=coverage, trials=42, results=results,
        download_note="Yahoo requests one calendar month, but current/future dates and all but the latest 15 completed bars are discarded BEFORE analysis.",
        limitations="Different strategies/holding/exits from long-history lab; not a like-for-like performance comparison. Current universe selection bias; daily-bar stop-first fills; no live orders; no tuning or winner deployment.")
    (output/"results.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    pd.DataFrame(results).to_csv(output/"all_trials.csv", index=False)
    (output/"summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
