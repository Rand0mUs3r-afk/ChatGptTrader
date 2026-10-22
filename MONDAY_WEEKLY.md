# Isolated Monday-entry weekly-hold experiment

All additions are on experiments/monday-weekly-hold, branched from the $1,000 experiment at cfb425f80954a37a8d9bcdb8e101b54aa5461a3b. No other branch, existing runner or main launcher is edited. Run python run_monday_weekly.py, optionally with --asof YYYY-MM-DD (exclusive).

## Rules

The eight inherited configurations, including cash, are each compared with Thursday-close and Friday-close scheduled exits at 5/15 bps per side: 32 separate trials. Original 2/3-session holding limits are replaced only in this new runner. Strategy signals and stop/2R target definitions are reused unchanged. Monday-open entries use the preceding Friday's completed history and benchmark information, never Monday's closing/high/low data to select the entry. Alphabetical candidate priority remains. No qualifying or affordable signal means no trade that week.

Four-session normal schedule: Monday open to Thursday close (three elapsed calendar days). Five-session normal schedule: Monday open to Friday close (four elapsed calendar days). Stops/targets may exit earlier; daily ambiguity is stop-first, stop gaps exit at open and favorable target gaps are capped at target. Once exited, stay in cash until another eligible Monday. No Tuesday replacement entries and no re-entry later in the same week.

Both exit variants require a complete retained Monday-Friday week and the preceding Friday with at least four retained signal bars. Any missing weekday or an incomplete terminal week is skipped, even if Thursday itself is present. There is no shortened-window forced exit, no shifted holiday entry and no performance-based week exclusion. Eligibility is checked from available dates, not an independently verified exchange calendar. Missing Mondays do not create schedule rows. Other skipped Mondays and reasons are listed in week_eligibility.csv.

## Account and reports

Each alternative account starts at 1,000. Allocation is at most 25% of current equity; planned stop-risk ceiling is 6% of that budget (initially 250 allocated, 15 risk). Whole shares, no leverage, one position at a time. Actual allocation/risk can be smaller; gaps can exceed planned risk. Both budgets update after realized P&L. Costs and stops affect which whole-share trades fit.

Final summary includes total trades, wins, losses, breakevens, final equity, net P&L and actual average/minimum/maximum holding sessions plus average calendar days. Journals include signal/entry/scheduled and actual exit dates, exit reasons, entry/exit fills, planned stop risk and holding durations. Entry/exit sessions count inclusively; same-day exits are one session and zero elapsed days. All retained input hashes and eligible weeks are saved. Never aggregate alternative trials as one portfolio.

Analysis uses only the latest 15 retained completed sessions; older download data is discarded before signals. The current date is always excluded. There may be only one or two eligible Mondays, so zero/few trades cannot validate a strategy. No independent holdout, live orders, commissions, cash interest or fractional shares. Current-universe and daily-bar limitations remain.

## Workflow

Monday weekly hold experiment runs automatically on pushes affecting its four experiment files on this new branch. It installs dependencies, runs the full pytest suite, runs the market-data experiment, publishes a summary, and uploads monday-weekly-hold-reports. This new workflow does not add a Run workflow button on main; no main changes are authorized. The old Frozen reclaim compression lab launcher continues to run the older branch, not this weekly experiment.

Five local synthetic scheduling/portfolio tests passed using the shared signal functions; full-repository CI and real market-data results remain to be verified. No historical profit result is claimed by this code commit.
