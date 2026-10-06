from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Iterator

import pandas as pd
import requests

from turkeyfundlens.config import URL_GENEL, URL_DAGILIM, DEFAULT_FON_TIPI


@dataclass(frozen=True)
class FetchConfig:
    """Configuration for TEFAS/Fonturkey data requests."""
    max_retries: int = 5
    success_sleep: float = 1.0
    error_sleep: float = 15.0
    timeout: int = 40
    language: str = "TR"
    fund_type: str = DEFAULT_FON_TIPI


def _normalize_date(value) -> pd.Timestamp:
    return pd.to_datetime(value).normalize()


def _build_payload(start_date, end_date, config: FetchConfig) -> dict:
    start = _normalize_date(start_date).strftime("%Y%m%d")
    end = _normalize_date(end_date).strftime("%Y%m%d")
    return {
        "dil": config.language,
        "fonTipi": config.fund_type,
        "fonKod": None,
        "fonGrup": None,
        "basTarih": start,
        "bitTarih": end,
        "fonTurKod": None,
        "fonUnvanTip": None,
        "kurucuKod": None,
        "fonTurAciklama": None,
        "sfonTurKod": None,
    }


def month_chunks(start_date, end_date) -> Iterator[tuple[pd.Timestamp, pd.Timestamp]]:
    """Yield monthly date chunks between start_date and end_date inclusive."""
    current = _normalize_date(start_date)
    end = _normalize_date(end_date)
    while current <= end:
        chunk_end = current + pd.DateOffset(months=1) - pd.Timedelta(days=1)
        if chunk_end > end:
            chunk_end = end
        yield current, chunk_end
        current = current + pd.DateOffset(months=1)


def fetch_tefas_period(
    start_date,
    end_date,
    config: Optional[FetchConfig] = None,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch general and allocation data for a single date period."""
    config = config or FetchConfig()
    payload = _build_payload(start_date, end_date, config)
    start = _normalize_date(start_date)
    end = _normalize_date(end_date)

    if verbose:
        print(f"Fetching fund data: {start.date()} - {end.date()}")

    last_error: Optional[Exception] = None
    for attempt in range(config.max_retries):
        try:
            response_general = requests.post(URL_GENEL, json=payload, timeout=config.timeout)
            response_allocation = requests.post(URL_DAGILIM, json=payload, timeout=config.timeout)

            if response_general.status_code == 200 and response_allocation.status_code == 200:
                data_general = response_general.json().get("resultList", [])
                data_allocation = response_allocation.json().get("resultList", [])
                return pd.DataFrame(data_general), pd.DataFrame(data_allocation)

            if verbose:
                print(
                    "  -> Non-200 response: "
                    f"general={response_general.status_code}, allocation={response_allocation.status_code}"
                )
        except Exception as exc:  # network/timeouts/json errors are handled uniformly
            last_error = exc
            if verbose:
                print(f"  -> Request failed: {exc}")

        if attempt < config.max_retries - 1:
            if verbose:
                remaining = config.max_retries - attempt - 1
                print(f"  -> Sleeping {config.error_sleep}s before retry. Remaining retries: {remaining}")
            time.sleep(config.error_sleep)

    if last_error is not None and verbose:
        print(f"  -> Final failure for {start.date()} - {end.date()}: {last_error}")
    return pd.DataFrame(), pd.DataFrame()


def fetch_tefas_history(
    start_date,
    end_date,
    config: Optional[FetchConfig] = None,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch historical data using monthly chunks and concatenate the result."""
    config = config or FetchConfig()
    general_frames: list[pd.DataFrame] = []
    allocation_frames: list[pd.DataFrame] = []

    for chunk_start, chunk_end in month_chunks(start_date, end_date):
        df_general, df_allocation = fetch_tefas_period(
            chunk_start,
            chunk_end,
            config=config,
            verbose=verbose,
        )
        if not df_general.empty:
            general_frames.append(df_general)
        if not df_allocation.empty:
            allocation_frames.append(df_allocation)
        time.sleep(config.success_sleep)

    df_general_final = (
        pd.concat(general_frames, ignore_index=True).drop_duplicates()
        if general_frames else pd.DataFrame()
    )
    df_allocation_final = (
        pd.concat(allocation_frames, ignore_index=True).drop_duplicates()
        if allocation_frames else pd.DataFrame()
    )

    return df_general_final, df_allocation_final


def fetch_last_years(
    years: int = 5,
    end_date=None,
    config: Optional[FetchConfig] = None,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convenience helper to fetch the latest N years of fund data."""
    end = _normalize_date(end_date or pd.Timestamp.today())
    start = end - pd.DateOffset(years=years)
    return fetch_tefas_history(start, end, config=config, verbose=verbose)
