# Manual strategy experiment

Branch: experiments/trend-pullback-blend. The journal fixes are inherited; the default
scanner is unchanged. This is an experiment, not a proven profitable strategy.

## Rules

Compare deduplicated baseline signals, an experimental 20-EMA trend pullback, and their
union. The blend prefers experimental signals on the same ticker/date. Other baseline
duplicates use score then strategy name. These priorities do not use future returns.

Experimental rules: close > EMA20 > SMA50 > SMA200; rising EMA20; positive relative
strength against SPY; existing price/liquidity/extension/market filters. At least one
of the previous three lows must be within configured 0.5 ATR of its then-current EMA20,
with relative volume below 1. Signal close must exceed previous high and current open,
with relative volume at least 1. Stop: last five lows minus 0.1 ATR. Use existing 2R target,
next-open execution, five-session hold, slippage and commission assumptions.
The constant score 75 is a placeholder, not a probability or calibrated rank.

Trend pullbacks are commonly described, not proven to be the most popular or profitable:
https://www.investopedia.com/terms/s/swingtrading.asp
https://www.lat.london/resources/blog/swing-trading-strategies-beginners-guide/
These sources do not validate the exact thresholds used here.

## Comparison

Run python compare_strategies.py. One download per ticker is shared by all modes and
saved with SHA-256 hashes. Any failed ticker aborts the run. Common signal dates exclude
warmup and leave a full holding window. Latest 20% of eligible dates is a chronological
holdout. Boundary-straddling trades are excluded. Each partition resets starting equity.
No tuning is performed. Reusing holdout after tuning makes it development data.

Equity uses the inherited single-position replay, not the configured five-position
portfolio. Drawdown uses closed trades, not daily mark-to-market. Current constituents
introduce survivorship/selection bias. No earnings filter or opening-gap revalidation.
Daily bars and adjusted historical prices retain the existing simulator limitations.

## Manual workflow

Actions > Run Swing Trading Bot > Run workflow > select experiments/trend-pullback-blend
> Run workflow. Select this branch, not main or the previous improvement branch.
The existing workflow file is reused; the market comparison has only workflow_dispatch,
no push, pull-request, or schedule trigger. The existing separate unit-test workflow
can still run tests automatically. No workflow has been dispatched by this patch.
The job uses read-only repository permissions and a 30-minute timeout, runs tests,
downloads public data, and places no live orders.

Review the job summary and strategy-comparison artifact (14-day retention). Outputs under
reports/strategy_experiment include comparison.md, comparison.json, source OHLCV snapshots,
candidate CSVs, and per-mode/per-partition journal CSVs. Starting/final equity, returns,
win/loss counts, profit factor and closed-trade drawdown are in the comparison JSON;
the Markdown table shows the main equity and drawdown figures.
Run python run_backtest.py locally for the original backtest and journal.
Unit tests are not historical performance results. No historical returns have yet been
verified for this experiment.
