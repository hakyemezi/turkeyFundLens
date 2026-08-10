from __future__ import annotations

from typing import Optional, Sequence, Union

from besfundlens.core.engine import (
    DEFAULT_LANGUAGE,
    initialize_engine,
    run_allocation_classification,
    run_universe_analysis,
    compare_funds,
    selected_funds_report_to_markdown,
)
from besfundlens.classification.report import classification_report_to_markdown
from besfundlens.data.loaders import load_data
from besfundlens.storage.sqlite_store import update_sqlite_cache


def run_universe_analysis_from_sqlite(
    db_path,
    lookback: Optional[Union[str, int]] = "1m",
    valid_only: bool = True,
    language: str = DEFAULT_LANGUAGE,
    top_n: int = 10,
    classify: bool = True,
    classification_config=None,
    classification_model_path=None,
    fit_classifier: bool = True,
    save_classifier_to=None,
) -> dict:
    df_general, df_allocation = load_data(source="sqlite", db_path=db_path)
    initialize_engine(df_general, df_allocation)
    return run_universe_analysis(
        lookback=lookback,
        valid_only=valid_only,
        language=language,
        top_n=top_n,
        classify=classify,
        classification_config=classification_config,
        classification_model_path=classification_model_path,
        fit_classifier=fit_classifier,
        save_classifier_to=save_classifier_to,
    )


def classify_funds_from_sqlite(
    db_path,
    lookback: Optional[Union[str, int]] = "1m",
    fund_codes: Optional[Sequence[str]] = None,
    config=None,
    model_path=None,
    fit: bool = True,
    save_model_to=None,
) -> dict:
    """
    Classify funds by asset allocation using a SQLite cache.

    Pass ``model_path`` with ``fit=False`` to assign funds to the classes of an
    already-fitted model instead of discovering new ones, which is what keeps
    class names comparable between reporting periods.
    """
    df_general, df_allocation = load_data(source="sqlite", db_path=db_path)
    initialize_engine(df_general, df_allocation)
    return run_allocation_classification(
        lookback=lookback,
        fund_codes=fund_codes,
        config=config,
        model_path=model_path,
        fit=fit,
        save_model_to=save_model_to,
    )


def classification_markdown_from_sqlite(
    db_path,
    lookback: Optional[Union[str, int]] = "1m",
    fund_codes: Optional[Sequence[str]] = None,
    config=None,
    model_path=None,
    fit: bool = True,
    language: str = DEFAULT_LANGUAGE,
    top_n: int = 15,
) -> str:
    """Standalone allocation classification report as Markdown."""
    result = classify_funds_from_sqlite(
        db_path=db_path,
        lookback=lookback,
        fund_codes=fund_codes,
        config=config,
        model_path=model_path,
        fit=fit,
    )
    return classification_report_to_markdown(
        result["classification_df"],
        fit_info=result["fit_info"],
        language=language,
        top_n=top_n,
    )


def compare_funds_from_sqlite(
    db_path,
    fund_codes: Sequence[str],
    lookback: Optional[Union[str, int]] = "1m",
    sort_by: Optional[str] = None,
    ascending: bool = False,
):
    df_general, df_allocation = load_data(source="sqlite", db_path=db_path)
    initialize_engine(df_general, df_allocation)
    return compare_funds(
        fund_codes=fund_codes,
        lookback=lookback,
        sort_by=sort_by,
        ascending=ascending,
    )


def build_or_update_cache_then_run(
    db_path,
    start_date=None,
    end_date=None,
    lookback: Optional[Union[str, int]] = "1m",
    language: str = DEFAULT_LANGUAGE,
    top_n: int = 10,
    verbose: bool = True,
) -> dict:
    update_info = update_sqlite_cache(
        db_path=db_path,
        start_date=start_date,
        end_date=end_date,
        verbose=verbose,
    )
    result = run_universe_analysis_from_sqlite(
        db_path=db_path,
        lookback=lookback,
        language=language,
        top_n=top_n,
    )
    result["update_info"] = update_info
    return result


def selected_funds_markdown_from_sqlite(
    db_path,
    fund_codes: Sequence[str],
    lookback: Optional[Union[str, int]] = "1m",
    language: str = DEFAULT_LANGUAGE,
) -> str:
    comparison_df = compare_funds_from_sqlite(
        db_path=db_path,
        fund_codes=fund_codes,
        lookback=lookback,
    )
    return selected_funds_report_to_markdown(comparison_df, language=language)
