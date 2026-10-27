# Previous-high paper policy and rollback

## Preserved baseline

Repository: Rand0mUs3r-afk/ChatGptTrader, main.
Pre-change commit: d21efc0bc804da9a51b579cb22ead3a92a42c93c.
Git stores the full original tree and file contents at that commit; recovery does not depend on chat memory.
The original portfolio_paper.py remains unchanged as the three-slot fixed-2R baseline.

## New policy

The workflow still launches portfolio_runtime.py, which now selects portfolio_previous_high.py.
Maximum allocation is 10% of equity per entry, including the existing cost allowance.
At most nine occupied symbols, counting pending entries, are allowed.
Gross allocation is capped at 90%; combined planned stop risk is capped at 5.4% of equity.
Per-entry planned risk remains 6% of its allocation, or at most 0.6% of equity.
These are ceilings, not required exposure or guaranteed maximum losses.

TP is the most recent confirmed swing high above the proposed entry limit, within the valid history already fetched by ranking (approximately 800 calendar days).
A swing high exceeds both preceding daily highs and is at least both following daily highs; both following bars must already be completed.
Eligible highs are searched in reverse chronological order, not highest-price order.
Targets are rounded down to cents. If no eligible target remains above entry, skip the setup.
No fixed-2R or minimum-R target filter is imposed.
Historical ranking uses the same target selection using only data available through each signal bar; it does not use future pivot confirmation.
The existing seven-session holding exit, structural stops, quote freshness, spread checks, duplicate IDs, paper-account verification, protection verification, and reconciliation retries are retained.
The policy is installed with exact source-shape checks and refuses to run if the preserved implementation changes unexpectedly.

## Files in this change

Added: portfolio_previous_high.py; tests/test_previous_high_policy.py; this document.
Modified: portfolio_runtime.py; .github/workflows/alpaca-paper-coordinator.yml.
No credentials, signals-source checkout, scheduler, or existing broker orders are changed.

## Rollback

Prefer git revert of the single commit that introduced this document. This reverses the policy while preserving subsequent history.
The baseline commit above is also available for comparing or restoring individual files.
Do not reset the entire branch to the baseline if later unrelated changes must be retained.
Reverting code does not undo submitted broker orders or change their stop/target legs.
If more than three symbols remain occupied after rollback, the old capacity guard will stop new activity until the book is reviewed; rollback is not permission to liquidate positions.
Directly running portfolio_paper.py still invokes the preserved old policy; use the workflow's portfolio_runtime.py entrypoint for the new policy.

## Validation

Fourteen target-selection and sizing unit tests passed in the preparation environment.
Two additional repository integration tests validate installation, nine-slot reconciliation, and report constants in CI before the coordinator runs.
The new broker-connected policy has not been verified at commit preparation time.
