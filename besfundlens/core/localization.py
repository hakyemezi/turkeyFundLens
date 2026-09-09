"""
Interface and report wording, in English and Turkish.

Everything the engine puts in front of a reader is named here: the report
headings and column labels, and the translations for the labels it computes —
quadrant, archetype, flow regime, and the Fund DNA scope and currency bands.

Split out of ``besfundlens.core.engine``, which had grown to hold the analytics
and all of their wording in one file. Nothing here touches the analytics; it
needs only the language helpers and the classification group labels, and
``engine`` re-exports every name so existing imports keep working.
"""

from __future__ import annotations

from besfundlens.classification.taxonomy import GROUP_LABELS_TR
from besfundlens.core.utils import DEFAULT_LANGUAGE, normalize_language


REPORT_LABELS = {
    "en": {
        "market_report_title": "# besFundLens Market Narrative Report",
        "selected_report_title": "# Selected Funds Comparison Report",
        "executive_summary": "## Executive Summary",
        "main_narrative": "## Main Narrative",
        "largest_archetypes": "## Largest Archetypes by Starting AUM",
        "market_flow_quadrants": "## Market-Flow Quadrants",
        "strongest_inflow_archetypes": "## Strongest Inflow Archetypes",
        "most_negative_market_effect": "## Most Negative Market-Effect Archetypes",
        "dominant_regime_by_archetype": "## Dominant Market-Flow Regime by Archetype",
        "interpretation_notes": "## Interpretation Notes",
        "fund_comparison": "## Fund Comparison",
        "fund_universe_count": "Fund universe count",
        "total_start_aum": "Total start AUM",
        "total_end_aum": "Total end AUM",
        "total_aum_change": "Total AUM change",
        "total_net_flow": "Total net flow",
        "total_market_effect": "Total market effect",
        "of_starting_aum": "of starting AUM",
        "archetype": "Archetype",
        "aum_share": "AUM Share",
        "flow": "Flow",
        "weighted_flow": "Weighted Flow",
        "market_effect": "Market Effect",
        "aum_change": "AUM Change",
        "fund_count": "Fund Count",
        "quadrant": "Quadrant",
        "dominant_regime": "Dominant Regime",
        "aum_share_in_regime": "AUM Share in Regime",
        "strength": "Strength",
        "insight": "Insight",
        "fund": "Fund",
        "return": "Return",
        "participant_change": "Participant Change",
        "regime": "Regime",
        "no_selected_data": "No selected fund data available.",
        "note_flow": "`Flow` represents estimated investor net flow as a percentage of starting AUM.",
        "note_market_effect": "`Market Effect` represents the estimated AUM impact of fund return.",
        "note_aum_change": "`AUM Change` is approximately the sum of Flow and Market Effect.",
        "note_dominant_regime": "`Dominant Regime` shows the largest AUM-weighted market-flow quadrant within each archetype.",
        "note_strength": "`Strength` indicates whether the dominant regime is clearly concentrated or fragmented.",
        "note_lookthrough": "Look-through-heavy funds should be analyzed with additional underlying fund exposure data.",
    },
    "tr": {
        "market_report_title": "# besFundLens Piyasa Anlatı Raporu",
        "selected_report_title": "# Seçili Fon Karşılaştırma Raporu",
        "executive_summary": "## Yönetici Özeti",
        "main_narrative": "## Ana Anlatı",
        "largest_archetypes": "## Başlangıç AUM'a Göre En Büyük Fon Tipleri",
        "market_flow_quadrants": "## Piyasa-Akış Rejimleri",
        "strongest_inflow_archetypes": "## En Güçlü Net Giriş Alan Fon Tipleri",
        "most_negative_market_effect": "## En Negatif Piyasa Etkisine Sahip Fon Tipleri",
        "dominant_regime_by_archetype": "## Fon Tipine Göre Baskın Piyasa-Akış Rejimi",
        "interpretation_notes": "## Yorum Notları",
        "fund_comparison": "## Fon Karşılaştırması",
        "fund_universe_count": "Fon evrenindeki fon sayısı",
        "total_start_aum": "Toplam başlangıç AUM",
        "total_end_aum": "Toplam bitiş AUM",
        "total_aum_change": "Toplam AUM değişimi",
        "total_net_flow": "Toplam net akış",
        "total_market_effect": "Toplam piyasa etkisi",
        "of_starting_aum": "başlangıç AUM'a göre",
        "archetype": "Fon Tipi",
        "aum_share": "AUM Payı",
        "flow": "Akış",
        "weighted_flow": "Ağırlıklı Akış",
        "market_effect": "Piyasa Etkisi",
        "aum_change": "AUM Değişimi",
        "fund_count": "Fon Sayısı",
        "quadrant": "Rejim",
        "dominant_regime": "Baskın Rejim",
        "aum_share_in_regime": "Rejim İçindeki AUM Payı",
        "strength": "Yoğunlaşma",
        "insight": "Yorum",
        "fund": "Fon",
        "return": "Getiri",
        "participant_change": "Katılımcı Değişimi",
        "regime": "Rejim",
        "no_selected_data": "Seçili fon verisi bulunamadı.",
        "note_flow": "`Akış`, başlangıç AUM'a göre tahmini yatırımcı net akışını gösterir.",
        "note_market_effect": "`Piyasa Etkisi`, fon getirisinin tahmini AUM etkisini gösterir.",
        "note_aum_change": "`AUM Değişimi`, yaklaşık olarak Akış ve Piyasa Etkisi toplamıdır.",
        "note_dominant_regime": "`Baskın Rejim`, her fon tipi içinde AUM ağırlıklı en büyük piyasa-akış rejimini gösterir.",
        "note_strength": "`Yoğunlaşma`, baskın rejimin net şekilde yoğunlaşıp yoğunlaşmadığını veya parçalı olup olmadığını gösterir.",
        "note_lookthrough": "Look-through ağırlığı yüksek fonlar, alt fon kırılımlarıyla ayrıca analiz edilmelidir.",
    },
}

