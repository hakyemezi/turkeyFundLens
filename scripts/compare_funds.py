from __future__ import annotations

import argparse

from turkeyfundlens.workflows import compare_funds_from_sqlite
from turkeyfundlens.core.engine import selected_funds_report_to_markdown, save_markdown_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare selected pension funds from SQLite cache.")
    parser.add_argument("--db-path", default="data/turkeyfundlens.sqlite")
    parser.add_argument("--funds", required=True, help="Comma-separated fund codes, e.g. AAJ,MHD,MEA")
    parser.add_argument("--lookback", default="1m")
    parser.add_argument("--language", choices=["en", "tr"], default="en")
    parser.add_argument("--output", default=None, help="Optional markdown output path")
    args = parser.parse_args()

    fund_codes = [code.strip().upper() for code in args.funds.split(",") if code.strip()]
    comparison_df = compare_funds_from_sqlite(
        db_path=args.db_path,
        fund_codes=fund_codes,
        lookback=args.lookback,
        sort_by="market_effect_pct",
        ascending=False,
    )
    markdown = selected_funds_report_to_markdown(comparison_df, language=args.language)
    print(markdown)
    if args.output:
        save_markdown_report(markdown, args.output)
        print(f"Report saved: {args.output}")


if __name__ == "__main__":
    main()
