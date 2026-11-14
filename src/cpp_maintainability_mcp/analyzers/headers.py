"""Header hygiene checks."""

from __future__ import annotations

import re
from pathlib import Path

from ..models import AnalysisResult, make_finding
from ..paths import HEADER_EXTENSIONS
from .base import Analyzer

HEAVY_INCLUDES = {
    "algorithm",
    "fstream",
    "functional",
    "iostream",
    "map",
    "memory",
    "set",
    "sstream",
    "string",
    "unordered_map",
    "unordered_set",
    "vector",
}


class HeaderAnalyzer(Analyzer):
    name = "headers"

    def analyze(self, path: Path) -> AnalysisResult:
        if path.suffix.lower() not in HEADER_EXTENSIONS:
            return AnalysisResult()
        text = path.read_text(errors="replace")
        findings = []

        has_pragma = re.search(r"^\s*#pragma\s+once\b", text, re.MULTILINE)
        has_guard = re.search(
            r"^\s*#ifndef\s+(\w+)\s*\n\s*#define\s+\1\b", text, re.MULTILINE
        )
        if not has_pragma and not has_guard:
            findings.append(
                make_finding(
                    file=str(path),
                    rule="missing-include-guard",
                    dimension="header_hygiene",
                    severity="warning",
                    message="Header has no #pragma once or include guard.",
                    start_line=1,
                    suggested_fix="Add '#pragma once' or a conventional include guard.",
                    impact={"defects": 0.3, "time": 0.4, "predictability": 0.3},
                    effort="S",
                    confidence=0.95,
                    analyzer=self.name,
                )
            )

        for match in re.finditer(
            r"^\s*using\s+namespace\s+([\w:]+)\s*;", text, re.MULTILINE
        ):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                make_finding(
                    file=str(path),
                    rule="using-namespace-in-header",
                    dimension="header_hygiene",
                    severity="warning",
                    message=(
                        f"'using namespace {match.group(1)}' in a header leaks "
                        "names into every includer."
                    ),
                    start_line=line,
                    suggested_fix="Qualify names or move the using-directive into a .cpp file.",
                    impact={"defects": 0.3, "time": 0.4, "predictability": 0.3},
                    effort="S",
                    confidence=0.95,
                    analyzer=self.name,
                )
            )

        for match in re.finditer(
            r'^\s*#include\s*[<"]([^>"]+)[>"]', text, re.MULTILINE
        ):
            name = match.group(1)
            base = name.split("/")[-1].split(".")[0]
            if base not in HEAVY_INCLUDES:
                continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                make_finding(
                    file=str(path),
                    rule="heavy-include-in-header",
                    dimension="header_hygiene",
                    severity="info",
                    message=(
                        f"Heavy include <{name}> in a header increases "
                        "recompilation cost for every includer."
                    ),
                    start_line=line,
                    suggested_fix=(
                        "Forward-declare where possible or move the include "
                        "into the .cpp file."
                    ),
                    impact={"defects": 0.1, "time": 0.5, "predictability": 0.2},
                    effort="S",
                    confidence=0.7,
                    analyzer=self.name,
                )
            )

        return AnalysisResult(
            findings=findings, metrics={"header_hygiene": float(len(findings))}
        )
