"""
Shared, dependency-free helpers used by the analytics engine and the
classification layer.

These functions were originally defined inside ``besfundlens.core.engine``.
They live here so that ``besfundlens.classification`` can reuse them without
importing the engine, which would create a circular import once the engine
starts calling into the classification pipeline.

``engine`` re-exports every name defined here, so existing imports such as
``from besfundlens.core.engine import safe_divide`` keep working unchanged.
"""

from __future__ import annotations

import re
from typing import Optional, Sequence, Union

import numpy as np
import pandas as pd

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "tr"}

LOOKBACK_PRESETS = {
    "1m": 20,
    "3m": 60,
    "6m": 120,
    "1y": 240,
}


def parse_tarih(series: pd.Series) -> pd.Series:
    """
    Karışık tarih formatlarını güvenli şekilde datetime'a çevirir.
    Önce pandas'ın mixed format desteğini dener.
    Olmazsa dayfirst=True ile tekrar dener.
    """
    parsed = pd.to_datetime(series, errors="coerce", format="mixed")

    missing_mask = parsed.isna()

    if missing_mask.any():
        parsed_fallback = pd.to_datetime(
            series[missing_mask],
            errors="coerce",
            dayfirst=True,
        )
        parsed.loc[missing_mask] = parsed_fallback

    return parsed


def make_safe_col_name(text: str) -> str:
    """
    Grup isimlerini güvenli dataframe kolon adına çevirir.

    Örnek:
    'Fixed Income'              -> 'fixed_income'
    'Foreign / International'   -> 'foreign_international'
    'Money Market / Collateral' -> 'money_market_collateral'
    """
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")
    return text


def is_finite_number(value) -> bool:
    """
    Tekil sayısal değerlerin NaN / inf olmadığını kontrol eder.
    """
    try:
        return pd.notna(value) and np.isfinite(value)
    except TypeError:
        return False


def normalize_language(language: str = DEFAULT_LANGUAGE) -> str:
    """
    Normalize report/output language.

    Supported values:
        - "en": English
        - "tr": Turkish
    """
    if language is None:
        return DEFAULT_LANGUAGE

    language = str(language).lower().strip()

    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: {language}. Supported languages: {sorted(SUPPORTED_LANGUAGES)}"
        )

    return language


def resolve_lookback_intervals(
    lookback: Optional[Union[str, int]] = None,
    lookback_intervals: int = 20,
) -> int:
    """
    Resolve lookback input into observation intervals.

    Examples:
        resolve_lookback_intervals("1m") -> 20
        resolve_lookback_intervals("3m") -> 60
        resolve_lookback_intervals(45)   -> 45

    Important:
        These are available fund observations / intervals, not calendar days.
    """
    if lookback is None:
        resolved = lookback_intervals
    elif isinstance(lookback, str):
        key = lookback.lower().strip()
        if key in LOOKBACK_PRESETS:
            resolved = LOOKBACK_PRESETS[key]
        else:
            try:
                resolved = int(key)
            except ValueError as exc:
                raise ValueError(
                    f"Unknown lookback preset: {lookback}. "
                    f"Use one of {sorted(LOOKBACK_PRESETS)} or an integer interval count."
                ) from exc
    else:
        resolved = int(lookback)

    if resolved <= 0:
        raise ValueError("lookback interval count must be positive.")

    return resolved


def normalize_fund_codes(fund_codes: Optional[Sequence[str]]) -> Optional[list]:
    """
    Normalize user-provided fund codes into uppercase unique codes.
    Keeps input order and removes duplicates.
    """
    if fund_codes is None:
        return None

    normalized = []
    seen = set()

    for code in fund_codes:
        if code is None:
            continue
        clean_code = str(code).strip().upper()
        if clean_code and clean_code not in seen:
            normalized.append(clean_code)
            seen.add(clean_code)

    return normalized


def safe_divide(numerator, denominator, default=np.nan):
    """
    Sıfır, NaN veya sonsuz payda/pay durumunda güvenli bölme yapar.
    Scalar hesaplamalarda kullanılır.
    """
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return default

    result = numerator / denominator

    if not np.isfinite(result):
        return default

    return result


def safe_divide_series(numerator, denominator, default=np.nan) -> pd.Series:
    """
    Pandas Series bazlı güvenli bölme yapar.
    Sıfır paydaları ve inf sonuçları default değerine çevirir.
    """
    denominator_safe = denominator.replace(0, np.nan)

    result = numerator / denominator_safe

    return result.replace([np.inf, -np.inf], np.nan).fillna(default)


def format_try(value) -> str:
    """
    TL tutarlarını okunabilir formata çevirir.
    """
    if not is_finite_number(value):
        return "N/A"

    return f"{value:,.2f} TL"


def format_pct(value) -> str:
    """
    Ondalık oranları yüzde formatına çevirir.

    Örnek:
    0.0123 -> 1.23%
    """
    if not is_finite_number(value):
        return "N/A"

    return f"{value * 100:.2f}%"


def format_number(value) -> str:
    """
    Büyük sayıları okunabilir formatta döndürür.
    """
    if not is_finite_number(value):
        return "N/A"

    return f"{value:,.2f}"
