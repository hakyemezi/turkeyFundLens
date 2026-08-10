from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from besfundlens.classification import (
    AllocationClassifier,
    ClassificationConfig,
    classify_universe,
)
from besfundlens.classification.axes import build_secondary_axes
from besfundlens.classification.features import build_allocation_features
from besfundlens.classification.report import classification_report_to_markdown
from besfundlens.classification.taxonomy import deduplicate_labels, label_centroid
from besfundlens.core.asset_metadata import build_asset_metadata
from besfundlens.core.engine import initialize_engine, run_universe_analysis

# Four clearly separated allocation profiles. Twelve funds each keeps the
# universe above the default `min_funds_for_model`, so the clustering path runs.
PROFILES = {
    "EQ": {"hs": 90, "bpp": 10},
    "FI": {"dt": 70, "ost": 20, "bpp": 10},
    "GOLD": {"km": 95, "bpp": 5},
    "PART": {"kkstl": 55, "khtl": 30, "hs": 15},
}

N_PER_PROFILE = 12
N_DATES = 24


def build_synthetic_panel(
    profiles: dict = PROFILES,
    n_per_profile: int = N_PER_PROFILE,
    n_dates: int = N_DATES,
    seed: int = 0,
    extra_funds: list | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build (df_general, df_allocation) for a synthetic fund universe.

    `extra_funds` accepts entries of the form
    ``(code, allocation)`` for a constant fund, or
    ``(code, allocation_first_half, allocation_second_half)`` for a fund that
    switches allocation mid-window.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2026-01-01", periods=n_dates)

    general_rows = []
    allocation_rows = []

    def emit(code: str, name: str, allocation_for_index):
        price = 1.0
        for day_index, date in enumerate(dates):
            price *= 1 + rng.normal(0.001, 0.004)
            units = 1_000_000 + day_index * 500

            general_rows.append({
                "fonKodu": code,
                "fonUnvan": name,
                "tarih": date,
                "fiyat": round(price, 6),
                "tedPaySayisi": units,
                "kisiSayisi": 5_000 + day_index,
                "portfoyBuyukluk": price * units,
            })

            row = {"fonKodu": code, "fonUnvan": name, "tarih": date}
            for asset_code, weight in allocation_for_index(day_index).items():
                row[asset_code] = weight + rng.normal(0, 1.0)
            allocation_rows.append(row)

    for profile_name, allocation in profiles.items():
        for index in range(n_per_profile):
            emit(
                f"{profile_name}{index:02d}",
                f"{profile_name} Fund {index}",
                lambda _, allocation=allocation: allocation,
            )

    for entry in extra_funds or []:
        if len(entry) == 2:
            code, allocation = entry
            emit(code, f"{code} Fund", lambda _, allocation=allocation: allocation)
        else:
            code, first, second = entry
            emit(
                code,
                f"{code} Fund",
                lambda i, first=first, second=second: first if i < n_dates // 2 else second,
            )

    df_general = pd.DataFrame(general_rows)
    df_allocation = pd.DataFrame(allocation_rows).fillna(0.0)

    return df_general, df_allocation


@pytest.fixture(scope="module")
def engine_state():
    df_general, df_allocation = build_synthetic_panel()
    return initialize_engine(df_general, df_allocation)


@pytest.fixture(scope="module")
def classification(engine_state):
    return classify_universe(
        engine_state["df_panel_dna"],
        engine_state["asset_meta_df"],
        lookback=20,
    )


# ------------------------------------------------------------------
# Model
# ------------------------------------------------------------------

def test_model_recovers_distinct_profiles(classification):
    """Each seeded profile should collapse into exactly one discovered class."""
    fit_info = classification["fit_info"]
    assert fit_info.model_fitted is True
    assert fit_info.k == len(PROFILES)
    assert fit_info.silhouette > 0.5

    df = classification["classification_df"]
    profile = df["fonKodu"].str.replace(r"\d+$", "", regex=True)

    classes_per_profile = df.groupby(profile)["class_id"].nunique()
    assert (classes_per_profile == 1).all()

    # ...and no two profiles share a class.
    assert df["class_id"].nunique() == len(PROFILES)


def test_k_selection_respects_configured_range(engine_state):
    config = ClassificationConfig(k_range=(2, 3))
    result = classify_universe(
        engine_state["df_panel_dna"],
        engine_state["asset_meta_df"],
        lookback=20,
        config=config,
    )
    assert 2 <= result["fit_info"].k <= 3


def test_fixed_k_is_honoured(engine_state):
    config = ClassificationConfig(k=6)
    result = classify_universe(
        engine_state["df_panel_dna"],
        engine_state["asset_meta_df"],
        lookback=20,
        config=config,
    )
    assert result["fit_info"].k == 6


def test_save_load_round_trip(engine_state, classification, tmp_path):
    path = tmp_path / "model.json"
    classification["model"].save(path)

    loaded = AllocationClassifier.load(path)
    assert loaded.feature_names == classification["model"].feature_names
    assert loaded.class_labels_en == classification["model"].class_labels_en

    reused = classify_universe(
        engine_state["df_panel_dna"],
        engine_state["asset_meta_df"],
        lookback=20,
        model=loaded,
    )

    original = classification["classification_df"].set_index("fonKodu")["asset_class"]
    replayed = reused["classification_df"].set_index("fonKodu")["asset_class"]

    pd.testing.assert_series_equal(original, replayed)


def test_predict_without_model_and_without_fit_raises(engine_state):
    with pytest.raises(ValueError, match="requires an existing model"):
        classify_universe(
            engine_state["df_panel_dna"],
            engine_state["asset_meta_df"],
            lookback=20,
            fit=False,
        )


def test_rule_fallback_below_min_funds():
    """A small universe skips clustering but still yields meaningful classes."""
    df_general, df_allocation = build_synthetic_panel(n_per_profile=5, seed=3)
    state = initialize_engine(df_general, df_allocation)

    result = classify_universe(
        state["df_panel_dna"],
        state["asset_meta_df"],
        lookback=20,
    )

    fit_info = result["fit_info"]
    assert fit_info.model_fitted is False
    assert "min_funds_for_model" in fit_info.fallback_reason
    # One class per profile, not one class per fund.
    assert result["classification_df"]["asset_class"].nunique() == len(PROFILES)


# ------------------------------------------------------------------
# Confidence
# ------------------------------------------------------------------

def test_lookthrough_weight_lowers_confidence():
    df_general, df_allocation = build_synthetic_panel(
        seed=5,
        extra_funds=[("FOF00", {"yyf": 60, "dt": 30, "bpp": 10})],
    )
    state = initialize_engine(df_general, df_allocation)

    result = classify_universe(state["df_panel_dna"], state["asset_meta_df"], lookback=20)
    df = result["classification_df"].set_index("fonKodu")

    fof_confidence = df.loc["FOF00", "class_confidence"]
    transparent_confidence = df.loc["EQ00", "class_confidence"]

    assert fof_confidence < transparent_confidence
    assert df.loc["FOF00", "lookthrough_band"] == "Heavy Look-through"


def test_lookthrough_penalty_can_be_disabled():
    df_general, df_allocation = build_synthetic_panel(
        seed=5,
        extra_funds=[("FOF00", {"yyf": 60, "dt": 30, "bpp": 10})],
    )
    state = initialize_engine(df_general, df_allocation)

    penalised = classify_universe(
        state["df_panel_dna"], state["asset_meta_df"], lookback=20,
    )["classification_df"].set_index("fonKodu")

    raw = classify_universe(
        state["df_panel_dna"],
        state["asset_meta_df"],
        lookback=20,
        config=ClassificationConfig(lookthrough_penalty=False),
    )["classification_df"].set_index("fonKodu")

    assert raw.loc["FOF00", "class_confidence"] > penalised.loc["FOF00", "class_confidence"]


# ------------------------------------------------------------------
# Stability and drift
# ------------------------------------------------------------------

def test_style_drift_detects_mid_window_switch():
    df_general, df_allocation = build_synthetic_panel(
        seed=11,
        extra_funds=[("DRIFT0", {"hs": 90, "bpp": 10}, {"dt": 85, "bpp": 15})],
    )
    state = initialize_engine(df_general, df_allocation)

    result = classify_universe(state["df_panel_dna"], state["asset_meta_df"], lookback=20)
    df = result["classification_df"].set_index("fonKodu")

    assert df.loc["DRIFT0", "style_drift"] > 100
    assert df.loc["DRIFT0", "style_drift"] > df.loc["EQ00", "style_drift"] * 10
    assert df.loc["DRIFT0", "class_stability"] < 1.0
    assert df.loc["EQ00", "class_stability"] == 1.0


def test_short_history_fund_is_not_reported_as_drifting():
    """
    A fund that launched mid-window has no earlier allocation to be compared
    against. Filling its missing sub-windows with zeros would put it at the top
    of the style-drift watchlist without it ever changing a holding.
    """
    df_general, df_allocation = build_synthetic_panel(seed=13)

    # Keep only the last 6 observations for one fund, as if it had just launched.
    late = df_general["fonKodu"].eq("EQ00")
    keep_dates = df_general.loc[late, "tarih"].sort_values().tail(6)

    df_general = df_general[~late | df_general["tarih"].isin(keep_dates)]
    df_allocation = df_allocation[
        ~df_allocation["fonKodu"].eq("EQ00") | df_allocation["tarih"].isin(keep_dates)
    ]

    state = initialize_engine(df_general, df_allocation)
    result = classify_universe(state["df_panel_dna"], state["asset_meta_df"], lookback=20)
    row = result["classification_df"].set_index("fonKodu").loc["EQ00"]

    assert row["n_observations"] == 6
    assert pd.isna(row["style_drift"])
    assert row["class_stability"] == 1.0
    # It is still classified — only the drift history is unavailable.
    assert row["asset_class"] == "Equity Weighted"


def test_stable_funds_report_full_stability(classification):
    df = classification["classification_df"]
    assert (df["class_stability"] == 1.0).all()
    assert df["n_sub_windows"].iloc[0] == 4


# ------------------------------------------------------------------
# Secondary axes
# ------------------------------------------------------------------

def test_participation_axis(classification):
    df = classification["classification_df"].set_index("fonKodu")

    # PART holds only lease certificates, participation accounts and equity.
    assert df.loc["PART00", "participation_class"] == "Participation"
    assert df.loc["PART00", "participation_class_tr"] == "Katılım"

    # FI holds government and corporate bonds.
    assert df.loc["FI00", "participation_class"] == "Conventional"
    assert df.loc["FI00", "interest_bearing_weight"] > 90


def test_committed_transactions_market_is_participation_compatible():
    """
    `btaa` / `btas` (BIST Taahhutlu Islemler Pazari) must not read as interest.

    It is the participation-compatible route to short-term liquidity, and two
    thirds of the funds named "katilim" in the live BES universe hold it.
    Treating it as repo mislabels most of them as conventional.
    """
    df_general, df_allocation = build_synthetic_panel(
        seed=17,
        extra_funds=[("KAT000", {"kkstl": 60, "khtl": 25, "btas": 15})],
    )
    state = initialize_engine(df_general, df_allocation)

    result = classify_universe(state["df_panel_dna"], state["asset_meta_df"], lookback=20)
    row = result["classification_df"].set_index("fonKodu").loc["KAT000"]

    assert row["participation_class"] == "Participation"
    assert row["interest_bearing_weight"] < 1.0


def test_pledged_collateral_still_counts_as_interest_exposure():
    """
    A negative repo leg is collateral pledged to borrow, not a short.

    The asset cannot be reported as both the holding and the cash raised against
    it, so the leg comes through negative and the row still totals 100. The
    participation verdict asks whether the fund is party to an interest-bearing
    transaction at all, and a repo entered from the borrowing side is still a
    repo — so its magnitude counts, and a signed sum would clear the screen for
    a fund that plainly does not qualify.
    """
    df_general, df_allocation = build_synthetic_panel(
        seed=19,
        extra_funds=[("PLEDGE", {"kkstl": 70, "khtl": 40, "r": -10})],
    )
    state = initialize_engine(df_general, df_allocation)

    result = classify_universe(state["df_panel_dna"], state["asset_meta_df"], lookback=20)
    row = result["classification_df"].set_index("fonKodu").loc["PLEDGE"]

    assert row["participation_class"] == "Conventional"
    assert row["interest_bearing_weight"] > 5      # |-10| survives, not -10
    assert row["participation_asset_weight"] > 100  # signed, so the book still nets to 100


def test_compositional_weights_stay_signed():
    """
    Only the interest screen uses magnitude. The currency weights are a
    decomposition of the published book, so a pledged leg must net out there
    rather than inflating exposure past 100.
    """
    df_general, df_allocation = build_synthetic_panel(
        seed=29,
        extra_funds=[("PLEDG2", {"hs": 85, "dt": 25, "r": -10})],
    )
    state = initialize_engine(df_general, df_allocation)

    result = classify_universe(state["df_panel_dna"], state["asset_meta_df"], lookback=20)
    row = result["classification_df"].set_index("fonKodu").loc["PLEDG2"]

    currency_total = row["try_weight"] + row["fx_weight"] + row["gold_weight"]
    assert currency_total <= 100.5


def test_invisible_portfolio_is_mixed_not_participation():
    """
    Zero observed interest exposure is not enough when most of the portfolio is
    held in other funds — there is nothing to vouch for.
    """
    df_general, df_allocation = build_synthetic_panel(
        seed=23,
        extra_funds=[("FOFKAT", {"yyf": 82, "osks": 18})],
    )
    state = initialize_engine(df_general, df_allocation)

    result = classify_universe(state["df_panel_dna"], state["asset_meta_df"], lookback=20)
    row = result["classification_df"].set_index("fonKodu").loc["FOFKAT"]

    assert row["interest_bearing_weight"] < 1.0
    assert row["participation_class"] == "Mixed"


def test_currency_and_risk_bands(classification):
    df = classification["classification_df"].set_index("fonKodu")

    assert df.loc["GOLD00", "currency_band"] == "Gold Weighted"
    assert df.loc["EQ00", "currency_band"] == "TRY Weighted"

    assert df.loc["FI00", "risk_band"] == "Conservative"
    assert df.loc["EQ00", "risk_band"] == "Specialised"
    assert df.loc["PART00", "risk_band_tr"] == "Dengeli"


def test_band_thresholds_are_configurable(engine_state):
    """Same data, different config, different band."""
    features, meta = build_allocation_features(
        engine_state["df_panel_dna"],
        engine_state["asset_meta_df"],
        lookback=20,
    )
    asset_meta = build_asset_metadata()

    strict = build_secondary_axes(
        features, meta, asset_meta, ClassificationConfig(risk_band_edges=(10.0, 35.0, 95.0))
    )
    loose = build_secondary_axes(
        features, meta, asset_meta, ClassificationConfig(risk_band_edges=(1.0, 5.0, 10.0))
    )

    # 90% equity: below a 95 cut point it is "Aggressive", above a 10 one it is "Specialised".
    assert strict.loc["EQ00", "risk_band"] == "Aggressive"
    assert loose.loc["EQ00", "risk_band"] == "Specialised"


def test_data_driven_risk_banding(engine_state):
    for method in ("quantile", "kmeans1d"):
        result = classify_universe(
            engine_state["df_panel_dna"],
            engine_state["asset_meta_df"],
            lookback=20,
            config=ClassificationConfig(risk_band_method=method),
        )
        bands = result["classification_df"]["risk_band"]
        assert bands.notna().all()
        assert bands.nunique() > 1


# ------------------------------------------------------------------
# Taxonomy
# ------------------------------------------------------------------

def test_label_centroid_naming_rules():
    features = ["Equity", "Fixed Income", "Money Market"]
    config = ClassificationConfig()

    assert label_centroid([80, 15, 5], features, config) == "Equity Weighted"
    assert label_centroid([45, 40, 15], features, config) == "Equity Tilted Multi-Asset"
    assert label_centroid([35, 35, 30], features, config) == "Multi-Asset (Equity / Fixed Income)"
    assert label_centroid([0, 0, 0], features, config) == "Unclassified"


def test_label_centroid_turkish():
    features = ["Equity", "Fixed Income"]
    assert label_centroid([80, 20], features, ClassificationConfig(), "tr") == "Hisse Senedi Ağırlıklı"


def test_duplicate_class_names_are_disambiguated():
    features = ["Fixed Income", "Equity", "Money Market"]
    centroids = [[80, 15, 5], [80, 5, 15]]
    labels = ["Fixed Income Weighted", "Fixed Income Weighted"]

    resolved = deduplicate_labels(labels, centroids, features)

    assert len(set(resolved)) == 2
    assert all(label.startswith("Fixed Income Weighted") for label in resolved)


def test_detailed_feature_space_keeps_names_and_families(engine_state):
    """
    The finer spaces must not fall back to "Other" families or mangled casing.

    `FAMILY_BY_GROUP` is written against broad groups; the detailed space uses
    `asset_group` labels, which inherit their family from the broad group.
    """
    result = classify_universe(
        engine_state["df_panel_dna"],
        engine_state["asset_meta_df"],
        lookback=20,
        config=ClassificationConfig(feature_space="detailed"),
    )
    df = result["classification_df"]

    assert (df["asset_class_family"] != "Other").all()
    assert df.loc[df["fonKodu"].eq("GOLD00"), "asset_class_family"].iloc[0] == "Precious Metals"

    # Detailed group names keep their published casing rather than being title-cased.
    features = result["features"]
    assert "Government Fixed Income" in features.columns
    assert not any(name.endswith(" Fx") for name in features.columns)


def test_broad_feature_names_match_dna_vocabulary(engine_state):
    """Broad feature labels must stay identical to the engine's DNA group labels."""
    features, _ = build_allocation_features(
        engine_state["df_panel_dna"],
        engine_state["asset_meta_df"],
        lookback=20,
    )
    for expected in ("Equity", "Fixed Income", "Money Market", "Precious Metals",
                     "Lease Certificates", "Participation Account"):
        assert expected in features.columns


def test_class_names_are_unique(classification):
    model = classification["model"]
    assert len(set(model.class_labels_en)) == len(model.class_labels_en)
    assert len(set(model.class_labels_tr)) == len(model.class_labels_tr)


# ------------------------------------------------------------------
# Engine integration and reporting
# ------------------------------------------------------------------

def test_run_universe_analysis_merges_classification(engine_state):
    result = run_universe_analysis(lookback=20, valid_only=False, top_n=5)
    lens = result["lens_universe_df"]

    for column in ("asset_class", "risk_band", "currency_band",
                   "participation_class", "lookthrough_band", "class_confidence"):
        assert column in lens.columns

    # The legacy rule-based archetype is preserved alongside the new class.
    assert "archetype" in lens.columns
    assert lens["archetype"].equals(lens["legacy_archetype"])

    assert "## Asset Allocation Classes" in result["markdown"]


def test_classification_can_be_disabled(engine_state):
    result = run_universe_analysis(lookback=20, valid_only=False, classify=False)

    assert result["classification_df"] is None
    assert "asset_class" not in result["lens_universe_df"].columns
    assert "## Asset Allocation Classes" not in result["markdown"]


def test_report_renders_in_both_languages(classification):
    df = classification["classification_df"]
    fit_info = classification["fit_info"]

    english = classification_report_to_markdown(df, fit_info, language="en")
    turkish = classification_report_to_markdown(df, fit_info, language="tr")

    assert "## Asset Allocation Classes" in english
    assert "## Risk Bands" in english
    assert "## Varlık Dağılımı Sınıfları" in turkish
    assert "## Risk Bantları" in turkish
    assert "Katılım" in turkish


def test_config_validation():
    with pytest.raises(ValueError, match="feature_space"):
        ClassificationConfig(feature_space="nonsense")

    with pytest.raises(ValueError, match="risk_band_method"):
        ClassificationConfig(risk_band_method="magic")

    with pytest.raises(ValueError, match="ascending"):
        ClassificationConfig(risk_band_edges=(50.0, 10.0, 70.0))

    with pytest.raises(ValueError, match="k_range"):
        ClassificationConfig(k_range=(10, 4))


def test_config_round_trip():
    config = ClassificationConfig(k=7, risk_band_edges=(5.0, 20.0, 60.0), transform="hellinger")
    restored = ClassificationConfig.from_dict(config.to_dict())

    assert restored == config
