"""
The allocation classifier.

A KMeans model groups funds by their window-averaged allocation vector; `k` is
chosen by silhouette score unless the caller fixes it. Cluster names come from
`taxonomy`, which reads the centroid — the model decides the grouping, the
taxonomy only names it.

The fitted model serialises to JSON (centroids + labels + config + fit
metadata), not pickle. That keeps the artifact readable, diffable and safe to
load, and lets a later run *assign* funds to the existing classes instead of
refitting, so class names stay comparable across periods.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from besfundlens.classification.config import DEFAULT_CONFIG, ClassificationConfig
from besfundlens.classification.features import apply_transform
from besfundlens.classification.taxonomy import (
    assign_family,
    label_centroid,
    deduplicate_labels,
    describe_centroid,
)

ARTIFACT_VERSION = 1


class ScikitLearnUnavailable(ImportError):
    """Raised when clustering is requested but scikit-learn is not installed."""


def _require_sklearn():
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ScikitLearnUnavailable(
            "scikit-learn is required for allocation classification. "
            "Install it with: pip install 'scikit-learn>=1.3'"
        ) from exc
    return KMeans, silhouette_score


@dataclass
class FitInfo:
    """What the model learned, and from what."""

    model_fitted: bool = False
    k: Optional[int] = None
    silhouette: Optional[float] = None
    n_funds: int = 0
    candidate_scores: dict = field(default_factory=dict)
    fallback_reason: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "model_fitted": self.model_fitted,
            "k": self.k,
            "silhouette": self.silhouette,
            "n_funds": self.n_funds,
            "candidate_scores": self.candidate_scores,
            "fallback_reason": self.fallback_reason,
            "window_start": self.window_start,
            "window_end": self.window_end,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "FitInfo":
        return cls(**{k: v for k, v in (payload or {}).items() if k in cls.__annotations__})


class AllocationClassifier:
    """
    KMeans over allocation vectors, with taxonomy-derived class names.

    Typical use::

        model = AllocationClassifier(config)
        model.fit(features)
        assignments = model.predict(features)
        model.save("models/allocation_classifier.json")

    and later::

        model = AllocationClassifier.load("models/allocation_classifier.json")
        assignments = model.predict(new_features)   # same class names
    """

    def __init__(self, config: ClassificationConfig = DEFAULT_CONFIG):
        self.config = config
        self.feature_names: list = []
        self.centroids: Optional[np.ndarray] = None
        self.class_labels_en: list = []
        self.class_labels_tr: list = []
        self.class_families: list = []
        self.class_descriptions: list = []
        self.fit_info = FitInfo()

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def fit(self, features: pd.DataFrame) -> "AllocationClassifier":
        """Fit the model on a window-averaged allocation matrix."""
        self.feature_names = list(features.columns)
        matrix = apply_transform(features, self.config).to_numpy(dtype=float)

        n_funds = matrix.shape[0]
        self.fit_info = FitInfo(n_funds=n_funds)

        if n_funds < self.config.min_funds_for_model:
            # Too few funds for clusters to mean anything. Every fund becomes
            # its own centroid and the taxonomy names it directly, which is
            # exactly the behaviour a small or synthetic dataset needs.
            self._fit_fallback(
                features,
                reason=(
                    f"only {n_funds} classifiable funds, "
                    f"below min_funds_for_model={self.config.min_funds_for_model}"
                ),
            )
            return self

        KMeans, silhouette_score = _require_sklearn()

        k_values = self._candidate_k_values(n_funds)
        if not k_values:
            self._fit_fallback(features, reason=f"no valid k for {n_funds} funds")
            return self

        best_k = None
        best_score = -np.inf
        best_model = None
        scores = {}

        for k in k_values:
            model = KMeans(
                n_clusters=k,
                random_state=self.config.random_state,
                n_init=self.config.n_init,
            )
            labels = model.fit_predict(matrix)

            if len(set(labels)) < 2:
                continue

            score = float(silhouette_score(matrix, labels))
            scores[k] = score

            if score > best_score:
                best_k, best_score, best_model = k, score, model

        if best_model is None:
            self._fit_fallback(features, reason="clustering produced a single group")
            return self

        self.centroids = best_model.cluster_centers_
        self._name_classes()

        self.fit_info.model_fitted = True
        self.fit_info.k = int(best_k)
        self.fit_info.silhouette = best_score
        self.fit_info.candidate_scores = {str(k): round(v, 6) for k, v in scores.items()}

        return self

    def _candidate_k_values(self, n_funds: int) -> list:
        if self.config.k is not None:
            return [self.config.k] if self.config.k < n_funds else []

        k_min, k_max = self.config.k_range
        return [k for k in range(k_min, k_max + 1) if k < n_funds]

    def _fit_fallback(self, features: pd.DataFrame, reason: str) -> None:
        """
        Purely rule-based classification, used when clustering is not viable.

        Each fund is named from its own allocation vector, then funds sharing a
        name are collapsed into one class whose centroid is their mean. Naming
        first and grouping second is what keeps a small universe from producing
        one near-duplicate class per fund.
        """
        transformed = apply_transform(features, self.config)

        per_fund_labels = [
            label_centroid(row, list(features.columns), self.config, "en")
            for row in transformed.to_numpy(dtype=float)
        ]

        grouped = transformed.groupby(pd.Index(per_fund_labels, name="label")).mean()

        self.centroids = grouped.to_numpy(dtype=float)
        self._name_classes()

        self.fit_info.model_fitted = False
        self.fit_info.k = int(self.centroids.shape[0])
        self.fit_info.silhouette = None
        self.fit_info.fallback_reason = reason

    def _name_classes(self) -> None:
        """Derive EN/TR names, families and descriptions from the centroids."""
        raw_en = [
            label_centroid(c, self.feature_names, self.config, "en")
            for c in self.centroids
        ]
        raw_tr = [
            label_centroid(c, self.feature_names, self.config, "tr")
            for c in self.centroids
        ]

        self.class_labels_en = deduplicate_labels(raw_en, self.centroids, self.feature_names)
        self.class_labels_tr = deduplicate_labels(raw_tr, self.centroids, self.feature_names)
        self.class_families = [
            assign_family(c, self.feature_names, self.config) for c in self.centroids
        ]
        self.class_descriptions = [
            describe_centroid(c, self.feature_names) for c in self.centroids
        ]

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Assign funds to the fitted classes.

        Returns a DataFrame indexed like `features` with the class id, EN/TR
        names, family, confidence and runner-up class.
        """
        if self.centroids is None:
            raise RuntimeError("AllocationClassifier is not fitted. Call fit() or load() first.")

        aligned = features.reindex(columns=self.feature_names).fillna(0.0)
        matrix = apply_transform(aligned, self.config).to_numpy(dtype=float)

        distances = self._distances(matrix)
        order = np.argsort(distances, axis=1)

        nearest = order[:, 0]
        runner_up = order[:, 1] if distances.shape[1] > 1 else nearest

        d1 = distances[np.arange(len(nearest)), nearest]
        d2 = distances[np.arange(len(runner_up)), runner_up]

        confidence = self._confidence(d1, d2, distances.shape[1])

        return pd.DataFrame(
            {
                "class_id": nearest,
                "asset_class": [self.class_labels_en[i] for i in nearest],
                "asset_class_tr": [self.class_labels_tr[i] for i in nearest],
                "asset_class_family": [self.class_families[i] for i in nearest],
                "class_description": [self.class_descriptions[i] for i in nearest],
                "class_confidence": confidence,
                "runner_up_class": [self.class_labels_en[i] for i in runner_up],
                "distance_to_centroid": d1,
            },
            index=features.index,
        )

    def _distances(self, matrix: np.ndarray) -> np.ndarray:
        """Euclidean distance from every fund to every centroid."""
        diff = matrix[:, None, :] - self.centroids[None, :, :]
        return np.sqrt((diff ** 2).sum(axis=2))

    @staticmethod
    def _confidence(d1: np.ndarray, d2: np.ndarray, n_classes: int) -> np.ndarray:
        """
        Margin between the nearest and second-nearest class, in [0, 1].

        1.0 means the fund sits on its centroid; 0.0 means it is equidistant
        between two classes and the assignment is a coin flip.
        """
        if n_classes < 2:
            return np.ones_like(d1)

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(d2 > 0, d1 / d2, 0.0)

        return np.clip(1.0 - ratio, 0.0, 1.0)

    def apply_lookthrough_penalty(
        self,
        confidence: pd.Series,
        lookthrough_weight: pd.Series,
    ) -> pd.Series:
        """
        Discount confidence by look-through weight.

        A fund holding 40% of other funds may sit neatly on a centroid, but we
        do not know what those funds hold. The allocation label is only as
        trustworthy as the share of the portfolio we can actually see.
        """
        if not self.config.lookthrough_penalty:
            return confidence

        visible = (100.0 - lookthrough_weight.clip(lower=0.0, upper=100.0)) / 100.0
        return (confidence * visible).clip(lower=0.0, upper=1.0)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        if self.centroids is None:
            raise RuntimeError("Cannot serialise an unfitted AllocationClassifier.")

        return {
            "artifact_version": ARTIFACT_VERSION,
            "config": self.config.to_dict(),
            "feature_names": self.feature_names,
            "centroids": np.asarray(self.centroids).tolist(),
            "class_labels_en": self.class_labels_en,
            "class_labels_tr": self.class_labels_tr,
            "class_families": self.class_families,
            "class_descriptions": self.class_descriptions,
            "fit_info": self.fit_info.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "AllocationClassifier":
        version = payload.get("artifact_version")
        if version != ARTIFACT_VERSION:
            raise ValueError(
                f"Unsupported model artifact version: {version}. Expected {ARTIFACT_VERSION}. "
                "Re-fit the model with the current besFundLens version."
            )

        model = cls(ClassificationConfig.from_dict(payload.get("config", {})))
        model.feature_names = list(payload["feature_names"])
        model.centroids = np.asarray(payload["centroids"], dtype=float)
        model.class_labels_en = list(payload["class_labels_en"])
        model.class_labels_tr = list(payload["class_labels_tr"])
        model.class_families = list(payload["class_families"])
        model.class_descriptions = list(payload.get("class_descriptions", []))
        model.fit_info = FitInfo.from_dict(payload.get("fit_info", {}))

        if not model.class_descriptions:
            model.class_descriptions = [
                describe_centroid(c, model.feature_names) for c in model.centroids
            ]

        return model

    def save(self, path: str | Path) -> str:
        """Write the model artifact as JSON and return the path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    @classmethod
    def load(cls, path: str | Path) -> "AllocationClassifier":
        """Load a model artifact written by `save()`."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    def centroid_table(self, language: str = "en") -> pd.DataFrame:
        """Cluster centroids as a readable table, for inspection and docs."""
        if self.centroids is None:
            raise RuntimeError("AllocationClassifier is not fitted.")

        labels = self.class_labels_tr if language == "tr" else self.class_labels_en
        table = pd.DataFrame(self.centroids, columns=self.feature_names)
        table.insert(0, "asset_class", labels)
        table.insert(1, "family", self.class_families)
        return table
