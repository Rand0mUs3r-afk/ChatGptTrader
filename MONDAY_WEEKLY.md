# Corrected experiment: daily entries, maximum five trading sessions

This replaces the earlier mistaken Monday-only interpretation on experiments/monday-weekly-hold. The branch name, script filename run_monday_weekly.py, workflow name Monday weekly hold experiment, report directory and artifact name remain for compatibility with the existing manual launcher. No main or other branch changes are made. The actual report heading is Daily-entry experiment — maximum five trading sessions, and results.json identifies daily_entry_max_five_sessions.

## Intended behavior

Enter on ANY trading day at the next open after a qualifying completed-bar signal. No Monday-only filter, previous-Friday requirement, complete-calendar-week requirement or same-week re-entry ban. One position per account; no same-day re-entry after an exit. Another qualifying next-open trade can be taken on a later day of the same week.

Hold for at most FIVE trading sessions, counting entry as session one. Stops or 2R targets can exit earlier. Otherwise close at the fifth session's close. With no holidays: Monday to Friday; Tuesday to next Monday; Wednesday to next Tuesday. Weekends do not count as trading sessions; sessions present in the aligned market data do. Strategy setup formulas, no-chase and SPY gates, stops, target definitions, alphabetical selection and cost assumptions are unchanged.

The analysis retains only fifteen completed sessions, excludes the current date, and uses four-bar signal readiness with no older warmup. Entries near the final data boundary remain permitted, as in the original daily-entry engine. If their normal maximum exit lies outside the window, liquidate at the final retained close and label window_end unless an earlier stop/target has already exited. Report forced P&L separately; a truncated final trade is not evidence of a completed five-session holding cycle.

## Portfolio and outputs

Each of eight configurations (including cash), at two per-side costs (15 bps primary, 5 bps secondary), starts separately at 1,000: sixteen trial accounts. Allocation cap is 25% of current equity; planned stop-risk ceiling is 6% of that allocation budget, initially 250 allocation and 15 risk. Whole shares, no leverage. Actual risk/allocation can be lower; gaps can exceed planned stop risk. Cash is zero return/interest and N/A win rate, not a successful trading strategy.

Final footer retains trades taken, wins/losses/breakevens, final equity, net P&L and average/min/max actual holding sessions plus average calendar days. Journals retain sizing budgets, planned risk, entry and exit dates, exit reason, holding sessions and calendar days. Same-day exits count as one session and zero elapsed days. Forced-exit count/P&L are displayed before the footer. Alternative trial accounts must not be combined into one portfolio.

all_trials.csv and results.json include diagnostic counts for occupied versus available entry dates, no-setup candidates, invalid opens, no-chase rejections, unaffordable whole shares and risk-size rejections. Candidate counts apply only until the first accepted alphabetical candidate on available dates; they are not an exhaustive scan or independent signals. A missing setup can include a failed benchmark gate. There is no week_eligibility.csv in the corrected experiment. For local runs, use a fresh output directory to avoid confusing old weekly artifacts with new results.

Run python run_monday_weekly.py, optionally --asof YYYY-MM-DD (exclusive). In Actions use the existing Monday weekly hold experiment manual launcher with main selected; it checks out this corrected branch. The branch-specific push workflow also runs when these files change. New reports remain in monday-weekly-hold-reports.

Five local synthetic regression tests passed using the shared signal functions. The full repository suite and real-data execution remain to be verified in Actions. Tiny samples, reused development data, current-universe bias, zero commissions and conservative stop-first daily-bar fills prevent validation claims. No market-data performance is fabricated by this change.
