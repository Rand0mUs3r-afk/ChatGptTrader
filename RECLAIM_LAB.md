# Frozen reclaim/compression experiment

Research only; no orders, winner deployment, or changes to existing runners and schedules. Run `python run_reclaim_lab.py`; optional exclusive cutoff: `python run_reclaim_lab.py --asof 2026-10-21`. Reports are written to reports/reclaim_lab.

## Fixed comparisons

- reversal2, maximum hold 3: unchanged reversal signal, stop and execution baseline.
- inside_breakout, maximum hold 2: unchanged inside-bar signal, stop and execution baseline.
- failed_reclaim, maximum hold 2: signal low below the previous three lows, bullish close back above that previous minimum and in the upper quarter of today's range; stop below signal low by 10% of signal range.
- compression_breakout, maximum hold 2: previous bar's range strictly smaller than each preceding two ranges; bullish signal close above previous high; stop below previous low by 10% of its range.
- reversal_no_chase, maximum hold 3: same reversal baseline but reject next-open entries more than half the signal range above signal close.
- reversal_compression_union, maximum hold 2: either reversal or compression. Prefer reversal's stop if both qualify. This is the matched ungated comparator.
- market_gated_union, maximum hold 2: identical union, accepted only when SPY's signal-day close exceeds its close three sessions earlier. No entry-day closing data used.
- cash: zero trades, costs, interest and return; not a buy-and-hold benchmark.

Eight configurations, two costs (15 bps primary, 5 bps secondary), two windows (15 sessions primary, final 5 sessions diagnostic): 32 trials, including cash comparisons. No parameter sweep or automatic winner selection. Hybrid comparisons must be against the ungated hybrid, not only reversal with a different hold.

## Controls and limitations

Every strategy requires four completed bars before a next-open entry, keeping readiness consistent. The five-session diagnostic therefore allows only one entry date and is NOT independent of the 15-session sample. It is intentionally not the earlier short-lookback five-session lab. Older downloaded bars are discarded before any signal calculations; no older warmup for SPY either. Current date is excluded even after close. Actual retained dates are recorded, not assumed to match an independently verified exchange calendar.

All configured tickers remain eligible, including SPY/QQQ if already present. SPY is additionally required as benchmark. Missing or mismatched data aborts the run; no silent exclusions. Yahoo may retrieve 60 calendar days, but only 15 retained bars are analyzed and the diagnostic starts afresh from the final five.

Execution preserves alphabetical candidate priority, one long position at a time, 25,000 starting equity per alternative account, 0.5% modeled stop risk, 20% notional cap, next-open entries, 2R targets, zero commission and adverse per-side slippage. Daily-bar ambiguity uses stop-first; opening gaps below stops exit at open, favorable target gaps are capped at target. Gaps may exceed modeled risk. Cost changes can change sizing. No same-day re-entry after an exit.

Forced end exits, their P&L, normal-exit P&L, averages, largest wins/losses, trade counts and loss streaks are reported. Drawdown uses closed-trade equity, not daily mark-to-market. Zero-trade win rate is N/A. No-trade trials do not demonstrate successful trading. Each new stop changes exit behavior as well as entry selection; do not attribute all performance differences solely to entry patterns.

The automated workflow runs pytest, then the backtest, publishes a job summary and uploads reports. It is restricted to pushes affecting these experiment files on experiments/one-week-strategy-lab, or explicit manual dispatch. Network/provider failures remain failures. Seven new synthetic tests passed locally; the full repository suite and real-data results are to be verified in Actions. Tiny samples, current-universe bias, correlated rules and reuse of already inspected data prevent validation claims. Freeze these rules before later untouched-data evaluation.
