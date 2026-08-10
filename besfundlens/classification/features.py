"""
Allocation feature construction.

The classifier does not look at a single day. For each fund it averages the
allocation vectors observed inside the lookback window, which makes the result
robust to a single bad publication date and lets us measure how much the
allocation moved inside the window.

Two products come out of this module:

- `build_allocation_features()`   one row per fund, the window-averaged vector
- `build_sub_window_features()`   the same, per sub-window, for stability metrics
"""

from __future__ import annotations

from typing import Optional, Union

import numpy as np
import pandas as pd

from besfundlens.core.utils import resolve_lookback_intervals
from besfundlens.classification.config import DEFAULT_CONFIG, ClassificationConfig

ID_COLS = ["fonKodu", "fonUnvan", "tarih"]


def resolve_asset_cols(panel_df: pd.DataFrame, asset_meta_df: pd.DataFrame) -> list:
    """Raw instrument columns present in both the panel and the metadata table."""
    known_codes = set(asset_meta_df["asset_code"])
    return [col for col in panel_df.columns if col in known_codes]


def build_feature_names(
    asset_meta_df: pd.DataFrame,
    asset_cols: list,
    config: ClassificationConfig = DEFAULT_CONFIG,
) -> tuple[list, dict]:
    """
    Return (feature_names, feature_to_codes) for the configured feature space.

    `feature_names` are readable labels ("Fixed Income", "Equity", ...) so the
    centroids of the fitted model stay directly interpretable.
    """
    if config.group_col is None:
        # Raw feature space: one feature per instrument code.
        name_map = dict(zip(asset_meta_df["asset_code"], asset_meta_df["asset_name_en_clean"]))
        feature_names = [name_map.get(code, code) for code in asset_cols]
        return feature_names, {name: [code] for name, code in zip(feature_names, asset_cols)}

    valid_meta = asset_meta_df[asset_meta_df["asset_code"].isin(asset_cols)]
    groups = sorted(valid_meta[config.group_col].dropna().unique())

    feature_to_codes = {}
    for group in groups:
        codes = valid_meta.loc[valid_meta[config.group_col].eq(group), "asset_code"].tolist()
        # The metadata already holds the display form of the group name
        # ("Government Fixed Income FX"), so it is used as-is. Round-tripping it
        # through the engine's DNA column cleaner would title-case it back into
        # "Government Fixed Income Fx".
        feature_to_codes[group] = codes

    return list(feature_to_codes), feature_to_codes


def aggregate_allocation(
    df: pd.DataFrame,
    feature_to_codes: dict,
) -> pd.DataFrame:
    """Sum raw instrument columns into the configured feature columns."""
    aggregated = {}
    for label, codes in feature_to_codes.items():
        present = [code for code in codes if code in df.columns]
        aggregated[label] = df[present].sum(axis=1) if present else 0.0
    return pd.DataFrame(aggregated, index=df.index)


