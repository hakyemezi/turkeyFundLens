"""besFundLens: analytics engine for Turkish pension funds."""

from .core.engine import (
    BUILD_VERSION,
    LOOKBACK_PRESETS,
    initialize_engine,
    run_universe_analysis,
    run_universe_analysis_from_dataframes,
    run_allocation_classification,
    compare_funds,
    compare_funds_from_dataframes,
    selected_funds_report_to_markdown,
    generate_selected_funds_report,
    save_markdown_report,
    print_build_info,
    resolve_lookback_intervals,
)

from .classification import (
    AllocationClassifier,
    ClassificationConfig,
    classification_report_to_markdown,
    classify_universe,
    summarize_classification,
)

from .workflows import (
    run_universe_analysis_from_sqlite,
    compare_funds_from_sqlite,
    build_or_update_cache_then_run,
    selected_funds_markdown_from_sqlite,
    classify_funds_from_sqlite,
    classification_markdown_from_sqlite,
)

__all__ = [
    "BUILD_VERSION",
    "LOOKBACK_PRESETS",
    "initialize_engine",
    "run_universe_analysis",
    "run_universe_analysis_from_dataframes",
    "run_universe_analysis_from_sqlite",
    "compare_funds",
    "compare_funds_from_dataframes",
    "compare_funds_from_sqlite",
    "build_or_update_cache_then_run",
    "selected_funds_report_to_markdown",
    "selected_funds_markdown_from_sqlite",
    "generate_selected_funds_report",
    "save_markdown_report",
    "print_build_info",
    "resolve_lookback_intervals",
    # v2 allocation classification
    "AllocationClassifier",
    "ClassificationConfig",
    "classify_universe",
    "classify_funds_from_sqlite",
    "classification_markdown_from_sqlite",
    "classification_report_to_markdown",
    "summarize_classification",
    "run_allocation_classification",
]
