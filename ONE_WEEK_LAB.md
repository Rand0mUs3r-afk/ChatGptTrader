# Strict five-session strategy lab

Manual research only. This branch adds files; it does not replace the 15-session runner, alter scheduled workflows, deploy a winner, or submit orders.

## Run

```sh
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -p 'test_one_week_lab.py'
python run_one_week.py
# Optional historical cutoff (exclusive):
python run_one_week.py --asof 2026-10-21 --output reports/one_week_2026_10_21
```

The default excludes the current New York calendar date even after market close. One week means five completed daily sessions, not necessarily Monday-Friday. The downloader requests up to 45 calendar days for retrieval reliability, then discards everything except five completed bars BEFORE signal calculations. No older indicator warmup is used. All tickers must share the same five dates or the run fails. Exact dates and input hashes are recorded. Availability is based on the provider's bars, not independently verified against an exchange calendar.

## Experiments

16 strategies x 3 maximum holding periods (1/2/3 sessions) x 2 slippage assumptions (5/15 bps per side) = 96 trials.

- Original rules: breakout3, momentum3, reversal2, dip_rebound3, inside_breakout. Original four-bar readiness is preserved, so they can enter only on the fifth session.
- Short rules: fast_breakout (bullish close above previous high), fast_reversal (same with a bearish preceding candle), fast_momentum (bullish close above previous close), bullish_engulfing (bearish previous body engulfed by bullish current body), close_strength (bullish close in the upper quarter of its daily range). These require at least two completed bars.
- momentum_union: either original breakout or momentum.
- two_vote_blend: at least two original rules.
- recovery_union: any fast_reversal, bullish_engulfing, or original dip_rebound3.
- trend_confirm: both fast_momentum and close_strength.
- fast_two_vote: at least two short rules.
- reversal_inside_union: either original reversal2 or inside_breakout.

Votes overlap and are correlated; more votes do not imply independent evidence or a known higher win probability. Rules and thresholds are fixed hypotheses, not automatically fitted to this week.

## Execution and outputs

Each trial starts separately at 25,000 with one long position at a time, next-open entries, 0.5% modeled stop risk, 20% notional cap, zero commission, and adverse per-side slippage. Gaps can exceed modeled risk. Stops use the lowest available low in the last up-to-three completed bars minus 10% of their average range; targets are twice the raw entry-to-stop distance. Daily bars use stop-first when both levels are touched; target gaps are conservatively capped at target. No same-day re-entry after an exit. Candidates rank by matching vote count, then signal-bar close location, then ticker. All ranking inputs precede entry. This differs from the original alphabetical selection, so it is not a controlled comparison of window length alone.

At most three entry dates are available, often fewer. Holdings truncated by the window are liquidated at the final close and labeled window_end unless a stop/target already exited them. A normally scheduled final-day time exit is not counted as forced.

Reports include retained input CSVs/hashes, all 96 summaries, per-trial journals, average win/loss/trade, largest gain/loss, losing streak, and forced versus normal exit P&L. Higher-cost trials are displayed first, ranked by net P&L within each cost group. Zero-trade win rates are N/A. Sizing is recalculated with costs, so cost comparisons are not necessarily fee-only differences. Drawdown is closed-trade equity drawdown, NOT daily mark-to-market. No profits or win rates are combined across alternative trials.

This tiny, current-universe, non-holdout experiment cannot validate an edge. Many trials on one week increase selection risk. Synthetic tests check mechanics, not profitability or market-data access. No real-market backtest results are included in this commit.
