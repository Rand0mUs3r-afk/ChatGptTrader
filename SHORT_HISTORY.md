# Separate short-history sandbox

Branch: experiments/short-history-15-sessions. The old experiment branch and main are unchanged.
This is a NEW strategy family experiment, not the old 200-day setups on insufficient history.
The latest 15 completed DAILY trading sessions are analyzed, not 15 calendar days. Yahoo
requests one month to obtain those sessions; current/future dates and all earlier bars
are discarded before any indicator/signal calculation. No older warmup is used. The current
New York calendar date is excluded conservatively even if its exchange session has ended.
All tickers must have identical retained dates or the replay fails rather than mixing periods.

Five fixed long-only rules: bullish close above prior three highs; three rising closes
with a bullish current candle; bearish previous candle followed by close above its high;
rebound after previous close is below its prior-three mean minus one population standard
deviation; and breakout above an inside candle. First three bars initialize these rules.
Two fixed blends: union of breakout/momentum, and at least two of the five rules agreeing.
No parameter tuning, learned weights, or claimed probability calibration.

Seven modes x 1/2/3-session maximum holds x 5/15 bps per side = 42 reported trials.
Next-open entries, no same-day signal-close fills. Stop is lowest low of the signal's latest
three bars minus 10% of their average high-low range. Target is 2x actual open-to-stop risk.
Risk sizing uses entry/stop slippage, 0.5% equity risk budget, 20% notional cap, zero commission.
One position per trial, no reuse of capital on an exit session. Alphabetical ticker tie-break.
Daily stop/target ambiguity is stop-first. A gap below stop fills at open. No short trades.

IMPORTANT new end policy: a position still running when the 15 retained bars end is
hypothetically sold at the final close with costs. Such sales have exit_reason=window_end
and are counted separately. No future prices are assumed. This is not the prior lab's
20-session exclusion policy, and results are NOT directly comparable to that lab.
Drawdown is closed-trade only, not daily account value. No independent holdout is claimed.
A handful of trades cannot establish a live edge. Current-universe selection bias remains.

Actions > Run Swing Trading Bot > Run workflow > choose experiments/short-history-15-sessions.
Market tests are manual-only; unit-test CI may run on push. No workflow is dispatched by
this commit. Artifact: short-history-15-results (14-day retention), including retained
bars, all 42 summaries, journals with reasons and equity, and hashes/date coverage.

archive/previous_results_selected.csv records selected full-period summary P&Ls transcribed
from the user's pasted logs, at 15-bps costs and starting equity 25000. It is NOT a complete
original result archive. Original ZIPs, raw old prices and individual old trade journals
have not been saved here; retain the earlier Actions artifacts separately. The two-year
label means downloaded history including warmup, not two full years of evaluated signals.
One-year/six-month/one-month windows overlap and are not independent tests.
The one-week stage is not implemented or enabled; wait for the user's 15-session upload.
