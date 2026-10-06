"""
turkeyFundLens allocation classification layer (v2).

Classifies pension funds by what they actually hold. The grouping is discovered
by a clustering model over window-averaged allocation vectors; the rule-based
taxonomy only names the resulting classes. Four configurable categorical axes
sit alongside the asset class: participation, risk, currency and look-through.

    from turkeyfundlens.classification import classify_universe

    result = classify_universe(df_panel_dna, asset_meta_df, lookback="3m")
    result["classification_df"].head()
"""

from turkeyfundlens.classification.config import (
    DEFAULT_CONFIG,
    ClassificationConfig,
    FEATURE_SPACE_GROUP_COLS,
    GROWTH_ASSET_GROUPS,
    INTEREST_BEARING_CODES,
    LOOKTHROUGH_ASSET_GROUPS,
    PARTICIPATION_CODES,
)
from turkeyfundlens.classification.features import (
    build_allocation_features,
    build_sub_window_features,
)
from turkeyfundlens.classification.taxonomy import (
    assign_family,
    describe_centroid,
    label_centroid,
    translate_family,
    translate_group,
)
from turkeyfundlens.classification.model import (
    AllocationClassifier,
    FitInfo,
    ScikitLearnUnavailable,
)
from turkeyfundlens.classification.axes import (
    build_secondary_axes,
    classify_currency_band,
    classify_lookthrough_band,
    classify_participation,
    classify_risk_band,
    compute_support_weights,
)
from turkeyfundlens.classification.stability import compute_stability
from turkeyfundlens.classification.pipeline import (
    classify_universe,
    summarize_classification,
)
from turkeyfundlens.classification.report import (
    build_classification_sections,
    classification_report_to_markdown,
)

__all__ = [
    "ClassificationConfig",
    "DEFAULT_CONFIG",
    "FEATURE_SPACE_GROUP_COLS",
    "INTEREST_BEARING_CODES",
    "PARTICIPATION_CODES",
    "GROWTH_ASSET_GROUPS",
    "LOOKTHROUGH_ASSET_GROUPS",
    "build_allocation_features",
    "build_sub_window_features",
    "label_centroid",
    "assign_family",
    "describe_centroid",
    "translate_group",
    "translate_family",
    "AllocationClassifier",
    "FitInfo",
    "ScikitLearnUnavailable",
    "build_secondary_axes",
    "compute_support_weights",
    "classify_participation",
    "classify_risk_band",
    "classify_currency_band",
    "classify_lookthrough_band",
    "compute_stability",
    "classify_universe",
    "summarize_classification",
    "build_classification_sections",
    "classification_report_to_markdown",
]
