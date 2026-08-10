"""
Secondary classification axes.

These four axes sit next to the model-derived asset class, each as its own
categorical column. They are threshold-based rather than model-derived because
each one encodes a *definition* rather than a pattern to be discovered:

- participation: a fund is interest-free iff it holds no interest-bearing
  instruments. No unsupervised method can recover "riba" from allocation data.
- currency / look-through: dominance bands over an already-meaningful quantity.
- risk: bands over growth-asset weight. This one accepts a data-driven method
  (`quantile` or `kmeans1d`) for callers who prefer the universe to set its own
  boundaries; `fixed` is the default because fixed edges stay comparable across
  reporting periods.

Every threshold comes from `ClassificationConfig`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from besfundlens.classification.config import DEFAULT_CONFIG, ClassificationConfig

PARTICIPATION_LABELS = {
    "en": {
        "participation": "Participation",
        "conventional": "Conventional",
        "mixed": "Mixed",
        "unknown": "Unknown",
    },
    "tr": {
        "participation": "Katılım",
        "conventional": "Konvansiyonel",
        "mixed": "Karma",
        "unknown": "Bilinmiyor",
    },
}

RISK_BAND_LABELS = {
    "en": ["Conservative", "Balanced", "Aggressive", "Specialised"],
    "tr": ["Muhafazakâr", "Dengeli", "Atak", "Uzmanlaşmış"],
}

CURRENCY_BAND_LABELS = {
    "en": {
        "try": "TRY Weighted",
        "fx": "FX Weighted",
        "gold": "Gold Weighted",
        "mixed": "Mixed Currency",
    },
    "tr": {
        "try": "TRY Ağırlıklı",
        "fx": "FX Ağırlıklı",
        "gold": "Altın Ağırlıklı",
        "mixed": "Karma Kur",
    },
}

LOOKTHROUGH_BAND_LABELS = {
    "en": ["Transparent", "Partial Look-through", "Heavy Look-through"],
    "tr": ["Şeffaf", "Kısmi Look-through", "Yoğun Look-through"],
}


def _raw_weight(meta: pd.DataFrame, codes, magnitude: bool = False) -> pd.Series:
    """
    Sum the `w_<code>` columns for the given instrument codes.

    On negative entries
    -------------------
    A negative weight (a fund reporting -8% repo) is not a short position. The
    fund pledged that asset as collateral to borrow against it, and it cannot be
    reported as both the asset and the cash, so the leg comes through negative
    and the row still totals 100.

    That makes signed summation the right default: the weights are a genuine
    decomposition of the portfolio, and `participation_asset_weight` plus
    `interest_bearing_weight` should add back up to roughly 100.

    `magnitude=True` is for the one different question — not "how much of the
    portfolio is this" but "is the fund party to this kind of transaction at
    all". A repo entered from the borrowing side is still a repo, and the fund
    still pays interest on it, so its magnitude is what counts.
    """
    cols = [f"w_{code}" for code in codes if f"w_{code}" in meta.columns]
    if not cols:
        return pd.Series(0.0, index=meta.index)

    selected = meta[cols]
    return (selected.abs() if magnitude else selected).sum(axis=1)


def _feature_weight(features: pd.DataFrame, groups) -> pd.Series:
    """Sum the feature columns matching the given group labels."""
    cols = [group for group in groups if group in features.columns]
    if not cols:
        return pd.Series(0.0, index=features.index)
    return features[cols].sum(axis=1)


def compute_support_weights(
    features: pd.DataFrame,
    meta: pd.DataFrame,
    asset_meta_df: pd.DataFrame,
    config: ClassificationConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Numeric quantities the bands are built from.

    Kept as columns in their own right because they are useful on their own —
    a reader often wants the raw FX weight, not just the band it fell into.
    """
    currency_map = dict(zip(asset_meta_df["asset_code"], asset_meta_df["currency_exposure"]))

    def codes_for_currency(value):
        return [code for code, exposure in currency_map.items() if exposure == value]

    support = pd.DataFrame(index=features.index)

    # The participation verdict asks whether the fund is party to an
    # interest-bearing transaction, so a pledged (negative) repo leg still
    # counts. Everything else is compositional and stays signed, so the weights
    # keep adding up to the published 100.
    support["interest_bearing_weight"] = _raw_weight(
        meta, config.interest_bearing_codes, magnitude=True
    )
    support["participation_asset_weight"] = _raw_weight(meta, config.participation_codes)
    support["growth_asset_weight"] = _feature_weight(features, config.growth_asset_groups)
    support["lookthrough_weight"] = _feature_weight(features, config.lookthrough_asset_groups)

    support["try_weight"] = _raw_weight(meta, codes_for_currency("TRY"))
    support["fx_weight"] = _raw_weight(meta, codes_for_currency("FX"))
    support["gold_weight"] = _raw_weight(meta, codes_for_currency("Gold"))

    return support