QUADRANT_TRANSLATIONS = {
    "en": {
        "Negative Market / Negative Flow": "Negative Market / Negative Flow",
        "Negative Market / Positive Flow": "Negative Market / Positive Flow",
        "Positive Market / Negative Flow": "Positive Market / Negative Flow",
        "Positive Market / Positive Flow": "Positive Market / Positive Flow",
        "Negative Market / Neutral Flow": "Negative Market / Neutral Flow",
        "Positive Market / Neutral Flow": "Positive Market / Neutral Flow",
        "Neutral Market / Positive Flow": "Neutral Market / Positive Flow",
        "Neutral Market / Negative Flow": "Neutral Market / Negative Flow",
        "Neutral Market / Neutral Flow": "Neutral Market / Neutral Flow",
    },
    "tr": {
        "Negative Market / Negative Flow": "Negatif Piyasa / Negatif Akış",
        "Negative Market / Positive Flow": "Negatif Piyasa / Pozitif Akış",
        "Positive Market / Negative Flow": "Pozitif Piyasa / Negatif Akış",
        "Positive Market / Positive Flow": "Pozitif Piyasa / Pozitif Akış",
        "Negative Market / Neutral Flow": "Negatif Piyasa / Nötr Akış",
        "Positive Market / Neutral Flow": "Pozitif Piyasa / Nötr Akış",
        "Neutral Market / Positive Flow": "Nötr Piyasa / Pozitif Akış",
        "Neutral Market / Negative Flow": "Nötr Piyasa / Negatif Akış",
        "Neutral Market / Neutral Flow": "Nötr Piyasa / Nötr Akış",
    },
}

DOMINANCE_TRANSLATIONS = {
    "en": {
        "High dominance": "High dominance",
        "Moderate dominance": "Moderate dominance",
        "Weak dominance": "Weak dominance",
        "Fragmented": "Fragmented",
        "Unknown": "Unknown",
    },
    "tr": {
        "High dominance": "Yüksek yoğunlaşma",
        "Moderate dominance": "Orta düzey yoğunlaşma",
        "Weak dominance": "Zayıf yoğunlaşma",
        "Fragmented": "Parçalı",
        "Unknown": "Bilinmiyor",
    },
}

