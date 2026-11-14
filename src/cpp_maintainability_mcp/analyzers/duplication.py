"""Token-ish duplication detection using normalized line windows."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..cpp_text import strip_comments_and_strings
from ..models import AnalysisResult, make_finding
from .base import Analyzer

WINDOW = 6


def _normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


class DuplicationAnalyzer(Analyzer):
    name = "duplication"

    def analyze(self, path: Path) -> AnalysisResult:
        results, _ = self.analyze_files([path])
        return results.get(str(path), AnalysisResult())

    def analyze_files(
        self, paths: list[Path]
    ) -> tuple[dict[str, AnalysisResult], list]:
        windows: dict[str, list[tuple[str, int]]] = {}
        normalized: dict[str, list[str]] = {}
        for path in paths:
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            lines = strip_comments_and_strings(text).splitlines()
            norm = [_normalize(line) for line in lines]
            normalized[str(path)] = norm
            for i in range(len(norm) - WINDOW + 1):
                block = norm[i : i + WINDOW]
                if sum(1 for line in block if line) < WINDOW:
                    continue
                digest = hashlib.sha1("\n".join(block).encode("utf-8")).hexdigest()
                windows.setdefault(digest, []).append((str(path), i + 1))

        findings = []
        duplicated: dict[str, set[int]] = {file: set() for file in normalized}
        for occurrences in windows.values():
            if len(occurrences) < 2:
                continue
            first_file, first_line = occurrences[0]
            second_file, second_line = occurrences[1]
            if first_file == second_file and abs(second_line - first_line) < WINDOW:
                continue
            for file, line in occurrences:
                for offset in range(WINDOW):
                    duplicated[file].add(line + offset)
            findings.append(
                make_finding(
                    file=second_file,
                    rule="duplicate-block",
                    dimension="duplication",
                    severity="warning",
                    message=(
                        f"Duplicated {WINDOW}-line block also at "
                        f"{first_file}:{first_line}."
                    ),
                    start_line=second_line,
                    end_line=second_line + WINDOW - 1,
                    evidence={
                        "other": f"{first_file}:{first_line}",
                        "window": WINDOW,
                    },
                    suggested_fix=(
                        "Extract the duplicated block into a shared function, "
                        "template, or algorithm."
                    ),
                    impact={"defects": 0.4, "time": 0.6, "predictability": 0.4},
                    effort="M",
                    confidence=0.9,
                    analyzer=self.name,
                )
            )

        results: dict[str, AnalysisResult] = {}
        for file, norm in normalized.items():
            total = max(1, sum(1 for line in norm if line))
            ratio = len(duplicated[file]) / total
            results[file] = AnalysisResult(
                metrics={"duplication": min(1.0, ratio)}
            )
        return results, findings
