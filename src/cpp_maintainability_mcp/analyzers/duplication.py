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


def _merge_ranges(
    ranges: list[tuple[int, int, str]],
) -> list[tuple[int, int, set[str]]]:
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged: list[tuple[int, int, set[str]]] = []
    start, end, digest = ordered[0]
    hashes = {digest}
    for next_start, next_end, next_digest in ordered[1:]:
        if next_start <= end + 1:
            end = max(end, next_end)
            hashes.add(next_digest)
        else:
            merged.append((start, end, hashes))
            start, end, hashes = next_start, next_end, {next_digest}
    merged.append((start, end, hashes))
    return merged


def _other_location(
    file: str,
    start: int,
    end: int,
    hashes: set[str],
    windows: dict[str, list[tuple[str, int]]],
) -> tuple[str, int] | None:
    for digest in hashes:
        for other_file, other_start in windows[digest]:
            if other_file == file and start <= other_start <= end:
                continue
            return other_file, other_start
    return None


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

        ranges_by_file: dict[str, list[tuple[int, int, str]]] = {
            file: [] for file in normalized
        }
        duplicated: dict[str, set[int]] = {file: set() for file in normalized}
        for digest, occurrences in windows.items():
            if len(occurrences) < 2:
                continue
            for file, line in occurrences:
                ranges_by_file[file].append((line, line + WINDOW - 1, digest))
                for offset in range(WINDOW):
                    duplicated[file].add(line + offset)

        findings = []
        for file, ranges in ranges_by_file.items():
            for start, end, hashes in _merge_ranges(ranges):
                other = _other_location(file, start, end, hashes, windows)
                if other is None:
                    continue
                other_file, other_start = other
                findings.append(
                    make_finding(
                        file=file,
                        rule="duplicate-block",
                        dimension="duplication",
                        severity="warning",
                        message=(
                            f"Duplicated {end - start + 1}-line block also at "
                            f"{other_file}:{other_start}."
                        ),
                        start_line=start,
                        end_line=end,
                        evidence={
                            "other": f"{other_file}:{other_start}",
                            "lines": end - start + 1,
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
