"""
Configuration for the besFundLens allocation classification layer.

Every threshold used by the classifier lives here. Nothing is hard-coded in the
classification functions themselves, so a caller can re-band the universe
without touching the code:

    config = ClassificationConfig(risk_band_edges=(5.0, 25.0, 50.0))
    result = classify_universe(panel_df, asset_meta_df, config=config)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Optional, Tuple

# Feature space -> asset metadata column used to aggregate raw allocation columns.
FEATURE_SPACE_GROUP_COLS = {
    "broad": "broad_asset_group",
    "detailed": "asset_group",
    "raw": None,  # raw instrument codes, no aggregation
}

# Instrument codes that carry interest (riba). A fund holding none of these
# above `participation_tolerance` is treated as participation / interest-free.
# Lease certificates (kira sertifikasi), participation accounts (katilma hesabi)
# and precious metals are intentionally absent: they are the instruments
# participation funds actually use.
#
# Note on money markets: `bpp` (Borsa Istanbul) and `tpp` (Takasbank) money
# markets and repo/reverse-repo are interest-bearing, and Turkish participation
# funds are indeed not observed holding them. `btaa` / `btas` are NOT here -
# see PARTICIPATION_CODES.
INTEREST_BEARING_CODES = (
    "dt", "hb", "kibd", "kba", "ybkb", "yba", "eut", "db", "dot",
    "fb", "ost", "bb", "vdm", "osdb", "ybosb",
    "vmtl", "vmd", "vm", "vmau",
    "r", "tr", "bpp", "tpp",
)

# Instruments a participation fund may hold. Anything outside both this set and
# INTEREST_BEARING_CODES (derivatives, generic funds, "other") is ambiguous and
# pushes the fund towards the mixed bucket rather than a clean verdict.
#
# `btaa` / `btas` (BIST Taahhutlu Islemler Pazari, the committed-transactions
# market) belong here rather than with repo. It is a sale-with-repurchase-
# commitment structure created as the participation-compatible route to
# short-term liquidity, and two thirds of the funds that call themselves
# "katilim" in the live BES universe hold it.
PARTICIPATION_CODES = (
    "kkstl", "kksd", "osks", "kksyd", "oksyd", "kks",
    "khtl", "khd", "khau", "kh",
    "km", "kmbyf", "kmkba", "kmkks",
    "hs", "yhs",
    "gas", "gyy", "gsyy", "gykb", "gsykb",
    "btaa", "btas",
)

# Broad asset groups that drive the risk band (growth / volatile assets).
GROWTH_ASSET_GROUPS = (
    "Equity",
    "Foreign Equity",
    "Precious Metals",
    "Real Estate / Alternative",
    "Venture Capital / Alternative",
)

# Broad asset groups whose true exposure is unknown without underlying holdings.
LOOKTHROUGH_ASSET_GROUPS = (
    "Fund",
    "ETF",
    "Foreign ETF",
)


@dataclass(frozen=True)
class ClassificationConfig:
    """Tunable parameters for the allocation classification pipeline."""

    # --- feature space -------------------------------------------------
    feature_space: str = "broad"
    renormalize: bool = True
    transform: str = "none"  # "none" | "hellinger"

    # --- clustering model ----------------------------------------------
    k: Optional[int] = None          # None -> silhouette-selected
    k_range: Tuple[int, int] = (4, 16)
    random_state: int = 42
    n_init: int = 10
    min_funds_for_model: int = 40    # below this, fall back to per-fund labelling

    # --- taxonomy (centroid -> human-readable name) ---------------------
    dominant_threshold: float = 60.0
    primary_threshold: float = 40.0

    # --- confidence ------------------------------------------------------
    lookthrough_penalty: bool = True
    low_confidence_threshold: float = 0.25

    # --- stability / drift ----------------------------------------------
    sub_window_count: int = 4

    # --- secondary axis: participation -----------------------------------
    participation_tolerance: float = 1.0    # max interest-bearing weight, %
    participation_min_coverage: float = 60.0  # min recognised participation weight, %

    # --- secondary axis: risk band ---------------------------------------
    risk_band_method: str = "fixed"  # "fixed" | "quantile" | "kmeans1d"
    risk_band_edges: Tuple[float, float, float] = (10.0, 35.0, 65.0)

    # --- secondary axis: currency band -----------------------------------
    currency_band_threshold: float = 60.0

    # --- secondary axis: look-through band -------------------------------
    lookthrough_band_edges: Tuple[float, float] = (5.0, 25.0)

    # --- data quality ----------------------------------------------------
    min_dagilim_total: float = 90.0
    max_dagilim_total: float = 105.0
    min_observations: int = 1

    # --- instrument sets (overridable) ------------------------------------
    interest_bearing_codes: Tuple[str, ...] = field(default=INTEREST_BEARING_CODES)
    participation_codes: Tuple[str, ...] = field(default=PARTICIPATION_CODES)
    growth_asset_groups: Tuple[str, ...] = field(default=GROWTH_ASSET_GROUPS)
    lookthrough_asset_groups: Tuple[str, ...] = field(default=LOOKTHROUGH_ASSET_GROUPS)

    def __post_init__(self):
        if self.feature_space not in FEATURE_SPACE_GROUP_COLS:
            raise ValueError(
                f"Unknown feature_space: {self.feature_space}. "
                f"Use one of {sorted(FEATURE_SPACE_GROUP_COLS)}."
            )

        if self.transform not in {"none", "hellinger"}:
            raise ValueError(f"Unknown transform: {self.transform}. Use 'none' or 'hellinger'.")

        if self.risk_band_method not in {"fixed", "quantile", "kmeans1d"}:
            raise ValueError(
                f"Unknown risk_band_method: {self.risk_band_method}. "
                "Use 'fixed', 'quantile' or 'kmeans1d'."
            )

        k_min, k_max = self.k_range
        if k_min < 2 or k_max < k_min:
            raise ValueError(f"Invalid k_range: {self.k_range}. Expected 2 <= k_min <= k_max.")

        if self.k is not None and self.k < 2:
            raise ValueError("k must be at least 2 when set explicitly.")

        if self.sub_window_count < 1:
            raise ValueError("sub_window_count must be at least 1.")

        if not (0.0 <= self.dominant_threshold <= 100.0):
            raise ValueError("dominant_threshold must be between 0 and 100.")

        if self.primary_threshold > self.dominant_threshold:
            raise ValueError("primary_threshold must not exceed dominant_threshold.")

        if list(self.risk_band_edges) != sorted(self.risk_band_edges):
            raise ValueError("risk_band_edges must be ascending.")

        if list(self.lookthrough_band_edges) != sorted(self.lookthrough_band_edges):
            raise ValueError("lookthrough_band_edges must be ascending.")

    @property
    def group_col(self) -> Optional[str]:
        """Asset metadata column used to aggregate raw allocation columns."""
        return FEATURE_SPACE_GROUP_COLS[self.feature_space]

    def to_dict(self) -> dict:
        """JSON-serialisable form, used inside the saved model artifact."""
        payload = asdict(self)
        for key, value in payload.items():
            if isinstance(value, tuple):
                payload[key] = list(value)
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "ClassificationConfig":
        """Rebuild a config from `to_dict()` output, ignoring unknown keys."""
        known = {f.name: f for f in fields(cls)}
        kwargs = {}

        for key, value in (payload or {}).items():
            if key not in known:
                continue
            if isinstance(known[key].default, tuple) or key.endswith(("_range", "_edges", "_codes", "_groups")):
                value = tuple(value) if isinstance(value, list) else value
            kwargs[key] = value

        return cls(**kwargs)


DEFAULT_CONFIG = ClassificationConfig()
