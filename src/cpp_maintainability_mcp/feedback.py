"""Ranking, suggestions, and regression gates."""

from __future__ import annotations

from .config import Config
from .models import Finding, ProjectScore

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
        threshold: float | None = None,
    ) -> dict:
        threshold = (
            threshold if threshold is not None else self.config.gate_threshold
        )
        before_ids = {finding.id for finding in before.findings}
        after_ids = {finding.id for finding in after.findings}
        new = [finding for finding in after.findings if finding.id not in before_ids]
        resolved = [
            finding for finding in before.findings if finding.id not in after_ids
        ]
        new_errors = [finding for finding in new if finding.severity == "error"]
        alert_files = [file for file in after.files if file.band == "alert"]
        return {
            "before": {"score": before.score, "band": before.band},
            "after": {"score": after.score, "band": after.band},
            "delta": round(after.score - before.score, 2),
            "new": [finding.to_dict() for finding in new],
            "resolved": [finding.to_dict() for finding in resolved],
            "gate": {
                "threshold": threshold,
                "passed": (
                    after.score >= threshold
                    and not new_errors
                    and not alert_files
                ),
                "new_errors": len(new_errors),
                "alert_files": [file.file for file in alert_files],
            },
        }
