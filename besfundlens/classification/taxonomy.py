"""
Naming layer for model-discovered classes.

The clustering model decides *which funds belong together*. This module decides
*what to call the resulting group*, by reading the cluster centroid and applying
a deterministic rule:

    top weight >= dominant_threshold  ->  "Precious Metals Weighted"
    top weight >= primary_threshold   ->  "Equity Tilted Multi-Asset"
    otherwise                         ->  "Multi-Asset (Fixed Income / Equity)"

Because the name is a pure function of the centroid, a class keeps its name as
long as its composition is stable — which is what makes period-over-period
comparison possible.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from besfundlens.core.asset_metadata import build_asset_metadata
from besfundlens.core.utils import normalize_language
from besfundlens.classification.config import DEFAULT_CONFIG, ClassificationConfig

# Broad asset group -> Turkish label.
GROUP_LABELS_TR = {
    "Equity": "Hisse Senedi",
    "Foreign Equity": "Yabancı Hisse Senedi",
    "Fixed Income": "Sabit Getirili",
    "Lease Certificates": "Kira Sertifikası",
    "Money Market": "Para Piyasası",
    "Money Market / Collateral": "Para Piyasası / Teminat",
    "Deposit": "Mevduat",
    "Participation Account": "Katılma Hesabı",
    "Precious Metals": "Kıymetli Maden",
    "Fund": "Yatırım Fonu",
    "ETF": "Borsa Yatırım Fonu",
    "Foreign ETF": "Yabancı Borsa Yatırım Fonu",
    "Real Estate / Alternative": "Gayrimenkul / Alternatif",
    "Venture Capital / Alternative": "Girişim Sermayesi / Alternatif",
    "Foreign Securities": "Yabancı Menkul Kıymet",
    "Derivatives": "Türev Araçlar",
    "Other": "Diğer",
}

# Level-1 family. Deliberately coarse: this is the axis a reader scans first.
FAMILY_BY_GROUP = {
    "Equity": "Equity",
    "Foreign Equity": "Equity",
    "Fixed Income": "Fixed Income",
    "Lease Certificates": "Fixed Income",
    "Money Market": "Money Market",
    "Money Market / Collateral": "Money Market",
    "Deposit": "Money Market",
    "Participation Account": "Money Market",
    "Precious Metals": "Precious Metals",
    "Fund": "Fund of Funds",
    "ETF": "Fund of Funds",
    "Foreign ETF": "Fund of Funds",
    "Real Estate / Alternative": "Alternative",
    "Venture Capital / Alternative": "Alternative",
    "Foreign Securities": "Alternative",
    "Derivatives": "Alternative",
    "Other": "Other",
}

def _extend_family_map() -> dict:
    """
    Widen the family map to the `detailed` and `raw` feature spaces.

    `FAMILY_BY_GROUP` above is written against the broad groups. The detailed
    space uses `asset_group` ("Government Fixed Income", "Eurobond", ...) and the
    raw space uses instrument names, so without this every class in those spaces
    would fall through to "Other". Each finer label inherits the family of the
    broad group its instruments belong to.
    """
    mapping = dict(FAMILY_BY_GROUP)
    meta = build_asset_metadata()

    for _, row in meta.iterrows():
        family = FAMILY_BY_GROUP.get(row["broad_asset_group"], "Other")
        for label in (row["asset_group"], row["asset_name_en_clean"]):
            if isinstance(label, str):
                mapping.setdefault(label, family)

    return mapping


# Broad labels keep their explicit family; finer labels inherit from their broad group.
GROUP_FAMILY_MAP = _extend_family_map()

FAMILY_LABELS_TR = {
    "Equity": "Hisse",
    "Fixed Income": "Sabit Getirili",
    "Money Market": "Para Piyasası",
    "Precious Metals": "Kıymetli Maden",
    "Fund of Funds": "Fon Sepeti",
    "Alternative": "Alternatif",
    "Multi-Asset": "Çoklu Varlık",
    "Other": "Diğer",
}

NAME_TEMPLATES = {
    "en": {
        "dominant": "{top} Weighted",
        "tilted": "{top} Tilted Multi-Asset",
        "mixed": "Multi-Asset ({top} / {second})",
        "empty": "Unclassified",
    },
    "tr": {
        "dominant": "{top} Ağırlıklı",
        "tilted": "{top} Eğilimli Çoklu Varlık",
        "mixed": "Çoklu Varlık ({top} / {second})",
        "empty": "Sınıflandırılamadı",
    },
}


def translate_group(group: str, language: str = "en") -> str:
    """Localise a feature-space group label."""
    if normalize_language(language) == "tr":
        return GROUP_LABELS_TR.get(group, group)
    return group


def translate_family(family: str, language: str = "en") -> str:
    """Localise a level-1 family label."""
    if normalize_language(language) == "tr":
        return FAMILY_LABELS_TR.get(family, family)
    return family


def _ranked_groups(centroid: Sequence[float], feature_names: Sequence[str]) -> list:
    """
    Feature labels ordered by descending centroid weight.

    Sorting the negated weights with a stable kind (rather than reversing an
    ascending sort) means exact ties fall back to feature order, so a name never
    depends on argsort's reversal semantics.
    """
    values = np.asarray(centroid, dtype=float)
    order = np.argsort(-values, kind="stable")
    return [(feature_names[i], float(values[i])) for i in order]


def label_centroid(
    centroid: Sequence[float],
    feature_names: Sequence[str],
    config: ClassificationConfig = DEFAULT_CONFIG,
    language: str = "en",
) -> str:
    """Deterministic, human-readable name for a cluster centroid."""
    language = normalize_language(language)
    templates = NAME_TEMPLATES[language]

    ranked = _ranked_groups(centroid, feature_names)
    ranked = [(name, weight) for name, weight in ranked if weight > 0]

    if not ranked:
        return templates["empty"]

    top_name, top_weight = ranked[0]
    top_label = translate_group(top_name, language)

    if top_weight >= config.dominant_threshold:
        return templates["dominant"].format(top=top_label)

    if top_weight >= config.primary_threshold:
        return templates["tilted"].format(top=top_label)

    second_label = translate_group(ranked[1][0], language) if len(ranked) > 1 else top_label
    return templates["mixed"].format(top=top_label, second=second_label)


def assign_family(
    centroid: Sequence[float],
    feature_names: Sequence[str],
    config: ClassificationConfig = DEFAULT_CONFIG,
) -> str:
    """Level-1 family for a centroid, always in English (translate on display)."""
    ranked = [(name, weight) for name, weight in _ranked_groups(centroid, feature_names) if weight > 0]

    if not ranked:
        return "Other"

    top_name, top_weight = ranked[0]

    if top_weight < config.primary_threshold:
        return "Multi-Asset"

    return GROUP_FAMILY_MAP.get(top_name, "Other")


def deduplicate_labels(
    labels: Sequence[str],
    centroids: Sequence[Sequence[float]],
    feature_names: Sequence[str],
) -> list:
    """
    Make class names unique.

    Two clusters can legitimately reduce to the same name (for example two
    "Fixed Income Weighted" groups that differ in their second holding). A
    report with duplicate row labels is unreadable, so collisions are broken by
    appending the discriminating second group, and by an index as a last resort.
    """
    counts = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1

    resolved = []
    used = set()

    for label, centroid in zip(labels, centroids):
        if counts[label] == 1:
            resolved.append(label)
            used.add(label)
            continue

        ranked = [(name, w) for name, w in _ranked_groups(centroid, feature_names) if w > 0]
        candidate = label

        for name, _ in ranked[1:3]:
            candidate = f"{label} / {name}"
            if candidate not in used:
                break

        suffix = 2
        while candidate in used:
            candidate = f"{label} #{suffix}"
            suffix += 1

        resolved.append(candidate)
        used.add(candidate)

    return resolved


def describe_centroid(
    centroid: Sequence[float],
    feature_names: Sequence[str],
    top_n: int = 3,
) -> str:
    """Short "Fixed Income 62.1%, Equity 21.4%" style composition summary."""
    ranked = [(name, w) for name, w in _ranked_groups(centroid, feature_names) if w >= 0.5]
    return ", ".join(f"{name} {weight:.1f}%" for name, weight in ranked[:top_n])
