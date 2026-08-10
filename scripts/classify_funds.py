from __future__ import annotations

import argparse
from pathlib import Path

from besfundlens.classification import ClassificationConfig
from besfundlens.classification.report import classification_report_to_markdown
from besfundlens.workflows import classify_funds_from_sqlite


def build_config(args: argparse.Namespace) -> ClassificationConfig:
    overrides = {"feature_space": args.feature_space}

    if args.k is not None:
        overrides["k"] = args.k
    if args.risk_band_method is not None:
        overrides["risk_band_method"] = args.risk_band_method
    if args.min_funds_for_model is not None:
        overrides["min_funds_for_model"] = args.min_funds_for_model
    if args.transform is not None:
        overrides["transform"] = args.transform

    return ClassificationConfig(**overrides)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Classify Turkish pension funds by asset allocation. "
            "Use --fit to discover classes, --predict to assign funds to an existing model."
        )
    )
    parser.add_argument("--db-path", default="data/besfundlens.sqlite")
    parser.add_argument("--lookback", default="3m")
    parser.add_argument("--language", choices=["en", "tr"], default="en")
    parser.add_argument("--output", default="reports/classification.md",
                        help="Output path. A .csv extension writes the full table, anything else writes Markdown.")
    parser.add_argument("--top-n", type=int, default=15)
    parser.add_argument("--fund-codes", nargs="*", default=None,
                        help="Restrict the run to specific fund codes.")

    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument("--fit", action="store_true",
                             help="Fit a new model (default when no model path is given).")
    model_group.add_argument("--predict", action="store_true",
                             help="Assign funds to an existing model without refitting.")

    parser.add_argument("--model-path", default=None,
                        help="Model artifact to load (--predict) or write (--fit).")
    parser.add_argument("--feature-space", choices=["broad", "detailed", "raw"], default="broad")
    parser.add_argument("--transform", choices=["none", "hellinger"], default=None)
    parser.add_argument("--k", type=int, default=None,
                        help="Fix the class count instead of selecting it by silhouette score.")
    parser.add_argument("--risk-band-method", choices=["fixed", "quantile", "kmeans1d"], default=None)
    parser.add_argument("--min-funds-for-model", type=int, default=None)

    args = parser.parse_args()

    if args.predict and not args.model_path:
        parser.error("--predict requires --model-path.")

    fit = not args.predict
    save_model_to = args.model_path if (fit and args.model_path) else None

    result = classify_funds_from_sqlite(
        db_path=args.db_path,
        lookback=args.lookback,
        fund_codes=args.fund_codes,
        config=build_config(args),
        model_path=args.model_path if args.predict else None,
        fit=fit,
        save_model_to=save_model_to,
    )

    classification_df = result["classification_df"]
    fit_info = result["fit_info"]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.suffix.lower() == ".csv":
        classification_df.to_csv(output, index=False, encoding="utf-8")
    else:
        markdown = classification_report_to_markdown(
            classification_df,
            fit_info=fit_info,
            language=args.language,
            top_n=args.top_n,
        )
        output.write_text(markdown, encoding="utf-8")

    classified = int(classification_df["asset_class"].notna().sum())
    mode = "KMeans" if fit_info.model_fitted else f"rule fallback ({fit_info.fallback_reason})"

    print(f"Classification saved: {output}")
    print(f"Model: {mode} | classes: {fit_info.k} | classified funds: {classified}")
    if fit_info.silhouette is not None:
        print(f"Silhouette score: {fit_info.silhouette:.3f}")
    if save_model_to:
        print(f"Model artifact saved: {save_model_to}")


if __name__ == "__main__":
    main()
