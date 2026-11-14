"""Testability heuristics."""

from __future__ import annotations

import re
from pathlib import Path

from ..models import AnalysisResult, make_finding
from .base import Analyzer

GLOBAL_STATE_RE = re.compile(
    r"^\s*(?:static|extern)\s+(?!const\b)(?!constexpr\b)[\w:<>,*&\s]+\s+"
    r"(\w+)\s*(?:=|;)",
    re.MULTILINE,
)
SINGLETON_RE = re.compile(r"\bgetInstance\s*\(")
HARDCODED_IO_RE = re.compile(
    r"\b(std::cin|std::cout|std::cerr|fopen|freopen|getenv|rand|srand|time)\s*\("
)


class TestabilityAnalyzer(Analyzer):
    name = "testability"

    def analyze(self, path: Path) -> AnalysisResult:
        text = path.read_text(errors="replace")
        findings = []

        for match in GLOBAL_STATE_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                make_finding(
                    file=str(path),
                    rule="global-mutable-state",
                    dimension="testability",
                    severity="warning",
                    message=f"Mutable global/static state '{match.group(1)}'.",
                    start_line=line,
                    suggested_fix=(
                        "Inject the dependency or encapsulate the state behind "
                        "an interface."
                    ),
                    impact={"defects": 0.3, "time": 0.4, "predictability": 0.4},
                    effort="M",
                    confidence=0.7,
                    analyzer=self.name,
                )
            )

        for match in SINGLETON_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                make_finding(
                    file=str(path),
                    rule="singleton",
                    dimension="testability",
                    severity="info",
                    message="Singleton access makes dependencies implicit.",
                    start_line=line,
                    suggested_fix="Pass the instance explicitly or use dependency injection.",
                    impact={"defects": 0.2, "time": 0.3, "predictability": 0.3},
                    effort="M",
                    confidence=0.6,
                    analyzer=self.name,
                )
            )

        for match in HARDCODED_IO_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                make_finding(
                    file=str(path),
                    rule="hardcoded-io",
                    dimension="testability",
                    severity="info",
                    message=f"Direct use of '{match.group(1)}' couples the code to its environment.",
                    start_line=line,
                    suggested_fix="Inject an I/O, clock, or randomness abstraction.",
                    impact={"defects": 0.2, "time": 0.3, "predictability": 0.3},
                    effort="M",
                    confidence=0.6,
                    analyzer=self.name,
                )
            )

        return AnalysisResult(
            findings=findings, metrics={"testability": float(len(findings))}
        )
