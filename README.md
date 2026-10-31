# ChatGptTrader

# Swing Trading Bot

A Python-based research and signal-generation tool for short-term
swing trading, targeting holding periods of 2–5 trading sessions.

## Features

- Daily historical OHLCV data
- EMA20, SMA50, SMA200, RSI14 and ATR14
- Relative volume and relative strength against SPY
- Breakout continuation strategy
- Trend pullback strategy
- Transparent setup scoring
- Stop, target and position-size calculations
- Ranked CSV reports
- Initial historical simulation framework
- Automated tests and GitHub Actions

## Important limitations

This is research software, not a proven profitable trading system.

- No automatic live orders
- No complete earnings/event calendar yet
- No portfolio-level correlation or exposure engine yet
- Historical data availability and quality depend on the provider
- The initial backtester is a simplified daily-bar simulator
- Position sizing does not guarantee a maximum loss

Do not use its signals as a substitute for independent evaluation.
Test all strategies before risking real capital.

## Requirements

- Python 3.11 or later
- pip
- Internet access for downloading market data

## Installation

Clone your repository, then enter its directory:

    git clone YOUR_REPOSITORY_URL
    cd swing-trading-bot

Create a virtual environment:

    python -m venv .venv

Activate it on macOS/Linux:

    source .venv/bin/activate

Activate it on Windows PowerShell:

    .venv\Scripts\Activate.ps1

Install the dependencies:

    python -m pip install --upgrade pip
    pip install -r requirements.txt
    pip install -e .

## Configure the ticker universe

Edit:

    config/tickers.txt

Put one ticker per line. Lines beginning with # are comments.

## Run the scanner

From the repository root:

    python main.py

Choose another ticker file or output path:

    python main.py --tickers config/tickers.txt --output reports/my_signals.csv

The report contains qualifying candidates, entry references, stops,
targets, scores, estimated share counts and rejection information.

If no candidates qualify, the bot writes an empty report and reports
that no qualifying candidates were found.

## Run tests

    pytest -q

## Strategy overview

### Breakout continuation

- Price above EMA20
- EMA20 above SMA50
- Positive EMA20 slope
- Close above prior 20-session high
- Relative volume at least the configured minimum
- Positive relative strength against SPY
- Price not excessively extended above EMA20
- Market-regime filter passes

### Trend pullback

- Same trend and liquidity filters
- Recent low near EMA20
- Bullish confirmation above the previous session's high
- Valid stop and target calculation

## Risk assumptions

Defaults are defined in `src/swingbot/config.py`.

- Account equity: $25,000
- Risk budget: 0.5% per trade
- Maximum position notional: 20% of equity
- Target: 2R
- Maximum holding period: 5 trading sessions

These are configurable starting assumptions, not optimized recommendations.

## Repository structure

- `data.py`: market-data retrieval and validation
- `indicators.py`: technical features
- `strategies.py`: signal detection
- `risk.py`: position sizing
- `scanner.py`: scanning and report generation
- `backtest.py`: historical simulation
- `tests/`: automated checks

## Development principles

1. Never use future data to generate historical signals.
2. Keep strategy rules deterministic and version-controlled.
3. Track rejected candidates as well as accepted candidates.
4. Include transaction costs in research.
5. Separate signal generation from order execution.
6. Do not enable live execution without independent safety checks.
7. Never commit API keys, passwords or brokerage credentials.

FROM PERPLEXITY OCT 30

## Dated clarification: research baseline and paper execution

The original research documentation above is preserved. The current repository also contains paper-broker, portfolio/reconciliation and exit-safety modules. In particular, the inspected Alpaca paper coordinator is a newer execution path, not merely the original daily scanner. Broker-paper orders are different from hypothetical backtest fills and from real-money orders. This review did not run the coordinator, verify credentials or account identities, inspect broker positions, or establish successful operation or profitability.

## Paper-coordinator configuration inspected

- Workflow: .github/workflows/alpaca-paper-coordinator.yml (Alpaca paper coordinator).
- Configured cron: */5 13-21 * * 1-5, meaning every five minutes during UTC hours 13 through 21, Monday through Friday.
- Manual modes: check, scan and tick. The manual and scheduled defaults select tick. The input description identifies a policy of up to nine PAPER positions, 10% allocation and previous-high targets; this is a declared workflow policy, not a verified actual account state.
- The workflow runs tests/self-tests, loads signal_source at pinned commit f2b5542f892cf1c6f3724ed68d343b4699354541, and invokes python portfolio_runtime.py --mode with the selected mode.
- The job is gated by vars.ALPACA_PAPER_KILL_SWITCH != 'true'. It passes ALPACA_PAPER_ENABLED as literal 'true', not the same-named repository variable. Do not assume setting that repository variable to false disables this coordinator.
- Paper credentials, expected account ID, strategy and data-feed values are supplied separately. Their actual values were not inspected.
- CURRENT ENABLED/DISABLED STATUS: NOT VERIFIED. Workflow source does not establish current workflow activation, repository Actions permissions, kill-switch value, credential validity, or successful scheduled execution.

This repository has additional workflows; the coordinator summary is not an exhaustive inventory of their triggers. In particular, a historical backtest or read-only scan must not be mistaken for broker-paper execution. Review each workflow before dispatching it. Earlier baseline risk defaults above should not automatically be attributed to a newer runner.

## Related projects and manual stop

ChatGptTrader-2K is a related but separate project with its own account/risk design. Other stock-signal repositories also overlap in purpose. Do not assume shared broker accounts, journal state, allocations or risk budgets are safely coordinated.

To stop new coordinator triggers, use Actions > Alpaca paper coordinator > workflow menu > Disable workflow; cancel queued/running runs separately. Other workflows require separate controls. Disabling all Actions in repository settings also stops tests and manual workflows.

Stopping a workflow or setting an entry/execution kill switch does not prove that paper positions were liquidated or broker orders cancelled. It can also stop workflow-managed exit checks. Inspect the paper account and outstanding orders separately.

This append changes documentation only, not code, workflows, enable flags, kill switches, credentials or accounts. Existing push-based CI may run if configured and permitted. This is a dated source-review note, not a continuously updated operational dashboard.
