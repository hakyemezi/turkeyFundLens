"""
Bilingual Markdown sections for the classification layer.

Follows the same shape as `engine.REPORT_LABELS`: a label table per language and
functions that return lists of Markdown lines, so sections can be appended to
the existing market narrative report or rendered standalone.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from besfundlens.core.utils import format_pct, normalize_language
from besfundlens.classification.pipeline import summarize_classification
from besfundlens.classification.taxonomy import translate_family

CLASSIFICATION_LABELS = {
    "en": {
        "report_title": "# besFundLens Allocation Classification Report",
        "asset_classes": "## Asset Allocation Classes",
        "risk_bands": "## Risk Bands",
        "currency_bands": "## Currency Exposure Bands",
        "participation": "## Participation vs Conventional",
        "drift_watchlist": "## Style Drift Watchlist",
        "model_quality": "## Classification Quality",
        "notes": "## Classification Notes",
        "asset_class": "Asset Class",
        "family": "Family",
        "risk_band": "Risk Band",
        "currency_band": "Currency Band",
        "participation_class": "Participation",
        "fund_count": "Fund Count",
        "aum_share": "AUM Share",
        "flow": "Flow",
        "market_effect": "Market Effect",
        "avg_confidence": "Avg Confidence",
        "avg_stability": "Avg Stability",
        "fund": "Fund",
        "style_drift": "Style Drift",
        "stability": "Stability",
        "confidence": "Confidence",
        "no_data": "No classification data available.",
        "model_type": "Model",
        "model_kmeans": "KMeans over window-averaged allocation vectors",
        "model_fallback": "Rule fallback (universe too small to cluster)",
        "class_count": "Class count (k)",
        "silhouette": "Silhouette score",
        "classified_funds": "Classified funds",
        "window": "Classification window",
        "low_confidence": "Low-confidence funds",
        "heavy_lookthrough": "Heavy look-through funds",
        "note_method": (
            "Classes are discovered by clustering window-averaged allocation vectors; "
            "class names are derived from each cluster centroid."
        ),
        "note_confidence": (
            "`Confidence` is the margin between the nearest and second-nearest class, "
            "discounted by the share of the portfolio held in other funds."
        ),
        "note_stability": (
            "`Stability` is the share of sub-windows in which the fund stayed in its own class."
        ),
        "note_drift": (
            "`Style Drift` is the allocation distance between the first and last sub-window, "
            "in percentage points."
        ),
        "note_disclaimer": (
            "Classification is descriptive analytics on published allocation data. "
            "It is not investment advice."
        ),
    },
    "tr": {
        "report_title": "# besFundLens Varlık Dağılımı Sınıflandırma Raporu",
        "asset_classes": "## Varlık Dağılımı Sınıfları",
        "risk_bands": "## Risk Bantları",
        "currency_bands": "## Kur Riski Bantları",
        "participation": "## Katılım / Konvansiyonel Dağılımı",
        "drift_watchlist": "## Stil Kayması İzleme Listesi",
        "model_quality": "## Sınıflandırma Kalitesi",
        "notes": "## Sınıflandırma Notları",
        "asset_class": "Varlık Sınıfı",
        "family": "Aile",
        "risk_band": "Risk Bandı",
        "currency_band": "Kur Bandı",
        "participation_class": "Katılım",
        "fund_count": "Fon Sayısı",
        "aum_share": "AUM Payı",
        "flow": "Akış",
        "market_effect": "Piyasa Etkisi",
        "avg_confidence": "Ort. Güven",
        "avg_stability": "Ort. Kararlılık",
        "fund": "Fon",
        "style_drift": "Stil Kayması",
        "stability": "Kararlılık",
        "confidence": "Güven",
        "no_data": "Sınıflandırma verisi bulunamadı.",
        "model_type": "Model",
        "model_kmeans": "Pencere-ortalamalı dağılım vektörleri üzerinde KMeans",
        "model_fallback": "Kural yedeği (evren kümeleme için çok küçük)",
        "class_count": "Sınıf sayısı (k)",
        "silhouette": "Silhouette skoru",
        "classified_funds": "Sınıflandırılan fon sayısı",
        "window": "Sınıflandırma penceresi",
        "low_confidence": "Düşük güvenli fon sayısı",
        "heavy_lookthrough": "Yoğun look-through fon sayısı",
        "note_method": (
            "Sınıflar, pencere-ortalamalı dağılım vektörlerinin kümelenmesiyle keşfedilir; "
            "sınıf adları her kümenin merkezinden türetilir."
        ),
        "note_confidence": (
            "`Güven`, en yakın ve ikinci en yakın sınıf arasındaki marjdır ve portföyün "
            "başka fonlarda tutulan payı oranında düşürülür."
        ),
        "note_stability": (
            "`Kararlılık`, fonun kendi sınıfında kaldığı alt pencerelerin oranıdır."
        ),
        "note_drift": (
            "`Stil Kayması`, ilk ve son alt pencere arasındaki dağılım mesafesidir (yüzde puan)."
        ),
        "note_disclaimer": (
            "Sınıflandırma, yayımlanan dağılım verisi üzerinde betimleyici bir analizdir. "
            "Yatırım tavsiyesi değildir."
        ),
    },
}


def classification_label(key: str, language: str = "en") -> str:
    """Look up a localised label, falling back to English."""
    language = normalize_language(language)
    return CLASSIFICATION_LABELS[language].get(key, CLASSIFICATION_LABELS["en"].get(key, key))


def _format_ratio(value) -> str:
    """Format a 0-1 score. `format_pct` is for decimal rates, this is for scores."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.2f}"


