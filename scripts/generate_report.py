from __future__ import annotations

import argparse

from turkeyfundlens.workflows import run_universe_analysis_from_sqlite
from turkeyfundlens.core.engine import save_markdown_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate turkeyFundLens market narrative report from SQLite cache.")
    parser.add_argument("--db-path", default="data/turkeyfundlens.sqlite")
    parser.add_argument("--lookback", default="1m")
    parser.add_argument(
        "--start",
        default=None,
        help="Measure from this date instead of over --lookback, e.g. 2026-09-17",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Measure up to this date instead of the latest in the cache",
    )
    parser.add_argument(
        "--include-unpublished",
        action="store_true",
        help="Keep days TEFAS lists a fund without a valuation (zero price, or no "
             "units in circulation) as published, rather than dropping them",
    )
    parser.add_argument("--language", choices=["en", "tr"], default="en")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--output", default="sample_reports/market_report.md")
    args = parser.parse_args()

    result = run_universe_analysis_from_sqlite(
        db_path=args.db_path,
        lookback=args.lookback,
        language=args.language,
        top_n=args.top_n,
        start_date=args.start,
        end_date=args.end,
        include_unpublished=args.include_unpublished,
    )
    save_markdown_report(result["markdown"], args.output)
    print(f"Report saved: {args.output}")


if __name__ == "__main__":
    main()
