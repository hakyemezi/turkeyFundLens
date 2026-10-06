from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

from turkeyfundlens.data.tefas_client import FetchConfig, fetch_tefas_history

TABLE_GENERAL = "fon_genel_bilgiler"
TABLE_ALLOCATION = "fon_dagilim_bilgileri"


def connect_sqlite(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def create_indexes(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_genel_fon_tarih ON {TABLE_GENERAL} (fonKodu, tarih)"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_dagilim_fon_tarih ON {TABLE_ALLOCATION} (fonKodu, tarih)"
    )
    conn.commit()


def save_full_snapshot(
    db_path: str | Path,
    df_general: pd.DataFrame,
    df_allocation: pd.DataFrame,
    if_exists: str = "replace",
) -> None:
    """Save complete general/allocation DataFrames into SQLite."""
    with connect_sqlite(db_path) as conn:
        if not df_general.empty:
            df_general.to_sql(TABLE_GENERAL, con=conn, if_exists=if_exists, index=False)
        if not df_allocation.empty:
            df_allocation.to_sql(TABLE_ALLOCATION, con=conn, if_exists=if_exists, index=False)
        create_indexes(conn)


def load_from_sqlite(db_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load turkeyFundLens source tables from SQLite."""
    with connect_sqlite(db_path) as conn:
        df_general = pd.read_sql(f"SELECT * FROM {TABLE_GENERAL}", conn)
        df_allocation = pd.read_sql(f"SELECT * FROM {TABLE_ALLOCATION}", conn)
    return df_general, df_allocation


def get_latest_date(
    conn: sqlite3.Connection,
    table_name: str = TABLE_GENERAL,
    date_col: str = "tarih",
) -> Optional[pd.Timestamp]:
    """Return the latest date available in a SQLite table."""
    try:
        value = pd.read_sql(f"SELECT MAX({date_col}) AS max_date FROM {table_name}", conn).iloc[0, 0]
    except Exception:
        return None
    if value is None:
        return None
    return pd.to_datetime(value)


def replace_period_records(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    table_name: str,
    start_date,
    date_col: str = "tarih",
) -> int:
    """
    Replace all records from start_date onward with the supplied DataFrame.

    This is intentionally named as period replacement rather than row-level upsert.
    It is robust for financial data that may receive late corrections.
    """
    if df is None or df.empty:
        return 0

    start_str = pd.to_datetime(start_date).strftime("%Y-%m-%d")
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table_name} WHERE {date_col} >= ?", (start_str,))
    df.to_sql(table_name, con=conn, if_exists="append", index=False)
    return len(df)


def update_sqlite_cache(
    db_path: str | Path,
    start_date=None,
    end_date=None,
    overlap_days: int = 2,
    config: Optional[FetchConfig] = None,
    verbose: bool = True,
) -> dict:
    """
    Fetch data and update a SQLite cache.

    If start_date is omitted, the function reads the latest date in the DB and
    starts overlap_days earlier. If the DB is empty/missing, it starts 5 years ago.
    """
    end = pd.to_datetime(end_date or pd.Timestamp.today()).normalize()

    with connect_sqlite(db_path) as conn:
        latest = get_latest_date(conn)
        if start_date is None:
            if latest is None:
                start = end - pd.DateOffset(years=5)
            else:
                start = latest - pd.DateOffset(days=overlap_days)
        else:
            start = pd.to_datetime(start_date).normalize()

        if verbose:
            print(f"Updating SQLite cache: {start.date()} - {end.date()}")

        df_general, df_allocation = fetch_tefas_history(
            start,
            end,
            config=config,
            verbose=verbose,
        )

        n_general = replace_period_records(conn, df_general, TABLE_GENERAL, start)
        n_allocation = replace_period_records(conn, df_allocation, TABLE_ALLOCATION, start)
        create_indexes(conn)
        conn.commit()

    return {
        "db_path": str(db_path),
        "start_date": start,
        "end_date": end,
        "general_rows_written": n_general,
        "allocation_rows_written": n_allocation,
    }
