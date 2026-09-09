from __future__ import annotations

from pathlib import Path

import pandas as pd

from besfundlens.data.tefas_client import FetchConfig, fetch_tefas_history
from besfundlens.storage.sqlite_store import load_from_sqlite


def load_from_csv(general_path: str | Path, allocation_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_csv(general_path), pd.read_csv(allocation_path)


def load_from_parquet(general_path: str | Path, allocation_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_parquet(general_path), pd.read_parquet(allocation_path)


# turkeyfundsdata returns one merged frame with upper-cased column names, since
# it is built for people reading a spreadsheet rather than for this engine. The
# engine wants the two endpoints kept apart and named as TEFAS names them, so
# the columns are mapped back on the way in.
TURKEYFUNDSDATA_GENERAL = {
    "TARIH": "tarih",
    "FONKODU": "fonKodu",
    "FONUNVAN": "fonUnvan",
    "FIYAT": "fiyat",
    "TEDPAYSAYISI": "tedPaySayisi",
    "KISISAYISI": "kisiSayisi",
    "PORTFOYBUYUKLUK": "portfoyBuyukluk",
    "BORSABULTENFIYAT": "borsaBultenFiyat",
}

# Columns turkeyfundsdata adds for display and the engine has no use for
TURKEYFUNDSDATA_EXTRA = ["FIYAT_6DEC"]

TURKEYFUNDSDATA_KEYS = ["TARIH", "FONKODU", "FONUNVAN"]


def load_turkeyfundsdata_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split a frame from turkeyfundsdata into the two frames the engine expects.

    ``turkeyfundsdata.tefas.get_fund_data_for_years`` can pull up to five years
    in one call, which is far more history than fetching live from here is
    practical for. It hands back price and allocation already merged, so this
    separates them again and restores the original TEFAS column names.

        from tefas import get_fund_data_for_years
        from besfundlens.data.loaders import load_turkeyfundsdata_frame

        df_general, df_allocation = load_turkeyfundsdata_frame(
            get_fund_data_for_years(5, "EMK")
        )
    """
    missing = [column for column in TURKEYFUNDSDATA_KEYS if column not in df.columns]
    if missing:
        raise ValueError(
            f"Not a turkeyfundsdata frame: missing {', '.join(missing)}. "
            "Expected the output of tefas.get_fund_data or get_fund_data_for_years."
        )

    general_columns = [c for c in TURKEYFUNDSDATA_GENERAL if c in df.columns]
    df_general = df[general_columns].rename(columns=TURKEYFUNDSDATA_GENERAL)

    # Whatever is neither a general field nor display-only is an allocation
    # percentage, which TEFAS publishes under lower-case short codes. The keys
    # belong to both frames, so they are put back at the front.
    allocation_columns = TURKEYFUNDSDATA_KEYS + [
        c
        for c in df.columns
        if c not in TURKEYFUNDSDATA_GENERAL and c not in TURKEYFUNDSDATA_EXTRA
    ]
    df_allocation = df[allocation_columns].rename(
        columns={
            **{k: v for k, v in TURKEYFUNDSDATA_GENERAL.items() if k in TURKEYFUNDSDATA_KEYS},
            **{
                c: c.lower()
                for c in allocation_columns
                if c not in TURKEYFUNDSDATA_KEYS
            },
        }
    )

    for frame in (df_general, df_allocation):
        frame["tarih"] = pd.to_datetime(frame["tarih"]).dt.strftime("%Y-%m-%d")

        # turkeyfundsdata formats TEDPAYSAYISI as a fixed-point string for
        # display, so anything that is not a key has to be coerced back to a
        # number or the engine divides a float by a str.
        values = [c for c in frame.columns if c not in ("tarih", "fonKodu", "fonUnvan")]
        frame[values] = frame[values].apply(pd.to_numeric, errors="coerce")

    return df_general.reset_index(drop=True), df_allocation.reset_index(drop=True)


def load_data(source: str = "sqlite", **kwargs) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load source data from sqlite, api, csv, or parquet."""
    source = source.lower()
    if source == "sqlite":
        return load_from_sqlite(kwargs["db_path"])
    if source == "api":
        return fetch_tefas_history(
            kwargs["start_date"],
            kwargs["end_date"],
            config=kwargs.get("config", FetchConfig()),
            verbose=kwargs.get("verbose", True),
        )
    if source == "csv":
        return load_from_csv(kwargs["general_path"], kwargs["allocation_path"])
    if source == "parquet":
        return load_from_parquet(kwargs["general_path"], kwargs["allocation_path"])
    raise ValueError("source must be one of: sqlite, api, csv, parquet")