def _class_column(language: str) -> str:
    return "asset_class_tr" if normalize_language(language) == "tr" else "asset_class"


def _axis_column(base: str, language: str) -> str:
    return f"{base}_tr" if normalize_language(language) == "tr" else base


def build_asset_class_section(
    classification_df: pd.DataFrame,
    language: str = "en",
    top_n: int = 15,
) -> list:
    """Main table: one row per model-discovered class."""
    language = normalize_language(language)
    lines = [classification_label("asset_classes", language), ""]

    class_col = _class_column(language)
    summary = summarize_classification(classification_df, group_col=class_col)

    if summary.empty:
        lines.append(classification_label("no_data", language))
        lines.append("")
        return lines

    families = (
        classification_df.dropna(subset=[class_col])
        .groupby(class_col)["asset_class_family"]
        .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "")
    )

    has_aum = "start_aum_share" in summary.columns

    header = [
        classification_label("asset_class", language),
        classification_label("family", language),
        classification_label("fund_count", language),
    ]
    align = ["---", "---", "---:"]

    if has_aum:
        header += [
            classification_label("aum_share", language),
            classification_label("flow", language),
            classification_label("market_effect", language),
        ]
        align += ["---:", "---:", "---:"]

    header += [
        classification_label("avg_confidence", language),
        classification_label("avg_stability", language),
    ]
    align += ["---:", "---:"]

    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(align) + "|")

    for _, row in summary.head(top_n).iterrows():
        family = translate_family(families.get(row[class_col], ""), language)
        cells = [str(row[class_col]), family, f"{int(row['fund_count'])}"]

        if has_aum:
            cells += [
                format_pct(row["start_aum_share"]),
                format_pct(row["weighted_flow_pct"]),
                format_pct(row["weighted_market_effect_pct"]),
            ]

        cells += [
            _format_ratio(row["avg_confidence"]),
            _format_ratio(row["avg_stability"]),
        ]

        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    return lines


def build_axis_section(
    classification_df: pd.DataFrame,
    axis: str,
    title_key: str,
    language: str = "en",
) -> list:
    """Breakdown table for one of the secondary categorical axes."""
    language = normalize_language(language)
    lines = [classification_label(title_key, language), ""]

    column = _axis_column(axis, language)
    summary = summarize_classification(classification_df, group_col=column)

    if summary.empty:
        lines.append(classification_label("no_data", language))
        lines.append("")
        return lines

    has_aum = "start_aum_share" in summary.columns

    header = [classification_label(axis, language), classification_label("fund_count", language)]
    align = ["---", "---:"]

    if has_aum:
        header += [
            classification_label("aum_share", language),
            classification_label("flow", language),
            classification_label("market_effect", language),
        ]
        align += ["---:", "---:", "---:"]

    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(align) + "|")

    for _, row in summary.iterrows():
        cells = [str(row[column]), f"{int(row['fund_count'])}"]
        if has_aum:
            cells += [
                format_pct(row["start_aum_share"]),
                format_pct(row["weighted_flow_pct"]),
                format_pct(row["weighted_market_effect_pct"]),
            ]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    return lines


