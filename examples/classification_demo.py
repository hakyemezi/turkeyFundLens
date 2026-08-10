from __future__ import annotations

from besfundlens.classification import ClassificationConfig
from besfundlens.classification.report import classification_report_to_markdown
from besfundlens.core.engine import save_markdown_report
from besfundlens.workflows import classify_funds_from_sqlite

DB_PATH = "data/besfundlens.sqlite"
MODEL_PATH = "models/allocation_classifier.json"

# Fit over a 3-month window and keep the model, so later runs can assign funds
# to these same classes instead of discovering new ones.
result = classify_funds_from_sqlite(
    db_path=DB_PATH,
    lookback="3m",
    save_model_to=MODEL_PATH,
)

df = result["classification_df"]
fit_info = result["fit_info"]

print(f"Classes: {fit_info.k} | silhouette: {fit_info.silhouette:.3f} | funds: {len(df)}")
print()
print(
    df[[
        "fonKodu",
        "asset_class",
        "asset_class_family",
        "class_confidence",
        "risk_band",
        "currency_band",
        "participation_class",
        "style_drift",
    ]]
    .sort_values("class_confidence")
    .head(10)
    .to_string(index=False)
)

save_markdown_report(
    classification_report_to_markdown(df, fit_info, language="en"),
    "sample_reports/classification_report_en.md",
)
save_markdown_report(
    classification_report_to_markdown(df, fit_info, language="tr"),
    "sample_reports/classification_report_tr.md",
)

# Same model, shorter window: the class names still mean the same thing.
recent = classify_funds_from_sqlite(
    db_path=DB_PATH,
    lookback="1m",
    model_path=MODEL_PATH,
    fit=False,
)

moved = recent["classification_df"].merge(
    df[["fonKodu", "asset_class"]].rename(columns={"asset_class": "asset_class_3m"}),
    on="fonKodu",
)
moved = moved[moved["asset_class"].notna() & moved["asset_class"].ne(moved["asset_class_3m"])]

print(f"\nFunds that changed class between the 3m and 1m windows: {len(moved)}")
if not moved.empty:
    print(moved[["fonKodu", "asset_class_3m", "asset_class", "style_drift"]].to_string(index=False))

# Every threshold is configurable, and the risk band can be data-driven.
custom = ClassificationConfig(
    feature_space="detailed",
    k=10,
    risk_band_method="quantile",
)
detailed = classify_funds_from_sqlite(db_path=DB_PATH, lookback="3m", config=custom)
print("\nDetailed feature space classes:")
print(detailed["classification_df"]["asset_class"].value_counts().to_string())
