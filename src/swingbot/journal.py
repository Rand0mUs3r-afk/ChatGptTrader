"""Cash-funded, single-position journal replay of simulated trade candidates."""
import math

import pandas as pd

COLUMNS = ["ticker", "strategy", "entry_date", "exit_date", "entry", "exit",
           "stop", "target", "exit_reason", "shares", "net_pnl", "net_r_multiple",
           "equity_before", "equity_after"]


def build_journal(trades, settings):
    """Replay one position at a time; no exit-day capital reuse or MTM equity.

    Ties use ticker then strategy, never future returns. Existing simulated
    fills/costs are reused; overlapping candidates are skipped. This is not
    the configured multi-position portfolio or actual brokerage performance.
    """
    equity = float(settings.account_equity)
    risk = float(settings.risk_fraction)
    cap = float(settings.maximum_position_fraction)
    slip = float(settings.slippage_bps) / 10_000
    commission = float(settings.commission_per_share)
    if not all(math.isfinite(x) for x in (equity, risk, cap, slip, commission)):
        raise ValueError("Journal settings must be finite.")
    if equity <= 0 or not 0 < risk <= 0.02 or not 0 < cap <= 1:
        raise ValueError("Invalid journal equity or risk limits.")
    if not 0 <= slip < 1 or commission < 0:
        raise ValueError("Invalid journal trading costs.")
    starting = equity
    rows, skipped = [], 0
    last_exit = None
    if not trades.empty:
        required = {"ticker", "strategy", "entry_date", "exit_date", "entry", "exit",
                    "stop", "target", "exit_reason", "net_pnl_per_share", "net_r_multiple"}
        if required - set(trades.columns):
            raise ValueError("Journal input is missing required trade columns.")
        ordered = trades.copy()
        for column in ("entry_date", "exit_date"):
            ordered[column] = pd.to_datetime(ordered[column], errors="raise")
            if ordered[column].isna().any():
                raise ValueError("Trade dates cannot be missing.")
        numeric = ["entry", "exit", "stop", "target", "net_pnl_per_share", "net_r_multiple"]
        ordered[numeric] = ordered[numeric].apply(pd.to_numeric, errors="raise")
        if not ordered[numeric].map(math.isfinite).all().all():
            raise ValueError("Trade values must be finite.")
        if ((ordered["exit_date"] < ordered["entry_date"]).any()
                or (ordered[["entry", "exit", "stop", "target"]] <= 0).any().any()
                or (ordered["stop"] >= ordered["entry"]).any()):
            raise ValueError("Invalid trade prices or date ordering.")
        ordered = ordered.sort_values(["entry_date", "ticker", "strategy"], kind="stable")
        for trade in ordered.to_dict("records"):
            if equity <= 0 or (last_exit is not None and trade["entry_date"] <= last_exit):
                skipped += 1
                continue
            entry_cost = trade["entry"] * (1 + slip) + commission
            stop_proceeds = trade["stop"] * (1 - slip) - commission
            risk_per_share = entry_cost - stop_proceeds
            shares = max(0, min(math.floor(equity * risk / risk_per_share),
                                math.floor(equity * cap / entry_cost)))
            if not shares:
                skipped += 1
                continue
            pnl = shares * trade["net_pnl_per_share"]
            before = equity
            equity += pnl
            if not math.isfinite(equity):
                raise ValueError("Journal equity exceeds finite numeric range.")
            last_exit = trade["exit_date"]
            row = {key: trade[key] for key in COLUMNS if key in trade}
            row.update(shares=shares, net_pnl=pnl, equity_before=before, equity_after=equity,
                       entry_date=trade["entry_date"].date().isoformat(),
                       exit_date=trade["exit_date"].date().isoformat())
            rows.append(row)
    journal = pd.DataFrame(rows, columns=COLUMNS)
    pnl = journal["net_pnl"].astype(float)
    gross_profit = float(pnl.clip(lower=0).sum())
    gross_loss = float(-pnl.clip(upper=0).sum())
    curve = pd.Series([starting] + [row["equity_after"] for row in rows], dtype=float)
    drawdown = (curve.cummax() - curve) / curve.cummax()
    summary = {
        "mode": "single_position_cash_funded_replay",
        "starting_equity": starting, "final_equity": equity,
        "net_pnl": equity - starting, "return_pct": (equity / starting - 1) * 100,
        "trades": len(rows), "skipped_candidates": skipped,
        "wins": int((pnl > 0).sum()), "losses": int((pnl < 0).sum()),
        "breakeven": int((pnl == 0).sum()),
        "win_rate_pct": float((pnl > 0).mean() * 100) if rows else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "profit_factor_status": "finite" if gross_loss else "no_losses_or_no_trades",
        "max_closed_trade_drawdown_pct": float(drawdown.max() * 100),
        "note": "Simulated; one position at a time; ticker/strategy tie-break; no exit-day reentry. "
                "Equity and drawdown use closed trades only, not daily mark-to-market. "
                "Costs follow the backtest. Not a multi-position portfolio or actual account.",
    }
    return journal, summary


def format_journal(summary):
    """Render a compact Markdown journal, also readable in terminal output."""
    factor = summary["profit_factor"]
    factor_text = f"{factor:.2f}" if factor is not None else "N/A (no losing trades or no trades)"
    rows = [
        ("Starting equity", f"{summary['starting_equity']:,.2f}"),
        ("Final equity", f"{summary['final_equity']:,.2f}"),
        ("Net P&L", f"{summary['net_pnl']:+,.2f}"),
        ("Return", f"{summary['return_pct']:+.2f}%"),
        ("Completed trades", str(summary["trades"])),
        ("Wins / Losses / Breakeven", f"{summary['wins']} / {summary['losses']} / {summary['breakeven']}"),
        ("Win rate", f"{summary['win_rate_pct']:.1f}%"),
        ("Profit factor (position-sized)", factor_text),
        ("Max closed-trade drawdown", f"{summary['max_closed_trade_drawdown_pct']:.2f}%"),
        ("Skipped candidates", str(summary["skipped_candidates"])),
    ]
    return ("# Trading journal - simulated single-position replay\n\n"
            "Amounts use the configured account-equity units.\n\n"
            "| Metric | Result |\n| :--- | ---: |\n"
            + "\n".join(f"| {label} | {value} |" for label, value in rows)
            + "\n\n" + summary["note"] + "\n")
