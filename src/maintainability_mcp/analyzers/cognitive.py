"""Cognitive and intent-debt heuristics."""

from __future__ import annotations

import re
from pathlib import Path

from ..models import AnalysisResult, make_finding
from .base import Analyzer

MAGIC_NUMBER_RE = re.compile(r"(?<![\w.])(\d{2,})(?![\w.])")
MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
SKIP_LINE_RE = re.compile(r"#include|#define|for\s*\(|case\s|\[|\]")
ALLOWED_NUMBERS = {"10", "100", "1000", "1024"}
MAX_MAGIC_NUMBERS = 5


class CognitiveAnalyzer(Analyzer):
    name = "cognitive"

    def analyze(self, path: Path) -> AnalysisResult:
        text = path.read_text(errors="replace")
        lines = text.splitlines()
        nloc = sum(
            1 for line in lines if line.strip() and not line.strip().startswith("//")
        )
        comment_lines = sum(
            1
            for line in lines
            if line.strip().startswith("//") or line.strip().startswith("*")
        )
        density = comment_lines / max(1, nloc)
        findings = []

        if nloc > 50 and density < 0.05:
            findings.append(
                make_finding(
                    file=str(path),
                    rule="low-comment-density",
                    dimension="cognitive_intent",
                    severity="info",
                    message=(
                        f"Only {density:.1%} of non-blank lines are comments; "
                        "intent is hard to recover."
                    ),
                    start_line=1,
                    evidence={"comment_density": round(density, 4), "nloc": nloc},
                    suggested_fix=(
                        "Document non-obvious decisions and invariants; prefer "
                        "clear names over narration."
                    ),
                    impact={"defects": 0.2, "time": 0.4, "predictability": 0.3},
                    effort="S",
                    confidence=0.6,
                    analyzer=self.name,
                )
            )

        for match in MARKER_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                make_finding(
                    file=str(path),
                    rule="unresolved-marker",
                    dimension="cognitive_intent",
                    severity="info",
                    message=f"Unresolved {match.group(1)} marker.",
                    start_line=line,
                    suggested_fix="Resolve the marker or link it to a tracked issue.",
                    impact={"defects": 0.1, "time": 0.2, "predictability": 0.2},
                    effort="S",
                    confidence=0.9,
                    analyzer=self.name,
                )
            )

        magic_count = 0
        for match in MAGIC_NUMBER_RE.finditer(text):
            value = match.group(1)
            if value in ALLOWED_NUMBERS:
                continue
            line = text.count("\n", 0, match.start()) + 1
            line_text = lines[line - 1] if 0 <= line - 1 < len(lines) else ""
            if SKIP_LINE_RE.search(line_text):
                continue
            magic_count += 1
            if magic_count > MAX_MAGIC_NUMBERS:
                break
            findings.append(
                make_finding(
                    file=str(path),
                    rule="magic-number",
                    dimension="cognitive_intent",
                    severity="info",
                    message=f"Magic number {value}.",
                    start_line=line,
                    evidence={"value": value},
                    suggested_fix="Name the constant and explain its meaning.",
                    impact={"defects": 0.1, "time": 0.3, "predictability": 0.2},
                    effort="S",
                    confidence=0.5,
                    analyzer=self.name,
                )
            )

        return AnalysisResult(
            findings=findings,
            metrics={"cognitive_intent": float(len(findings))},
        )
