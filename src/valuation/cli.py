"""Command-line interface for the valuation toolkit."""
from __future__ import annotations

import argparse
import sys

from .config import load_assumptions
from .data.base import DataError
from .pipeline import value_ticker
from .reporting import console, excel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="equity-dcf",
        description="Build a three-statement model and DCF valuation for a stock.",
    )
    parser.add_argument("ticker", help="Equity ticker symbol, e.g. AAPL")
    parser.add_argument(
        "-c", "--config", metavar="PATH",
        help="YAML assumptions file (defaults to packaged assumptions).")
    parser.add_argument(
        "-p", "--provider", default="yfinance", choices=["yfinance", "fmp"],
        help="Data provider (default: yfinance, no API key required).")
    parser.add_argument(
        "-o", "--excel", metavar="PATH",
        help="Write a formatted Excel workbook to PATH.")
    parser.add_argument(
        "--api-key", help="API key for providers that require one (e.g. fmp).")
    parser.add_argument(
        "--no-print", action="store_true",
        help="Suppress the console report (useful with --excel).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    assumptions = load_assumptions(args.config)

    provider_kwargs = {}
    if args.provider == "fmp" and args.api_key:
        provider_kwargs["api_key"] = args.api_key

    try:
        run = value_ticker(
            args.ticker, assumptions=assumptions,
            provider=args.provider, **provider_kwargs)
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # surface modeling/validation errors cleanly
        print(f"error: {exc}", file=sys.stderr)
        return 1

    model, result = run.model, run.result
    fcf = model.free_cash_flow_to_firm()

    # Warn if the balance sheet does not tie out (should be ~0 by construction).
    imbalance = model.balance_check()
    if (imbalance > 1.0).any():
        print("warning: balance sheet did not tie out within tolerance.",
              file=sys.stderr)

    if not args.no_print:
        print(console.render(
            run.financials, model.income_statement, model.balance_sheet,
            model.cash_flow_statement, fcf, result))

    if args.excel:
        path = excel.export(
            args.excel, run.financials, model.income_statement,
            model.balance_sheet, model.cash_flow_statement, fcf, result)
        print(f"\nExcel workbook written to: {path}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
