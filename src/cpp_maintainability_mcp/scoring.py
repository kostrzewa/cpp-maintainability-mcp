"""Composite maintainability scoring."""

from __future__ import annotations

from .config import Config
from .models import DimensionScore, FileScore, Finding, ProjectScore, band_for


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class ScoringEngine:
    def __init__(self, config: Config):
        self.config = config

    def score_file(
        self, file: str, metrics: dict[str, float], findings: list[Finding]
    ) -> FileScore:
        dimensions: list[DimensionScore] = []
        weighted_penalty = 0.0
        for name, weight in self.config.weights.items():
            good, bad = self.config.thresholds[name]
            value = metrics.get(name)
            if value is None:
                count = sum(1 for f in findings if f.dimension == name)
                value = float(count)
            penalty = _clamp((value - good) / (bad - good))
            dimensions.append(
                DimensionScore(
                    name=name,
                    value=round(value, 4),
                    penalty=round(penalty, 4),
                    weight=weight,
                    findings=sum(1 for f in findings if f.dimension == name),
                )
            )
            weighted_penalty += weight * penalty
        score = round(_clamp(10.0 - 9.0 * weighted_penalty, 1.0, 10.0), 2)
        return FileScore(
            file=file,
            score=score,
            band=band_for(score),
            dimensions=dimensions,
            findings=findings,
            metrics=metrics,
        )

    def score_project(
        self,
        file_scores: list[FileScore],
        findings: list[Finding],
        tools: dict[str, str] | None = None,
    ) -> ProjectScore:
        if not file_scores:
            return ProjectScore(10.0, "healthy", [], findings, tools or {})
        weights = [max(1.0, fs.metrics.get("nloc", 1.0)) for fs in file_scores]
        total_weight = sum(weights)
        score = sum(w * fs.score for w, fs in zip(weights, file_scores)) / total_weight
        score = round(score, 2)
        return ProjectScore(
            score=score,
            band=band_for(score),
            files=file_scores,
            findings=findings,
            tools=tools or {},
        )
