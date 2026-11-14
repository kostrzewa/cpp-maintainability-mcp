"""Ranking, suggestions, and regression gates."""

from __future__ import annotations

from .config import Config
from .models import GRADES, Finding, ProjectScore

EFFORT_WEIGHT = {"S": 1.0, "M": 2.0, "L": 3.0}


class FeedbackEngine:
    def __init__(self, config: Config):
        self.config = config

    def rank(self, findings: list[Finding], budget: int = 5) -> list[Finding]:
        def priority(finding: Finding) -> float:
            impact = sum(finding.impact.values()) if finding.impact else 0.5
            effort = EFFORT_WEIGHT.get(finding.effort, 2.0)
            return impact * finding.confidence / effort

        return sorted(findings, key=priority, reverse=True)[:budget]

    def suggest(self, findings: list[Finding], budget: int = 5) -> list[dict]:
        return [
            {
                "id": finding.id,
                "file": finding.file,
                "line": finding.start_line,
                "rule": finding.rule,
                "dimension": finding.dimension,
                "message": finding.message,
                "suggested_fix": finding.suggested_fix,
                "effort": finding.effort,
                "confidence": finding.confidence,
            }
            for finding in self.rank(findings, budget)
        ]

    def compare(
        self,
        before: ProjectScore,
        after: ProjectScore,
        tolerance: float | None = None,
    ) -> dict:
        tolerance = (
            tolerance
            if tolerance is not None
            else self.config.regression_tolerance
        )
        before_by_file = {file.file: file for file in before.files}
        before_ids = {finding.id for finding in before.findings}
        after_ids = {finding.id for finding in after.findings}
        new = [finding for finding in after.findings if finding.id not in before_ids]
        resolved = [
            finding for finding in before.findings if finding.id not in after_ids
        ]
        new_errors = [finding for finding in new if finding.severity == "error"]
        new_bad = [
            file
            for file in after.files
            if file.grade == "bad"
            and (
                file.file not in before_by_file
                or before_by_file[file.file].grade != "bad"
            )
        ]
        regressions = [
            file
            for file in after.files
            if file.file in before_by_file
            and file.score < before_by_file[file.file].score - tolerance
        ]
        distribution_delta = {
            grade: after.distribution.get(grade, 0)
            - before.distribution.get(grade, 0)
            for grade in GRADES
        }
        passed = (
            not new_bad
            and not regressions
            and not new_errors
            and distribution_delta["bad"] <= 0
            and distribution_delta["poor"] <= 0
        )
        return {
            "before": {
                "median": before.median,
                "grade": before.grade,
                "distribution": before.distribution,
            },
            "after": {
                "median": after.median,
                "grade": after.grade,
                "distribution": after.distribution,
            },
            "median_delta": round(after.median - before.median, 2),
            "distribution_delta": distribution_delta,
            "new_bad_files": [file.to_dict() for file in new_bad],
            "regressions": [file.to_dict() for file in regressions],
            "new": [finding.to_dict() for finding in new],
            "resolved": [finding.to_dict() for finding in resolved],
            "gate": {
                "tolerance": tolerance,
                "passed": passed,
                "new_errors": len(new_errors),
                "new_bad_files": len(new_bad),
                "regressions": len(regressions),
            },
        }
