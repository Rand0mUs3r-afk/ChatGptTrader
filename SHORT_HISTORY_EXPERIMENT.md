# Separate 15-session experiment

This branch preserves the earlier experiment files but its manual Run Swing Trading Bot
workflow runs python run_short_history.py. Main and experiments/trend-pullback-blend are
not modified by this patch. Nothing is auto-merged, dispatched, tuned, or live-traded.

Analysis uses exactly 15 completed daily bars per configured trading ticker, excluding
SPY as in the old universe. It means TRADING SESSIONS, not calendar days. Yahoo's 1mo
request may return more rows; the runner excludes the current New York date and keeps
only the last 15 BEFORE any features or performance calculations. Snapshots contain only
those 15 rows. All tickers must share exactly the same dates. No older indicator data.

The first signal can use four bars and enter on bar five. Hypotheses:
- breakout3: close above the previous three highs and above current open.
- momentum3: close above the close three sessions earlier and previous close.
- reversal2: previous close declined from its predecessor; current close exceeds prior
  high and current open.
- dip_rebound3: close below prior three-close mean minus half the prior average range,
  but above current open.
- inside_breakout: previous high/low strictly inside its predecessor's range, followed
  by close above previous high and current open.
- union: any rule qualifies; fixed priority is the listed base-rule order.
- consensus: at least two rules qualify; votes share data and are NOT independent.

All seven modes x holds 1/2/3 x per-side slippage 5/15bps = 42 predeclared trials.
No trained probabilities or parameter search. Entry next open; stop below latest three
lows by 0.1 of prior three-bar average range; target 2R from actual raw opening price.
Stop-first if a daily bar touches both levels. Gap stops exit at open; gap targets at
specified target. Whole-share sizing includes modeled costs in estimated stop risk,
with inherited equity/risk/notional caps. Gaps can exceed planned risk.
One cash-funded position; ties alphabetically by ticker; no exit-day reentry.

There is NO final-20-session entry exclusion. At endpoint, positions not naturally exited
remain OPEN. Realized P&L uses both-side costs; unrealized P&L uses final raw close less
entry cost, without hypothetical exit costs. Win/loss rates and streaks use CLOSED trades
only (N/A if none). Breakeven resets streaks. Daily-close equity includes open positions;
maximum drawdown is daily-close, not intraday. Do not compare directly with old closed-only
results. No development/holdout split: 15 bars cannot establish independent validation.

Artifacts: research.json, all_trials.csv, 15-bar input snapshots, closed journals with
reasons, separate open positions, and daily equity CSVs. Manual only; 30-minute timeout.
Archive below is a transcription of the prior one-month full-result money totals/trade
counts, NOT an archive of original price data, every partition, or individual old trades.
Keep/download the original workflow ZIPs to preserve those. Archive source commit was
e6b36557c69b08a5b7d6eb005a061b600fc18b09. No market backtest was run while preparing this patch.

This is a new exploratory engine, not a profitable-system claim. Current-universe bias,
adjusted prices, approximate daily-bar fills, tiny sample size, missing event controls,
and lack of independent validation remain. One-week stage is not prepared or run yet.