def classify_participation(
    support: pd.DataFrame,
    config: ClassificationConfig = DEFAULT_CONFIG,
    language: str = "en",
) -> pd.Series:
    """
    Participation (interest-free) verdict.

    - Participation: interest-bearing weight within tolerance **and** enough of
      the portfolio recognised as participation-compatible.
    - Mixed: no interest-bearing exposure, but too much of the portfolio sits in
      instruments we cannot vouch for either way (derivatives, generic funds).
    - Conventional: carries interest-bearing instruments above tolerance.
    """
    labels = PARTICIPATION_LABELS["tr" if language == "tr" else "en"]

    interest = support["interest_bearing_weight"]
    participation_assets = support["participation_asset_weight"]

    result = pd.Series(labels["conventional"], index=support.index, dtype=object)

    clean = interest <= config.participation_tolerance
    covered = participation_assets >= config.participation_min_coverage

    result[clean & ~covered] = labels["mixed"]
    result[clean & covered] = labels["participation"]

    empty = (interest + participation_assets) <= 0
    result[empty] = labels["unknown"]

    return result


def classify_risk_band(
    support: pd.DataFrame,
    config: ClassificationConfig = DEFAULT_CONFIG,
    language: str = "en",
) -> pd.Series:
    """
    Risk band from growth-asset weight (equity + foreign equity + precious
    metals + alternatives).

    `config.risk_band_method` picks how the edges are set:
    "fixed" uses `config.risk_band_edges`, "quantile" uses the universe's own
    quartiles, "kmeans1d" lets a 1-D KMeans find the natural breaks.
    """
    labels = RISK_BAND_LABELS["tr" if language == "tr" else "en"]
    growth = support["growth_asset_weight"].fillna(0.0)

    edges = _resolve_risk_edges(growth, config)

    band_index = np.digitize(growth.to_numpy(dtype=float), edges, right=False)
    return pd.Series([labels[i] for i in band_index], index=support.index, dtype=object)


def _resolve_risk_edges(growth: pd.Series, config: ClassificationConfig) -> list:
    """Three ascending cut points splitting growth weight into four bands."""
    if config.risk_band_method == "fixed":
        return list(config.risk_band_edges)

    values = growth.to_numpy(dtype=float)
    distinct = np.unique(values)

    # Data-driven banding needs enough distinct values to be meaningful.
    if distinct.size < 4:
        return list(config.risk_band_edges)

    if config.risk_band_method == "quantile":
        edges = np.quantile(values, [0.25, 0.5, 0.75])
    else:  # kmeans1d
        from sklearn.cluster import KMeans

        model = KMeans(
            n_clusters=4,
            random_state=config.random_state,
            n_init=config.n_init,
        ).fit(values.reshape(-1, 1))
        centers = np.sort(model.cluster_centers_.ravel())
        edges = (centers[:-1] + centers[1:]) / 2.0

    edges = np.sort(np.asarray(edges, dtype=float))

    # Ties would collapse bands; nudging keeps np.digitize monotonic.
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = np.nextafter(edges[i - 1], np.inf)

    return edges.tolist()


def classify_currency_band(
    support: pd.DataFrame,
    config: ClassificationConfig = DEFAULT_CONFIG,
    language: str = "en",
) -> pd.Series:
    """Dominant currency exposure, or "Mixed" when none clears the threshold."""
    labels = CURRENCY_BAND_LABELS["tr" if language == "tr" else "en"]
    threshold = config.currency_band_threshold

    result = pd.Series(labels["mixed"], index=support.index, dtype=object)
    result[support["try_weight"] >= threshold] = labels["try"]
    result[support["fx_weight"] >= threshold] = labels["fx"]
    result[support["gold_weight"] >= threshold] = labels["gold"]

    return result


def classify_lookthrough_band(
    support: pd.DataFrame,
    config: ClassificationConfig = DEFAULT_CONFIG,
    language: str = "en",
) -> pd.Series:
    """How much of the portfolio is other funds, and therefore not visible."""
    labels = LOOKTHROUGH_BAND_LABELS["tr" if language == "tr" else "en"]
    low, high = config.lookthrough_band_edges

    weight = support["lookthrough_weight"].fillna(0.0)
    band_index = np.digitize(weight.to_numpy(dtype=float), [low, high], right=False)

    return pd.Series([labels[i] for i in band_index], index=support.index, dtype=object)


def build_secondary_axes(
    features: pd.DataFrame,
    meta: pd.DataFrame,
    asset_meta_df: pd.DataFrame,
    config: ClassificationConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    All four axes plus their supporting weights, in EN and TR.

    Both languages are computed up front so a report can switch language
    without re-running the pipeline.
    """
    support = compute_support_weights(features, meta, asset_meta_df, config)

    result = support.copy()

    for language, suffix in (("en", ""), ("tr", "_tr")):
        result[f"participation_class{suffix}"] = classify_participation(support, config, language)
        result[f"risk_band{suffix}"] = classify_risk_band(support, config, language)
        result[f"currency_band{suffix}"] = classify_currency_band(support, config, language)
        result[f"lookthrough_band{suffix}"] = classify_lookthrough_band(support, config, language)

    return result
