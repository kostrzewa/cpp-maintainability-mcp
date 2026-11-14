"""Composite maintainability scoring."""

from __future__ import annotations

import statistics
from collections import Counter

from .config import Config
from .models import (
    GRADES,
    DimensionScore,
    FileScore,
    FileSummary,
    Finding,
    ProjectScore,
    band_for,
    grade_for,
)


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
            grade=grade_for(score),
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
            return ProjectScore(
                median=10.0,
                grade="excellent",
                distribution={grade: 0 for grade in GRADES},
                worst_files=[],
                best_files=[],
                files=[],
                findings=findings,
                tools=tools or {},
            )
        scores = [file.score for file in file_scores]
        median = round(statistics.median(scores), 2)
        distribution = {grade: 0 for grade in GRADES}
        for file in file_scores:
            distribution[file.grade] += 1
        worst = sorted(file_scores, key=lambda file: (file.score, file.file))[:5]
        best = sorted(file_scores, key=lambda file: (-file.score, file.file))[:5]
        return ProjectScore(
            median=median,
            grade=grade_for(median),
            distribution=distribution,
            worst_files=[_summary(file) for file in worst],
            best_files=[_summary(file) for file in best],
            files=file_scores,
            findings=findings,
            tools=tools or {},
        )


def _summary(file: FileScore) -> FileSummary:
    top_rules = [
        rule
        for rule, _ in Counter(finding.rule for finding in file.findings).most_common(3)
    ]
    return FileSummary(
        file=file.file,
        score=file.score,
        grade=file.grade,
        findings=len(file.findings),
        top_rules=top_rules,
    )
