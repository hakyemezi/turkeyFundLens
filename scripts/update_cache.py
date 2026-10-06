from __future__ import annotations

import argparse

from turkeyfundlens.config import DEFAULT_DB_PATHS, FUND_TYPE_PENSION, FUND_TYPES
from turkeyfundlens.data.tefas_client import FetchConfig
from turkeyfundlens.storage.sqlite_store import update_sqlite_cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally update a SQLite TEFAS fund cache.")
    parser.add_argument(
        "--fund-type",
        choices=FUND_TYPES,
        default=FUND_TYPE_PENSION,
        help="EMK for pension (BES) funds, YAT for securities investment funds",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite database path. Defaults to the file for the chosen fund type.",
    )
    parser.add_argument("--start", default=None, help="Optional explicit start date")
    parser.add_argument("--end", default=None, help="Optional explicit end date")
    parser.add_argument("--overlap-days", type=int, default=2)
    args = parser.parse_args()

    info = update_sqlite_cache(
        db_path=args.db_path or DEFAULT_DB_PATHS[args.fund_type],
        start_date=args.start,
        end_date=args.end,
        overlap_days=args.overlap_days,
        config=FetchConfig(fund_type=args.fund_type),
        verbose=True,
    )
    print(info)


if __name__ == "__main__":
    main()
