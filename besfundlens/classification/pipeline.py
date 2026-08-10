"""
Classification pipeline.

`classify_universe()` is the single entry point: it takes the DNA panel plus the
asset metadata table and returns one row per fund carrying the model-derived
asset class, the four secondary axes, the stability metrics and the provenance
of the window each verdict was computed from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import pandas as pd

from besfundlens.core.utils import resolve_lookback_intervals
from besfundlens.classification.axes import build_secondary_axes
from besfundlens.classification.config import DEFAULT_CONFIG, ClassificationConfig
from besfundlens.classification.features import (
    build_allocation_features,
    build_sub_window_features,
)
from besfundlens.classification.model import AllocationClassifier
from besfundlens.classification.stability import compute_stability

# Column order of the classification result, most important first.
RESULT_COLUMNS = [
    "fonKodu",
    "fonUnvan",
    "asset_class",
    "asset_class_tr",
    "asset_class_family",
    "class_id",
    "class_confidence",
    "runner_up_class",
    "class_description",
    "participation_class",
    "participation_class_tr",
    "risk_band",
    "risk_band_tr",
    "currency_band",
    "currency_band_tr",
    "lookthrough_band",
    "lookthrough_band_tr",
    "class_stability",
    "style_drift",
    "allocation_volatility",
    "drift_flag",
    "growth_asset_weight",
    "interest_bearing_weight",
    "participation_asset_weight",
    "lookthrough_weight",
    "try_weight",
    "fx_weight",
    "gold_weight",
    "distance_to_centroid",
    "n_observations",
    "n_sub_windows",
    "window_start",
    "window_end",
    "is_classifiable",
]


def classify_universe(
    panel_df: pd.DataFrame,
    asset_meta_df: pd.DataFrame,
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    config: ClassificationConfig = DEFAULT_CONFIG,
    model: Optional[AllocationClassifier] = None,
    model_path: Optional[Union[str, Path]] = None,
    fit: bool = True,
    save_model_to: Optional[Union[str, Path]] = None,
) -> dict:
    """
    Classify every fund in the panel by its asset allocation.

    Parameters
    ----------
    panel_df:
        DNA panel from `initialize_engine()` (raw allocation columns required).
    asset_meta_df:
        Asset metadata table from `build_asset_metadata()`.
    lookback / lookback_intervals:
        Observation window the classification is computed over.
    model / model_path:
        Reuse an already-fitted model instead of fitting a new one. This is what
        keeps class names comparable between reporting periods.
    fit:
        When False, a model must be supplied — the pipeline will only assign.
    save_model_to:
        Write the fitted model artifact to this path.

    Returns
    -------
    dict with keys `classification_df`, `model`, `features`, `fit_info`.
    """
    resolved = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    features, meta = build_allocation_features(
        panel_df=panel_df,
        asset_meta_df=asset_meta_df,
        lookback_intervals=resolved,
        lookback=None,
        config=config,
    )

    if model is None and model_path is not None:
        model = AllocationClassifier.load(model_path)

    classifiable = meta["is_classifiable"]
    fit_features = features[classifiable]

    if model is None:
        if not fit:
            raise ValueError(
                "fit=False requires an existing model. Pass model= or model_path=."
            )
        model = AllocationClassifier(config)
        model.fit(fit_features if not fit_features.empty else features)
        model.fit_info.window_start = _stringify_date(meta["window_start"].min())
        model.fit_info.window_end = _stringify_date(meta["window_end"].max())

    assignments = model.predict(features)

    axes = build_secondary_axes(features, meta, asset_meta_df, config)

    assignments["class_confidence"] = model.apply_lookthrough_penalty(
        assignments["class_confidence"],
        axes["lookthrough_weight"],
    )

    stability = compute_stability(
        sub_window_features=build_sub_window_features(
            panel_df=panel_df,
            asset_meta_df=asset_meta_df,
            lookback_intervals=resolved,
            lookback=None,
            config=config,
        ),
        window_features=features,
        model=model,
        latest_features=_latest_snapshot_features(
            panel_df=panel_df,
            asset_meta_df=asset_meta_df,
            config=config,
        ),
    )

    result = pd.concat([meta, assignments, axes, stability], axis=1)
    result = result.reset_index()

    # Funds with no usable allocation data get a blank verdict rather than a
    # confident-looking label derived from an all-zero vector.
    unusable = ~result["is_classifiable"]
    if unusable.any():
        for column in (
            "asset_class",
            "asset_class_tr",
            "asset_class_family",
            "runner_up_class",
            "class_description",
        ):
            result.loc[unusable, column] = None
        result.loc[unusable, "class_confidence"] = float("nan")
        result.loc[unusable, "class_id"] = -1

    ordered = [col for col in RESULT_COLUMNS if col in result.columns]
    remaining = [col for col in result.columns if col not in ordered]
    result = result[ordered + remaining]

    if save_model_to is not None:
        model.save(save_model_to)

    return {
        "classification_df": result,
        "model": model,
        "features": features,
        "fit_info": model.fit_info,
        "lookback_intervals": resolved,
    }


def _latest_snapshot_features(
    panel_df: pd.DataFrame,
    asset_meta_df: pd.DataFrame,
    config: ClassificationConfig,
) -> pd.DataFrame:
    """Allocation vector from the single most recent observation per fund."""
    features, _ = build_allocation_features(
        panel_df=panel_df,
        asset_meta_df=asset_meta_df,
        lookback_intervals=1,
        lookback=None,
        config=config,
    )
    return features


def _stringify_date(value) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def summarize_classification(
    classification_df: pd.DataFrame,
    group_col: str = "asset_class",
) -> pd.DataFrame:
    """
    Fund counts and average confidence per class.

    When the classification result has been merged onto a lens universe table,
    AUM-weighted flow and market-effect columns are summarised too.
    """
    if classification_df.empty or group_col not in classification_df.columns:
        return pd.DataFrame()

    df = classification_df[classification_df[group_col].notna()].copy()
    if df.empty:
        return pd.DataFrame()

    rows = []
    has_aum = "start_aum" in df.columns
    universe_aum = df["start_aum"].sum() if has_aum else 0.0

    for group_name, group_df in df.groupby(group_col, dropna=True):
        row = {
            group_col: group_name,
            "fund_count": int(group_df.shape[0]),
            "avg_confidence": group_df["class_confidence"].mean(),
            "avg_stability": group_df["class_stability"].mean()
            if "class_stability" in group_df.columns
            else float("nan"),
        }

        if has_aum:
            start_aum = group_df["start_aum"].sum()
            row["total_start_aum"] = start_aum
            row["start_aum_share"] = start_aum / universe_aum if universe_aum else float("nan")
            row["weighted_flow_pct"] = (
                group_df["total_net_flow"].sum() / start_aum if start_aum else float("nan")
            )
            row["weighted_market_effect_pct"] = (
                group_df["total_market_effect"].sum() / start_aum if start_aum else float("nan")
            )

        rows.append(row)

    summary = pd.DataFrame(rows)
    sort_col = "total_start_aum" if has_aum else "fund_count"
    return summary.sort_values(sort_col, ascending=False).reset_index(drop=True)
