"""
The v1 labels the engine puts in lens_universe_df were English only, whatever
the report language was. These cover the translations that fixed that.
"""

from besfundlens.classification.taxonomy import GROUP_LABELS_TR
from besfundlens.core.engine import (
    FLOW_REGIME_TRANSLATIONS,
    broad_asset_group_map,
    classify_flow_regime_v2,
    classify_flow_magnitude,
    translate_archetype,
    translate_flow_regime,
)


def test_named_archetypes_translate():
    assert translate_archetype("Money Market Fund", "tr") == "Para Piyasası Fonu"
    assert translate_archetype("Gold / Precious Metals Fund", "tr") == "Altın / Kıymetli Maden Fonu"


def test_dominant_fund_archetypes_are_built_from_the_group_labels():
    """The "{group} Dominant Fund" family is generated, not listed."""
    assert translate_archetype("Deposit Dominant Fund", "tr") == "Mevduat Ağırlıklı Fon"
    assert translate_archetype("Participation Account Dominant Fund", "tr") == "Katılma Hesabı Ağırlıklı Fon"


def test_every_asset_group_yields_a_translated_archetype():
    """A group added to the map must not silently fall back to English."""
    for group in set(broad_asset_group_map.values()):
        archetype = f"{group} Dominant Fund"
        assert translate_archetype(archetype, "tr") != archetype, group
        assert group in GROUP_LABELS_TR


def test_flow_regimes_translate_with_the_clause_first():
    assert (
        translate_flow_regime("Strong net inflow with participant growth", "tr")
        == "Katılımcı artışıyla güçlü net giriş"
    )
    assert (
        translate_flow_regime("Moderate net outflow despite participant growth", "tr")
        == "Katılımcı artışına rağmen ılımlı net çıkış"
    )
    assert translate_flow_regime("Neutral flow regime", "tr") == "Nötr akış rejimi"


def test_every_regime_the_engine_can_produce_is_covered():
    """
    Generated from the same inputs classify_flow_regime_v2 branches on, so a new
    magnitude or clause shows up here rather than as an English label in the UI.
    """
    flows = [0.2, 0.05, 0.005, 0.001, 0.0, -0.001, -0.005, -0.05, -0.2]
    produced = {
        classify_flow_regime_v2(flow, participants)
        for flow in flows
        for participants in (1, 0, -1)
    }
    missing = [regime for regime in produced if regime not in FLOW_REGIME_TRANSLATIONS["tr"]]
    assert not missing, missing


def test_every_magnitude_has_a_turkish_word():
    magnitudes = {classify_flow_magnitude(v) for v in (0.2, 0.05, 0.005, 0.0001, float("nan"))}
    for magnitude in magnitudes:
        assert any(
            key.startswith(magnitude) for key in FLOW_REGIME_TRANSLATIONS["tr"]
        ) or magnitude in ("Unknown",), magnitude


def test_english_is_left_alone():
    for label in ("Money Market Fund", "Deposit Dominant Fund"):
        assert translate_archetype(label, "en") == label
    assert (
        translate_flow_regime("Strong net inflow with participant growth", "en")
        == "Strong net inflow with participant growth"
    )


def test_unknown_labels_pass_through_rather_than_raising():
    assert translate_archetype("Something New Fund", "tr") == "Something New Fund"
    assert translate_flow_regime("Some new regime", "tr") == "Some new regime"
    assert translate_archetype(None, "tr") is None


def test_dna_labels_translate():
    from besfundlens.core.engine import (
        translate_asset_group,
        translate_currency_exposure,
        translate_market_scope,
    )

    assert translate_asset_group("Fixed Income", "tr") == "Sabit Getirili"
    assert translate_market_scope("Domestic", "tr") == "Yurt içi"
    assert translate_currency_exposure("FX", "tr") == "Döviz"

    # a currency code is a code in both languages
    assert translate_currency_exposure("TRY", "tr") == "TRY"

    for label in ("Fixed Income", "Domestic", "FX"):
        assert translate_asset_group(label, "en") == label
        assert translate_market_scope(label, "en") == label
        assert translate_currency_exposure(label, "en") == label


def test_every_dna_value_the_engine_emits_is_covered():
    """Guards against a scope or currency label being added without a translation."""
    from besfundlens.core.engine import (
        CURRENCY_TRANSLATIONS,
        SCOPE_TRANSLATIONS,
        currency_exposure_map,
        market_scope_map,
    )

    for value in set(market_scope_map.values()):
        assert value in SCOPE_TRANSLATIONS["tr"], value
    for value in set(currency_exposure_map.values()):
        assert value in CURRENCY_TRANSLATIONS["tr"], value