QUADRANT_PATTERN_MESSAGES = {
    "en": {
        "Negative Market / Negative Flow": "market performance and investor flows are both under pressure",
        "Negative Market / Positive Flow": "investor flows are positive despite negative market performance",
        "Positive Market / Negative Flow": "market performance is positive, but investor flows are negative, possibly indicating profit-taking or rotation",
        "Positive Market / Positive Flow": "both market performance and investor flows are positive",
        "Negative Market / Neutral Flow": "market performance is negative while investor flow is broadly neutral",
        "Positive Market / Neutral Flow": "market performance is positive while investor flow is broadly neutral",
        "Neutral Market / Positive Flow": "investor flows are positive while market impact is broadly neutral",
        "Neutral Market / Negative Flow": "investor flows are negative while market impact is broadly neutral",
        "Neutral Market / Neutral Flow": "both market impact and investor flow are broadly neutral",
    },
    "tr": {
        "Negative Market / Negative Flow": "piyasa performansı ve yatırımcı akışları aynı anda baskı altında",
        "Negative Market / Positive Flow": "negatif piyasa performansına rağmen yatırımcı akışları pozitif",
        "Positive Market / Negative Flow": "piyasa performansı pozitif ancak yatırımcı akışları negatif; bu durum kâr realizasyonu veya rotasyon sinyali olabilir",
        "Positive Market / Positive Flow": "piyasa performansı ve yatırımcı akışları aynı anda pozitif",
        "Negative Market / Neutral Flow": "piyasa performansı negatifken yatırımcı akışı genel olarak nötr",
        "Positive Market / Neutral Flow": "piyasa performansı pozitifken yatırımcı akışı genel olarak nötr",
        "Neutral Market / Positive Flow": "piyasa etkisi genel olarak nötrken yatırımcı akışları pozitif",
        "Neutral Market / Negative Flow": "piyasa etkisi genel olarak nötrken yatırımcı akışları negatif",
        "Neutral Market / Neutral Flow": "piyasa etkisi ve yatırımcı akışı genel olarak nötr",
    },
}

# The named archetypes classify_fund_archetype can return. The
# "{group} Dominant Fund" family is not listed, translate_archetype builds it
# from GROUP_LABELS_TR so that it tracks the asset group map.
ARCHETYPE_TRANSLATIONS = {
    "tr": {
        "Money Market Fund": "Para Piyasası Fonu",
        "Domestic Equity Fund": "Yerli Hisse Senedi Fonu",
        "Foreign Equity Fund": "Yabancı Hisse Senedi Fonu",
        "Domestic Fixed-Income Fund": "Yerli Sabit Getirili Fon",
        "Foreign Fixed-Income Fund": "Yabancı Sabit Getirili Fon",
        "Fixed-Income Fund": "Sabit Getirili Fon",
        "FX / Eurobond Fixed-Income Fund": "Döviz / Eurobond Sabit Getirili Fon",
        "Domestic Fixed-Income Dominant Multi-Asset Fund": "Yerli Sabit Getirili Ağırlıklı Çok Varlıklı Fon",
        "Foreign Fixed-Income Dominant Multi-Asset Fund": "Yabancı Sabit Getirili Ağırlıklı Çok Varlıklı Fon",
        "Fixed-Income Dominant Multi-Asset Fund": "Sabit Getirili Ağırlıklı Çok Varlıklı Fon",
        "Multi-Asset / Mixed Allocation Fund": "Çok Varlıklı / Karma Dağılımlı Fon",
        "Gold / Precious Metals Fund": "Altın / Kıymetli Maden Fonu",
        "Fund Allocation Dominant Fund": "Fon Sepeti Ağırlıklı Fon",
        "Unknown Fund Type": "Bilinmeyen Fon Türü",
    }
}
ARCHETYPE_TRANSLATIONS["en"] = {key: key for key in ARCHETYPE_TRANSLATIONS["tr"]}

# classify_flow_regime_v2 composes its label from a magnitude and a participant
# clause. Turkish puts the participant clause first, so the phrases cannot be
# assembled in the same order; the whole set is generated from the same pieces
# the engine itself uses, which keeps the two in step if a magnitude is added.
FLOW_MAGNITUDE_TRANSLATIONS_TR = {
    "Neutral / negligible": "nötr / ihmal edilebilir",
    "Small": "küçük",
    "Moderate": "ılımlı",
    "Strong": "güçlü",
    "Unknown": "bilinmeyen",
}

# English clause -> Turkish phrase, with {magnitude} where the magnitude goes
FLOW_REGIME_CLAUSES_TR = {
    "net inflow with participant growth": "katılımcı artışıyla {magnitude} net giriş",
    "net inflow without participant growth": "katılımcı artışı olmadan {magnitude} net giriş",
    "net inflow with stable participant count": "katılımcı sayısı sabitken {magnitude} net giriş",
    "net outflow with participant decline": "katılımcı azalışıyla {magnitude} net çıkış",
    "net outflow despite participant growth": "katılımcı artışına rağmen {magnitude} net çıkış",
    "net outflow with stable participant count": "katılımcı sayısı sabitken {magnitude} net çıkış",
}

# The regimes that carry no magnitude
FLOW_REGIME_STANDALONE_TR = {
    "Neutral flow with participant growth": "Katılımcı artışıyla nötr akış",
    "Neutral flow with participant decline": "Katılımcı azalışıyla nötr akış",
    "Neutral flow regime": "Nötr akış rejimi",
    "Unknown flow regime": "Bilinmeyen akış rejimi",
}


