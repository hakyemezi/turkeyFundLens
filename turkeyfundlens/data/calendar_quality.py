from __future__ import annotations

import pandas as pd

try:
    import holidays
except ImportError:  # pragma: no cover - optional dependency fallback
    holidays = None


def check_missing_business_days(
    df_general: pd.DataFrame,
    date_col: str = "tarih",
    country: str = "TR",
) -> pd.DatetimeIndex:
    """Return business days missing from df_general excluding weekends and public holidays."""
    if df_general is None or df_general.empty:
        return pd.DatetimeIndex([])

    dates = pd.to_datetime(df_general[date_col], errors="coerce").dropna()
    if dates.empty:
        return pd.DatetimeIndex([])

    start = dates.min().normalize()
    end = dates.max().normalize()
    business_days = pd.date_range(start=start, end=end, freq="B")

    if holidays is not None and country.upper() == "TR":
        years = list(range(start.year, end.year + 1))
        holiday_dates = pd.to_datetime(list(holidays.TR(years=years).keys()))
        business_days = business_days[~business_days.isin(holiday_dates)]

    existing = pd.DatetimeIndex(dates.dt.normalize().unique())
    return business_days.difference(existing)
