from __future__ import annotations

import argparse

from turkeyfundlens.config import DEFAULT_DB_PATHS, FUND_TYPE_PENSION, FUND_TYPES
from turkeyfundlens.data.tefas_client import FetchConfig, fetch_tefas_history
from turkeyfundlens.storage.sqlite_store import save_full_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch historical TEFAS fund data and save it to SQLite.")
    parser.add_argument("--start", required=True, help="Start date, e.g. 2021-06-15")
    parser.add_argument("--end", required=True, help="End date, e.g. 2026-06-15")
    parser.add_argument(
        "--fund-type",
        choices=FUND_TYPES,
        default=FUND_TYPE_PENSION,
        help="EMK for pension (BES) funds, YAT for securities investment funds",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite database path. Defaults to a separate file per fund type, "
             "since this replaces the tables it writes.",
    )
    parser.add_argument("--timeout", type=int, default=40)
    parser.add_argument("--max-retries", type=int, default=5)
    args = parser.parse_args()

    db_path = args.db_path or DEFAULT_DB_PATHS[args.fund_type]
    config = FetchConfig(timeout=args.timeout, max_retries=args.max_retries, fund_type=args.fund_type)
    df_general, df_allocation = fetch_tefas_history(args.start, args.end, config=config, verbose=True)
    save_full_snapshot(db_path, df_general, df_allocation, if_exists="replace")
    print(f"Saved general rows: {len(df_general):,}")
    print(f"Saved allocation rows: {len(df_allocation):,}")
    print(f"Database path: {db_path}")


if __name__ == "__main__":
    main()
