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