def build_drift_section(
    classification_df: pd.DataFrame,
    language: str = "en",
    top_n: int = 10,
) -> list:
    """Funds whose allocation moved most inside the window."""
    language = normalize_language(language)
    lines = [classification_label("drift_watchlist", language), ""]

    if "style_drift" not in classification_df.columns:
        lines.append(classification_label("no_data", language))
        lines.append("")
        return lines

    watchlist = (
        classification_df[classification_df["style_drift"].notna()]
        .sort_values("style_drift", ascending=False)
        .head(top_n)
    )

    if watchlist.empty:
        lines.append(classification_label("no_data", language))
        lines.append("")
        return lines

    class_col = _class_column(language)

    lines.append(
        f"| {classification_label('fund', language)} "
        f"| {classification_label('asset_class', language)} "
        f"| {classification_label('style_drift', language)} "
        f"| {classification_label('stability', language)} "
        f"| {classification_label('confidence', language)} |"
    )
    lines.append("|---|---|---:|---:|---:|")

    for _, row in watchlist.iterrows():
        lines.append(
            f"| {row['fonKodu']} "
            f"| {row[class_col] if pd.notna(row[class_col]) else '-'} "
            f"| {row['style_drift']:.1f} "
            f"| {_format_ratio(row.get('class_stability'))} "
            f"| {_format_ratio(row.get('class_confidence'))} |"
        )

    lines.append("")
    return lines


def build_model_quality_section(
    classification_df: pd.DataFrame,
    fit_info,
    language: str = "en",
    low_confidence_threshold: float = 0.25,
) -> list:
    """How much to trust the classes above."""
    language = normalize_language(language)
    lines = [classification_label("model_quality", language), ""]

    model_desc = classification_label(
        "model_kmeans" if getattr(fit_info, "model_fitted", False) else "model_fallback",
        language,
    )
    lines.append(f"- {classification_label('model_type', language)}: **{model_desc}**")
    lines.append(f"- {classification_label('class_count', language)}: **{getattr(fit_info, 'k', 'N/A')}**")

    silhouette = getattr(fit_info, "silhouette", None)
    if silhouette is not None:
        lines.append(
            f"- {classification_label('silhouette', language)}: **{silhouette:.3f}**"
        )

    classified = int(classification_df["asset_class"].notna().sum())
    lines.append(f"- {classification_label('classified_funds', language)}: **{classified}**")

    window_start = getattr(fit_info, "window_start", None)
    window_end = getattr(fit_info, "window_end", None)
    if window_start and window_end:
        lines.append(
            f"- {classification_label('window', language)}: **{window_start} - {window_end}**"
        )

    if "class_confidence" in classification_df.columns:
        low = int((classification_df["class_confidence"] < low_confidence_threshold).sum())
        lines.append(f"- {classification_label('low_confidence', language)}: **{low}**")

    if "lookthrough_band" in classification_df.columns:
        heavy = int(classification_df["lookthrough_band"].eq("Heavy Look-through").sum())
        lines.append(f"- {classification_label('heavy_lookthrough', language)}: **{heavy}**")

    lines.append("")
    return lines


def classification_note_lines(language: str = "en") -> list:
    """
    The interpretation notes as bare sentences, without bullets or a header.

    Exposed separately so the market narrative report can fold them into its own
    "Interpretation Notes" section instead of opening a second one.
    """
    language = normalize_language(language)
    return [
        classification_label(key, language)
        for key in (
            "note_method",
            "note_confidence",
            "note_stability",
            "note_drift",
            "note_disclaimer",
        )
    ]


def build_notes_section(language: str = "en") -> list:
    language = normalize_language(language)
    return [
        classification_label("notes", language),
        "",
        *(f"- {line}" for line in classification_note_lines(language)),
    ]


def build_classification_sections(
    classification_df: pd.DataFrame,
    fit_info=None,
    language: str = "en",
    top_n: int = 15,
    include_notes: bool = True,
) -> list:
    """All classification sections, as Markdown lines."""
    language = normalize_language(language)

    lines = []
    lines += build_asset_class_section(classification_df, language, top_n=top_n)
    lines += build_axis_section(classification_df, "risk_band", "risk_bands", language)
    lines += build_axis_section(classification_df, "currency_band", "currency_bands", language)
    lines += build_axis_section(classification_df, "participation_class", "participation", language)
    lines += build_drift_section(classification_df, language)

    if fit_info is not None:
        lines += build_model_quality_section(classification_df, fit_info, language)

    if include_notes:
        lines += build_notes_section(language)

    return lines


def classification_report_to_markdown(
    classification_df: pd.DataFrame,
    fit_info=None,
    language: str = "en",
    top_n: int = 15,
    title: Optional[str] = None,
) -> str:
    """Standalone classification report."""
    language = normalize_language(language)

    lines = [title or classification_label("report_title", language), ""]
    lines += build_classification_sections(
        classification_df,
        fit_info=fit_info,
        language=language,
        top_n=top_n,
    )

    return "\n".join(lines)
