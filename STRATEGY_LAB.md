# Broader strategy lab: first screening batch

This patch implements six additional fixed hypotheses, not all items in the research roadmap:
RSI(2)<10 dips above SMA200; lower Bollinger-band dips above SMA200; volatility-compression
20-session breakouts; failed 20-session breakdown/reclaims; gap-down recoveries; and
55-session Donchian breakouts in a positive 20/50 trend. Exact rules are in strategy_lab.py.
These are simplified daily-bar concepts, not reproductions of named published systems.
The existing baseline, experimental, blend, and refined modes are retained as controls.

Run python run_strategy_lab.py. The existing manual Run Swing Trading Bot workflow now
runs this lab on experiments/trend-pullback-blend, not the shorter comparison script.
The earlier comparison remains available as python compare_strategies.py.
Market backtests have no automatic push trigger. Separate unit-test CI is unchanged.
No live orders or automatic winner deployment. The job timeout remains 30 minutes.

The lab requests maximum provider history once per configured ticker, excludes the newest
row conservatively, and records actual dates, row counts, snapshots, and SHA-256 hashes.
There is no guaranteed twenty-year history for every stock. Ticker starts differ; later
listings do not truncate older stocks, and no pre-listing data is fabricated. Evaluation
requires the benchmark's warmup and actual matching sessions, with a common end date.
All new families pass shared minimum price/liquidity checks but do not inherit the
baseline's bullish market filter; their own conditions define their hypothesis.

Ten modes x three holds (5,10,20 sessions) x two per-side slippage assumptions (5,15 bps)
= 60 predeclared trials. Full/development/holdout each have a separate reset-equity replay,
not 180 independent parameter trials. Boundary trades stay only in full. All trials are
saved, not just profitable trials. Costs are repriced using identical raw fills per hold,
and sizing is recomputed with each cost setting. Target remains 2R and structural stop
remains recent five-session low minus 0.1 ATR for comparability; family-specific exits are
NOT implemented yet. A neutral scenario means no signal, not a default trade.

Outputs: research.md, research.json, all_trials.csv, all candidate/journal CSVs and readable
per-trial journals in strategy-lab-results. Journals include money totals, rates, streaks,
entry reasons and signal evidence. The lab does not rank or deploy a claimed winner.

Limitations: single position, normally capped at 20% equity, no daily mark-to-market,
current-stock-universe survivorship bias, adjusted provider prices, no earnings or opening
gap revalidation, daily-bar fill assumptions, and common rather than family-specific exits.
Current chronological holdout is no longer credibly untouched after repeated inspection.
This is screening, not walk-forward validation or multiple-testing-corrected evidence.
Cross-sectional rotation, random-entry/passive controls, a multi-position MTM simulator,
and independent validation remain future work. This patch does not claim those are done.
No market-performance results were verified while preparing this commit.

Research context (not proof of these thresholds):
https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
https://www.quantifiedstrategies.com/rsi-2-strategy/
https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
