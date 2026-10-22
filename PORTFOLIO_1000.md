# Current runner configuration: $1,000 account

This configuration supersedes the 25,000 equity / 20% allocation / 0.5% equity-risk values in the older experiment documentation. No strategy signals, stop locations, 2R targets, holding limits, cost assumptions, ticker ordering or data windows change.

Running python run_reclaim_lab.py now explicitly starts each alternative strategy/window/cost account at 1,000, caps entry cost including modeled slippage at 25% of current equity, and caps planned stop risk at 6% of that allocation budget. Initially the allocation budget is 250 and risk ceiling is 15 (1.5% of equity). Both compound with current equity after each closed trade, rather than remaining fixed dollar amounts. Risk is a ceiling, not a target or a forced 6% price stop. Actual risk can be lower; opening gaps can exceed planned risk.

Whole shares only, no leverage, one open position per separate account. Expensive stocks can be skipped when even one share exceeds the allocation cap. Journals record allocation budget, risk budget, position cost and planned stop risk. Unaffordable candidate events are counted, not described as trades. Results can differ from a scaled version of the old account.

Journals include actual held_sessions (entry and exit sessions inclusive) and held_calendar_days (elapsed date difference). An entry-day exit counts as one trading session and zero calendar days. Final report footer includes total trades, wins, losses, breakevens, final equity, net P&L, average/shortest/longest held sessions and average calendar days for each separate trial. Never sum alternative-trial equities or trade counts into one account.

The simulate function retains old default arguments for historical comparisons and existing tests; the command-line runner explicitly passes starting=1000.0, allocation=0.25, risk_fraction=0.06. The existing experiment workflow and main's manual launcher both execute this updated runner. Three new synthetic tests passed locally; full-suite and market-data execution must be verified in Actions. This commit provides code, not fabricated $1,000 performance results.
