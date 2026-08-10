from besfundlens import BUILD_VERSION, resolve_lookback_intervals
from besfundlens.core.engine import translate_quadrant_name


def test_version_available():
    assert "repo-stable" in BUILD_VERSION


def test_lookback_presets():
    assert resolve_lookback_intervals("1m") == 20
    assert resolve_lookback_intervals("3m") == 60
    assert resolve_lookback_intervals(45) == 45


def test_tr_quadrant_translation():
    assert translate_quadrant_name("Negative Market / Negative Flow", "tr") == "Negatif Piyasa / Negatif Akış"


def test_moved_helpers_still_importable_from_engine():
    """v0.2.0 moved these out of engine.py; the re-exports must keep working."""
    from besfundlens.core.engine import (  # noqa: F401
        add_dna_columns,
        asset_group_map,
        broad_asset_group_map,
        build_asset_metadata,
        build_dna_panel,
        clean_dna_label,
        currency_exposure_map,
        format_pct,
        make_safe_col_name,
        market_scope_map,
        parse_tarih,
        safe_divide,
        validate_asset_metadata,
    )

    assert safe_divide(10, 4) == 2.5
    assert make_safe_col_name("Foreign / International") == "foreign_international"
    assert broad_asset_group_map["hs"] == "Equity"


def test_classification_public_api():
    from besfundlens import (  # noqa: F401
        AllocationClassifier,
        ClassificationConfig,
        classification_markdown_from_sqlite,
        classification_report_to_markdown,
        classify_funds_from_sqlite,
        classify_universe,
        run_allocation_classification,
        summarize_classification,
    )

    config = ClassificationConfig()
    assert config.group_col == "broad_asset_group"
    assert config.feature_space == "broad"