def _build_flow_regime_translations() -> dict:
    turkish = dict(FLOW_REGIME_STANDALONE_TR)
    for magnitude, magnitude_tr in FLOW_MAGNITUDE_TRANSLATIONS_TR.items():
        for clause, clause_tr in FLOW_REGIME_CLAUSES_TR.items():
            phrase = clause_tr.format(magnitude=magnitude_tr)
            turkish[f"{magnitude} {clause}"] = phrase[0].upper() + phrase[1:]
    return {"en": {key: key for key in turkish}, "tr": turkish}


FLOW_REGIME_TRANSLATIONS = _build_flow_regime_translations()

# The Fund DNA scope and currency labels. Asset groups are not repeated here,
# translate_asset_group reads them from GROUP_LABELS_TR.
SCOPE_TRANSLATIONS = {
    "tr": {
        "Domestic": "Yurt içi",
        "Foreign / International": "Yurt dışı / Uluslararası",
        "Commodity / Global Pricing": "Emtia / Küresel Fiyatlama",
        "Operational / Cash-like": "Operasyonel / Nakit Benzeri",
        "Look-through Required": "Look-through Gerekli",
        "Other / Unknown": "Diğer / Bilinmeyen",
    }
}
SCOPE_TRANSLATIONS["en"] = {key: key for key in SCOPE_TRANSLATIONS["tr"]}

CURRENCY_TRANSLATIONS = {
    "tr": {
        "TRY": "TRY",
        "FX": "Döviz",
        "Gold": "Altın",
        "Operational / Collateral": "Operasyonel / Teminat",
        "Mixed / Unknown": "Karma / Bilinmeyen",
        "Look-through Required": "Look-through Gerekli",
        "Other / Unknown": "Diğer / Bilinmeyen",
    }
}
CURRENCY_TRANSLATIONS["en"] = {key: key for key in CURRENCY_TRANSLATIONS["tr"]}


def report_label(key: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Return a localized report label.
    """
    language = normalize_language(language)
    return REPORT_LABELS[language].get(key, REPORT_LABELS["en"].get(key, key))


def translate_quadrant_name(quadrant: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate market-flow quadrant labels for report output.
    """
    language = normalize_language(language)
    return QUADRANT_TRANSLATIONS[language].get(quadrant, quadrant)


def translate_dominance_strength(strength: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate dominance strength labels for report output.
    """
    language = normalize_language(language)
    return DOMINANCE_TRANSLATIONS[language].get(strength, strength)


def translate_archetype(archetype: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate a v1 archetype label.

    ``classify_fund_archetype`` returns either one of the named archetypes or,
    when a single asset group dominates, ``f"{group} Dominant Fund"`` built from
    the broad asset group map. The second family is translated from the group
    labels rather than being listed here, so a new asset group is covered the
    moment it is added to the map.
    """
    language = normalize_language(language)
    if language == "en" or not isinstance(archetype, str):
        return archetype

    if archetype in ARCHETYPE_TRANSLATIONS[language]:
        return ARCHETYPE_TRANSLATIONS[language][archetype]

    if archetype.endswith(" Dominant Fund"):
        group = archetype[: -len(" Dominant Fund")]
        translated = GROUP_LABELS_TR.get(group)
        if translated:
            return f"{translated} Ağırlıklı Fon"

    return archetype


def translate_flow_regime(regime: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate a flow regime label.
    """
    language = normalize_language(language)
    return FLOW_REGIME_TRANSLATIONS[language].get(regime, regime)


def translate_asset_group(group: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate a broad asset group name, as used by the Fund DNA columns.
    """
    if normalize_language(language) == "en":
        return group
    return GROUP_LABELS_TR.get(group, group)


def translate_market_scope(scope: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate a market scope label.
    """
    language = normalize_language(language)
    return SCOPE_TRANSLATIONS[language].get(scope, scope)


def translate_currency_exposure(currency: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate a currency exposure label. Currency codes are left as they are.
    """
    language = normalize_language(language)
    return CURRENCY_TRANSLATIONS[language].get(currency, currency)


def get_quadrant_pattern_message(quadrant: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Return a localized natural-language explanation for a market-flow quadrant.
    """
    language = normalize_language(language)
    fallback = QUADRANT_PATTERN_MESSAGES["en"].get(
        quadrant,
        "the market-flow profile is mixed or neutral",
    )
    return QUADRANT_PATTERN_MESSAGES[language].get(quadrant, fallback)
