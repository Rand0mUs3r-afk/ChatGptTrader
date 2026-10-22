# Recent-weighted swing blend: implemented runner

Run python run_recent_blend.py, optionally --asof YYYY-MM-DD (exclusive) and --output reports/recent_swing_blend. This is new executable code, not the earlier fifteen-bar lab. Existing scripts and branches are unchanged.

## Data and account

Retrieve at most five calendar years of adjusted daily OHLCV before cutoff, excluding the current day. No older warmup. All configured tickers plus SPY must share identical sessions; bad/missing data fails rather than silently dropping instruments. At least 300 sessions required. Provider date availability is not independently exchange-calendar verified. Today's universe and retrospective adjusted prices are not a point-in-time, survivorship-free dataset.

Each trial starts separately at 1,000 after 252 retained training sessions. Allocation cap: 25% of current realized equity; modeled stop-risk ceiling: 6% of that allocation budget (initially 250 allocation, 15 risk). Whole shares, no leverage, one open position per account, no same-day re-entry after exit. Gaps can exceed planned risk. Entries any trading day at the next open using only preceding completed bars. Stops/targets can exit on entry day. Maximum hold variants are five and seven trading sessions inclusive of entry; fifth/seventh-session close if no earlier exit. Final truncated trades are explicitly labeled window_end. Zero commission/cash interest; 5/15 bps adverse slippage per side. Cost scenarios recalculate sizing, weights and trade paths, not just fees on frozen trades. Stop-first daily-bar ambiguity; favorable target gaps capped at target; stops gapping down exit at open. Targets use 2R raw entry-to-stop distance.

## What is mixed

Twelve atomic signals: the five original short rules, failed reclaim, compression breakout, fast breakout/reversal/momentum, bullish engulfing and close strength. Original momentum union, two-vote blend, no-chase reversal and market-gated union remain comparators. Family baselines cover trend, recovery and compression. Close strength is a quality tie-breaker, not an extra independent family vote; it is also reported as an individual baseline.

Balanced and recent blends require at least two distinct families, not several correlated votes from one family. Each family counts once. Stop is the lowest stop among contributing atomic signals. Blends rank candidates by family score, then signal-close location, then ticker; other baselines use ticker priority. Family-attributed P&L is divided equally among contributing families for accounting only, not causal attribution; quality-only trades use an unassigned bucket.

22 configurations x 2 holds x 2 cost levels = 88 alternative accounts. No portfolio totals across alternatives and no automatic winner deployment.

## Causal monthly recent weighting

Separate fixed-rule family shadow portfolios start after four bars and supply completed-trade net P&L divided by actual planned stop risk. Before each evaluation calendar month, use only shadow trades exited strictly before that month's first retained index. Positions open across the boundary and all later exits are excluded. Shadows are precomputed for efficiency, but the weight query is strictly prefix-filtered. The saved weight audit records the last permissible exit index.

Decay is exponential with 126-session half-life. The weighted mean risk multiple is shrunk toward zero by effective sample count / (effective sample count + 20), clipped to [-1,1], exponentiated and normalized. Final weights mix 75% adaptive weights with 25% uniform weights. Insufficient history therefore stays near equal rather than declaring a winner from one trade. Parameters are fixed hypotheses, not optimized on final results. Weights freeze for the month, and realized profits/equity are never recency-weighted. This is monthly forward adaptation with an initial training period, NOT an independently untouched final holdout or a proof of edge. The latest fifteen days were already inspected during strategy development.

## Reports and execution

The summary includes total trades, wins/losses/breakevens, final equity, net P&L, win rate, actual mean/min/max held sessions, daily mark-to-market drawdown and forced exits. Journals include elapsed calendar days, entry/exit dates, votes, family weights, stop risk, exit reasons and equity. Save daily equity, monthly unweighted returns, family accounting contributions, monthly weight audits, skip counts and hashed input snapshots. Daily MTM values positions at close less estimated exit slippage, not intraday drawdown. Monthly and all-history results remain subject to sample size and development bias.

Recent-weighted swing blend workflow automatically runs repository pytest and the real-data runner on pushes affecting these new files on experiments/recent-weighted-swing-blend; reports artifact is recent-weighted-swing-reports. It has a workflow_dispatch declaration for a future separately approved default-branch launcher; this commit does not change main or promise a new Run button. The old Monday workflow still runs the old branch.

Seven new local tests passed. An additional offline synthetic-provider end-to-end execution produced all 88 trial journals/monthly reports with reconciled equities. Full repository CI and real-provider data execution remain unverified until Actions completes. Scalping is explicitly disabled: no intraday coverage or spread/latency execution model has been verified, and same-day daily-bar exits must not be labeled scalping performance.
