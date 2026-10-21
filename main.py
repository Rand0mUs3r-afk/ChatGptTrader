
import argparse
import logging
import sys

from swingbot.config import DEFAULT_SETTINGS
from swingbot.scanner import load_tickers, save_report, scan_market


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily swing-trading research scanner"
    )
    parser.add_argument(
        "--tickers",
        default="config/tickers.txt",
        help="Path to a ticker file",
    )
    parser.add_argument(
        "--output",
        default="reports/signals.csv",
        help="Path to the CSV report",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        tickers = load_tickers(args.tickers)
        if not tickers:
            raise ValueError("Ticker list is empty.")

        report = scan_market(tickers, DEFAULT_SETTINGS)
        path = save_report(report, args.output)

        if report.empty:
            print("No qualifying candidates found.")
        else:
            columns = [
                "ticker",
                "strategy",
                "score",
                "entry",
                "stop",
                "target",
                "reward_risk",
                "shares",
                "eligible",
            ]
            print(report[columns].to_string(index=False))

        print(f"\nReport saved to: {path}")
        return 0

    except Exception as exc:
        logging.exception("Scanner failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
