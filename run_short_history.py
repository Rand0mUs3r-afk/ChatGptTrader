"""Manual 15-session lab: no market observations outside the retained window."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import yfinance as yf

from swingbot.config import DEFAULT_SETTINGS
from swingbot.short_history import MODES, run_trial


def main():
    output = Path("reports/short_history_15")
    output.mkdir(parents=True, exist_ok=True)
    symbols = []
    for line in Path("config/tickers.txt").read_text().splitlines():
        ticker = line.split("#", 1)[0].strip().upper()
        if ticker and ticker != DEFAULT_SETTINGS.benchmark and ticker not in symbols:
            symbols.append(ticker)
    if not symbols:
        raise ValueError("No trading tickers configured")
    today = pd.Timestamp.now(tz="America/New_York").date()
    panel, coverage = {}, {}
    for ticker in symbols:
        raw = yf.Ticker(ticker).history(period="1mo", interval="1d", auto_adjust=True, actions=False, raise_errors=True)
        raw = raw.loc[raw.index.date < today]
        # Truncate BEFORE any feature calculations, validation statistics, or replay.
        bars = raw[["Open", "High", "Low", "Close", "Volume"]].tail(15).copy()
        bars.index = pd.DatetimeIndex(bars.index).tz_localize(None).normalize()
        if len(bars) != 15:
            raise ValueError(f"{ticker}: need exactly 15 completed daily bars")
        panel[ticker] = bars
        text = bars.to_csv(index_label="Date")
        name = "".join(c if c.isalnum() or c in "._-" else "_" for c in ticker)
        (output / f"{name}.csv").write_text(text, encoding="utf-8")
        coverage[ticker] = dict(start=str(bars.index[0].date()), end=str(bars.index[-1].date()),
                               bars=15, sha256=hashlib.sha256(text.encode()).hexdigest())
    dates = next(iter(panel.values())).index
    if any(not bars.index.equals(dates) for bars in panel.values()):
        raise ValueError("Tickers must share the same 15 sessions; refusing different evaluation windows")
    results = []
    for mode in MODES:
        for hold in (1, 2, 3):
            for cost in (5.0, 15.0):
                settings = replace(DEFAULT_SETTINGS, slippage_bps=cost)
                closed, opened, daily, summary = run_trial(panel, mode, hold, settings)
                trial = f"{mode}_h{hold}_bps{int(cost)}"
                closed.to_csv(output / f"{trial}_closed.csv", index=False)
                opened.to_csv(output / f"{trial}_open.csv", index=False)
                daily.to_csv(output / f"{trial}_equity.csv", index=False)
                results.append(summary)
    note = ("15 COMPLETED TRADING SESSIONS, not 15 calendar days. Provider request is one month, "
            "but only the retained 15 bars enter calculations or snapshots. Current-day bars excluded conservatively. "
            "First four bars establish signals; earliest entry is the fifth bar. New short-lookback hypotheses, "
            "not the earlier 200-day strategies. No 20-session entry exclusion. Single-position next-open entries, "
            "stop-first daily-bar handling, 2R targets, cash/risk caps, no exit-day reentry. "
            "Open positions marked at final close WITHOUT hypothetical exit costs; excluded from win/loss rates. "
            "Drawdown is daily-close marked-to-market, not intraday. 42 predeclared trials, no tuning, "
            "no holdout, no proven edge, no live orders. Not directly comparable with the old closed-trade-only engine.")
    manifest = dict(window="15_trading_sessions", coverage=coverage, trial_count=len(results),
                    settings=dict(account_equity=DEFAULT_SETTINGS.account_equity,
                                  risk_fraction=DEFAULT_SETTINGS.risk_fraction,
                                  maximum_position_fraction=DEFAULT_SETTINGS.maximum_position_fraction,
                                  commission_per_share=DEFAULT_SETTINGS.commission_per_share),
                    results=results, note=note)
    (output / "research.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    pd.DataFrame(results).to_csv(output / "all_trials.csv", index=False)
    text = "# 15-session short-history experiment\n\n" + note + "\n\n"
    text += f"Data: {dates[0].date()} through {dates[-1].date()}.\n\n"
    text += "| Mode | Hold | Cost bps/side | Closed | Open | Realized P&L | Unrealized P&L | Return | Closed win rate |\n| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    for row in sorted(results, key=lambda r: r["return_pct"], reverse=True):
        rate = "N/A" if row["win_rate_pct"] is None else f"{row['win_rate_pct']:.1f}%"
        text += (f"| {row['mode']} | {row['hold']} | {row['slippage_bps']:g} | {row['closed_trades']} | "
                 f"{row['open_positions']} | {row['realized_pnl']:+.2f} | {row['unrealized_pnl']:+.2f} | "
                 f"{row['return_pct']:+.2f}% | {rate} |\n")
    (output / "research.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
