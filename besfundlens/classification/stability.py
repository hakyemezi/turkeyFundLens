"""
Stability and style-drift metrics.

Classifying on a window average hides one thing worth seeing: whether the fund
actually held that allocation throughout, or moved into it. These metrics split
the window into sub-windows and measure how much the fund moved.

- `class_stability`        share of sub-windows assigned to the modal class
- `allocation_volatility`  mean L1 distance between consecutive sub-windows
- `style_drift`            L1 distance between the first and last sub-window
- `drift_flag`             latest snapshot lands in a different class than the window

A fund with no observations in a sub-window is missing there, not empty. Filling
it with zeros would make a fund that launched mid-window look like it rotated
its entire portfolio, so absent sub-windows propagate as NaN throughout.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd


def _presence(frame: pd.DataFrame) -> pd.Series:
    """
    True for funds that actually have allocation data in this frame.

    Absence shows up two ways depending on the producer: sub-window matrices
    leave missing funds as NaN, while the window matrix zero-fills them. A real
    allocation row sums to ~100, so "no non-zero weight" covers both.
    """
    return frame.notna().any(axis=1) & frame.fillna(0.0).abs().sum(axis=1).gt(0)


def l1_distance(a: pd.DataFrame, b: pd.DataFrame) -> pd.Series:
    """
    Row-wise L1 distance between two aligned allocation matrices.

    Both are percentage compositions summing to ~100, so the distance reads as
    "percentage points of the portfolio that moved", doubled (a move out of one
    group and into another is counted on both sides).

    Funds absent from either side get NaN rather than a distance measured
    against an imaginary all-zero portfolio.
    """
    aligned_b = b.reindex(index=a.index, columns=a.columns)

    both_present = _presence(a) & _presence(aligned_b)
    distance = (a.fillna(0.0) - aligned_b.fillna(0.0)).abs().sum(axis=1)

    return distance.where(both_present)


def compute_stability(
    sub_window_features: Sequence[pd.DataFrame],
    window_features: pd.DataFrame,
    model,
    latest_features: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Stability metrics for every fund in `window_features`.

    `sub_window_features` is ordered oldest -> newest. With fewer than two
    usable sub-windows the drift metrics are undefined and come back as NaN,
    while `class_stability` defaults to 1.0 (nothing observed moved).
    """
    index = window_features.index

    result = pd.DataFrame(index=index)
    result["class_stability"] = 1.0
    result["allocation_volatility"] = np.nan
    result["style_drift"] = np.nan
    result["n_sub_windows"] = len(sub_window_features)

    usable = [frame for frame in sub_window_features if frame is not None and not frame.empty]

    if len(usable) >= 2:
        result["class_stability"] = _class_stability(usable, model, index)

        distances = [
            l1_distance(usable[i + 1], usable[i])
            for i in range(len(usable) - 1)
        ]
        result["allocation_volatility"] = pd.concat(distances, axis=1).mean(axis=1).reindex(index)
        result["style_drift"] = l1_distance(usable[-1], usable[0]).reindex(index)

    result["drift_flag"] = _drift_flag(window_features, latest_features, model, index)

    return result


def _class_stability(
    sub_windows: Sequence[pd.DataFrame],
    model,
    index: pd.Index,
) -> pd.Series:
    """
    Share of sub-windows in which the fund landed in its own modal class.

    Sub-windows where the fund has no data contribute nothing to either side of
    the ratio, so a fund observed in only one sub-window scores 1.0 rather than
    being penalised for history it does not have.
    """
    assignments = []

    for frame in sub_windows:
        aligned = frame.reindex(index)
        present = _presence(aligned)

        predicted = model.predict(aligned.fillna(0.0))["class_id"]
        assignments.append(predicted.where(present))

    matrix = pd.concat(assignments, axis=1)

    def modal_share(row: pd.Series) -> float:
        observed = row.dropna()
        if observed.empty:
            return np.nan
        return observed.value_counts().iloc[0] / len(observed)

    return matrix.apply(modal_share, axis=1).reindex(index)


def _drift_flag(
    window_features: pd.DataFrame,
    latest_features: Optional[pd.DataFrame],
    model,
    index: pd.Index,
) -> pd.Series:
    """True when the most recent snapshot no longer matches the window class."""
    if latest_features is None or latest_features.empty:
        return pd.Series(False, index=index)

    latest = latest_features.reindex(index)
    present = _presence(window_features) & _presence(latest)

    window_class = model.predict(window_features.fillna(0.0))["class_id"]
    latest_class = model.predict(latest.fillna(0.0))["class_id"]

    return (window_class != latest_class).where(present, False).reindex(index).fillna(False)