def select_allocation_rows(
    panel_df: pd.DataFrame,
    lookback_intervals: int,
    config: ClassificationConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Keep the last `lookback_intervals` rows per fund that actually carry
    allocation data and pass the distribution-total quality filter.
    """
    df = panel_df.copy()

    if "dagilim_toplam" in df.columns:
        df = df[df["dagilim_toplam"].notna()]
        df = df[
            df["dagilim_toplam"].between(
                config.min_dagilim_total,
                config.max_dagilim_total,
            )
        ]

    if df.empty:
        return df

    df = df.sort_values(["fonKodu", "tarih"])
    return df.groupby("fonKodu", group_keys=False).tail(lookback_intervals)


def _normalize_rows(features: pd.DataFrame, config: ClassificationConfig) -> pd.DataFrame:
    """Rescale each row to sum to 100 so distances are not driven by total drift."""
    if not config.renormalize:
        return features

    totals = features.sum(axis=1)
    scaled = features.div(totals.replace(0, np.nan), axis=0) * 100.0
    return scaled.fillna(0.0)


def apply_transform(features: pd.DataFrame, config: ClassificationConfig) -> pd.DataFrame:
    """
    Optional transform applied before clustering.

    "hellinger" (element-wise square root of the composition) spreads out funds
    that differ only in small allocations. It is off by default because raw
    weights keep the cluster centroids readable as percentages.
    """
    if config.transform == "hellinger":
        return np.sqrt(features.clip(lower=0.0))
    return features


def build_allocation_features(
    panel_df: pd.DataFrame,
    asset_meta_df: pd.DataFrame,
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    config: ClassificationConfig = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build the window-averaged allocation matrix.

    Returns
    -------
    (features, meta)
        `features`: one row per fund, columns are the feature-space labels,
                    values are percentages summing to ~100.
        `meta`:     per-fund provenance and raw-code weights, indexed the same
                    way, including funds that could not be classified.
    """
    resolved = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    asset_cols = resolve_asset_cols(panel_df, asset_meta_df)
    if not asset_cols:
        raise ValueError(
            "No known allocation columns found in the panel. "
            "Check that the allocation table uses TEFAS/Fonturkey instrument codes."
        )

    feature_names, feature_to_codes = build_feature_names(asset_meta_df, asset_cols, config)

    all_funds = pd.Index(
        sorted(panel_df["fonKodu"].dropna().unique()),
        name="fonKodu",
    )

    window = select_allocation_rows(panel_df, resolved, config)

    if window.empty:
        empty_features = pd.DataFrame(0.0, index=all_funds, columns=feature_names)
        empty_meta = _empty_meta(all_funds, panel_df, asset_cols)
        return empty_features, empty_meta

    aggregated = aggregate_allocation(window, feature_to_codes)
    aggregated["fonKodu"] = window["fonKodu"].values

    features = aggregated.groupby("fonKodu")[feature_names].mean()
    features = _normalize_rows(features, config)

    # Raw code weights are kept alongside the (possibly aggregated) features
    # because the secondary axes need instrument-level detail.
    raw_weights = window[asset_cols].copy()
    raw_weights["fonKodu"] = window["fonKodu"].values
    raw_weights = raw_weights.groupby("fonKodu")[asset_cols].mean()
    raw_weights = _normalize_rows(raw_weights, config)

    meta = _build_meta(window, all_funds, raw_weights, asset_cols, panel_df, config)

    features = features.reindex(all_funds).fillna(0.0)

    return features, meta


def _build_meta(
    window: pd.DataFrame,
    all_funds: pd.Index,
    raw_weights: pd.DataFrame,
    asset_cols: list,
    panel_df: pd.DataFrame,
    config: ClassificationConfig,
) -> pd.DataFrame:
    """Per-fund provenance, name and raw instrument weights."""
    grouped = window.groupby("fonKodu")

    meta = pd.DataFrame(index=all_funds)
    meta["n_observations"] = grouped.size().reindex(all_funds).fillna(0).astype(int)
    meta["window_start"] = grouped["tarih"].min().reindex(all_funds)
    meta["window_end"] = grouped["tarih"].max().reindex(all_funds)

    names = (
        panel_df.sort_values("tarih")
        .groupby("fonKodu")["fonUnvan"]
        .last()
        .reindex(all_funds)
    )
    meta["fonUnvan"] = names

    meta["is_classifiable"] = meta["n_observations"] >= config.min_observations

    raw = raw_weights.reindex(all_funds).fillna(0.0)
    for code in asset_cols:
        meta[f"w_{code}"] = raw[code]

    return meta


def _empty_meta(all_funds: pd.Index, panel_df: pd.DataFrame, asset_cols: list) -> pd.DataFrame:
    meta = pd.DataFrame(index=all_funds)
    meta["n_observations"] = 0
    meta["window_start"] = pd.NaT
    meta["window_end"] = pd.NaT
    meta["fonUnvan"] = (
        panel_df.sort_values("tarih").groupby("fonKodu")["fonUnvan"].last().reindex(all_funds)
    )
    meta["is_classifiable"] = False
    for code in asset_cols:
        meta[f"w_{code}"] = 0.0
    return meta


def build_sub_window_features(
    panel_df: pd.DataFrame,
    asset_meta_df: pd.DataFrame,
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    config: ClassificationConfig = DEFAULT_CONFIG,
) -> list:
    """
    Split the lookback window into `config.sub_window_count` consecutive slices
    and build the allocation matrix for each.

    Returns a list of DataFrames (oldest slice first), all sharing the same
    columns and fund index. Slices with no data at all are skipped.
    """
    resolved = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    asset_cols = resolve_asset_cols(panel_df, asset_meta_df)
    feature_names, feature_to_codes = build_feature_names(asset_meta_df, asset_cols, config)

    all_funds = pd.Index(sorted(panel_df["fonKodu"].dropna().unique()), name="fonKodu")
    window = select_allocation_rows(panel_df, resolved, config)

    if window.empty or config.sub_window_count < 2:
        return []

    window = window.sort_values(["fonKodu", "tarih"])
    # Rank observations backwards from the newest so every fund is sliced by
    # its own available history, not by calendar dates it may be missing.
    reverse_rank = window.groupby("fonKodu").cumcount(ascending=False)
    slice_size = max(1, int(np.ceil(resolved / config.sub_window_count)))
    slice_id = (reverse_rank // slice_size).clip(upper=config.sub_window_count - 1)

    slices = []
    for index in range(config.sub_window_count - 1, -1, -1):  # oldest -> newest
        part = window[slice_id.values == index]
        if part.empty:
            continue

        aggregated = aggregate_allocation(part, feature_to_codes)
        aggregated["fonKodu"] = part["fonKodu"].values
        frame = aggregated.groupby("fonKodu")[feature_names].mean()
        frame = _normalize_rows(frame, config)
        slices.append(frame.reindex(all_funds))

    return slices
