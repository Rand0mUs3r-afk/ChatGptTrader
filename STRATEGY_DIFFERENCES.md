# Strategy differences and refined confluence

Development is the earlier 80% of shared eligible signal dates; holdout is the later
20%. Full is a separate complete replay. These are partitions, not strategy names.
Refinement below is a fixed hypothesis, not optimization from observed development P&L.
Development results have not been supplied to this patch or verified from Actions.

## Original strategies

Baseline has two entry setups. Both require close > EMA20 > SMA50, positive five-session
EMA20 slope, positive 20-session return relative to SPY, liquidity/price/extension filters,
and (by default) SPY close > EMA20 > SMA50. Default signal relative volume is at least 1.5.

- Breakout: close above the prior 20-session high (excluding current session).
- Pullback: current low within configured 0.5 ATR of current EMA20, close above previous
  high and previous open. This does not explicitly require close above CURRENT open.
- Baseline uses its existing heuristic score; default minimum score is 65. This is not
  a probability and is not calibrated by the comparison.

Experimental: close > EMA20 > SMA50 > SMA200, positive slope/relative strength and shared
liquidity/regime/extension constraints. A low near EMA20 on at least one of the previous
three sessions must coincide with relative volume below 1. Current close must exceed
previous high and CURRENT open, with current relative volume at least 1. Score 75 is a
placeholder, not comparable evidence of predictive confidence.

## Two different ways to combine them

- Existing blend (OR): take either source. Experimental has priority on same-stock/date
  collisions; baseline otherwise uses score then strategy-name tie breaking.
- Refined confluence (AND): require at least one baseline signal AND an experimental
  signal on the SAME stock and signal date. Reject mismatched inputs. Retain one
  experimental entry/stop/target plan, label refined_confluence, and log both reasons.
  Do not add heuristic scores or open two positions. Under defaults this inherits
  baseline volume >=1.5, experimental long-term trend, a prior quiet EMA touch, and
  bullish recovery. It may agree with a breakout, a baseline pullback, or both.

Both selectors deduplicate stock/date candidates. Portfolio replay still selects by
entry date then ticker then strategy; it does NOT globally rank stocks by signal score.
All modes retain the existing stop (five-session low minus 0.1 ATR), next-open simulator,
2R target and five-session maximum hold by default, costs and cash-funded single-position
journal. A gap changes entry risk/target in the existing simulator; no new gap filter exists.

## Evaluation

The existing manual Run Swing Trading Bot workflow now compares baseline, experimental,
blend, and refined, on identical downloaded snapshots, costs, dates and risk settings.
Each mode has full/development/holdout journals with money totals, rates, streaks and reasons.
Check refined_development_journal.md and refined_holdout_journal.md in the artifact.
Do not sum partitions or modes: they are alternative independent replays.

There is no demonstrated improvement in returns, win rate, drawdown or streaks yet.
Fewer candidate signals do not guarantee fewer accepted trades or better outcomes because
portfolio conflicts can change. The sources share indicators: agreement is correlated,
not independent evidence. Do not tune against holdout results; repeated inspection after
changes makes that period development data. A current constituent universe, daily bars,
missing earnings controls, and closed-trade-only equity remain important limitations.
The scanner default, main branch, and manual-only market-backtest trigger are unchanged.
