"""Engine orchestration: resolve files, run analyzers, score, persist."""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any

from .analyzers import (
    CognitiveAnalyzer,
    DuplicationAnalyzer,
    HeaderAnalyzer,
    HeuristicCppAnalyzer,
    TestabilityAnalyzer,
)
from .analyzers.clang_tidy_analyzer import ClangTidyAnalyzer
from .analyzers.cppcheck_analyzer import CppcheckAnalyzer
from .analyzers.libclang_analyzer import LibclangAnalyzer
from .analyzers.lizard_analyzer import LizardAnalyzer
from .config import Config
from .feedback import FeedbackEngine
from .guide import GuideEngine
from .history import HistoryStore
from .models import DimensionScore, FileScore, Finding, ProjectScore
from .scoring import ScoringEngine
from .toolchain import (
    default_checks,
    resolve_clang_tidy,
    resolve_cppcheck,
    resolve_libclang,
    tool_environment,
)

ANALYZER_CLASSES = {
    "heuristic": HeuristicCppAnalyzer,
    "duplication": DuplicationAnalyzer,
    "headers": HeaderAnalyzer,
    "cognitive": CognitiveAnalyzer,
    "testability": TestabilityAnalyzer,
    "lizard": LizardAnalyzer,
    "cppcheck": CppcheckAnalyzer,
    "clang_tidy": ClangTidyAnalyzer,
    "libclang": LibclangAnalyzer,
}


def build_analyzers(config: Config) -> list:
    analyzers = []
    env = tool_environment(config)
    checks = default_checks(config)
    for name in config.enabled_analyzers:
        analyzer_class = ANALYZER_CLASSES.get(name)
        if analyzer_class is None:
            continue
        if name == "cppcheck":
            analyzers.append(
                analyzer_class(
                    resolve_cppcheck(config),
                    config.cxx_standard,
                    env,
                )
            )
        elif name == "clang_tidy":
            analyzers.append(
                analyzer_class(
                    resolve_clang_tidy(config),
                    config.build_dir,
                    config.cxx_standard,
                    checks,
                    env,
                )
            )
        elif name == "libclang":
            analyzers.append(
                analyzer_class(
                    resolve_libclang(config),
                    config.cxx_standard,
                )
            )
        else:
            analyzers.append(analyzer_class())
    return analyzers


def resolve_files(paths: list[str], config: Config) -> list[Path]:
    files: list[Path] = []
    for item in paths:
        path = Path(item)
        if path.is_file():
            if path.suffix.lower() in config.extensions:
                files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            if child.suffix.lower() not in config.extensions:
                continue
            if _ignored(child, config.ignore_patterns):
                continue
            try:
                if child.stat().st_size > config.max_file_bytes:
                    continue
            except OSError:
                continue
            files.append(child)
    return sorted(set(files))


def _ignored(path: Path, patterns: tuple[str, ...]) -> bool:
    parts = set(path.parts)
    for pattern in patterns:
        pattern = pattern.rstrip("/")
        if pattern in parts:
            return True
        if fnmatch.fnmatch(path.name, pattern):
            return True
    return False


def parse_diff(diff: str) -> dict[str, list[tuple[int, int]]]:
    files: dict[str, list[tuple[int, int]]] = {}
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            path = path.removeprefix("b/")
            if path == "/dev/null":
                current = None
                continue
            current = path
            files.setdefault(current, [])
        elif line.startswith("@@") and current:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or 1)
                files[current].append((start, start + count - 1))
    return files


def _matches_diff_file(path: Path, diff_map: dict[str, list[tuple[int, int]]]) -> bool:
    name = str(path)
    for candidate in diff_map:
        if name == candidate or name.endswith(candidate) or candidate.endswith(name):
            return True
    return False


def _in_diff(
    finding: Finding, diff_map: dict[str, list[tuple[int, int]]]
) -> bool:
    ranges = diff_map.get(finding.file)
    if ranges is None:
        for candidate, candidate_ranges in diff_map.items():
            if finding.file.endswith(candidate) or candidate.endswith(finding.file):
                ranges = candidate_ranges
                break
    if ranges is None:
        return False
    if not ranges:
        return True
    return any(start <= finding.start_line <= end for start, end in ranges)


def _project_from_dict(payload: dict[str, Any]) -> ProjectScore:
    files = [
        FileScore(
            file=item["file"],
            score=item["score"],
            band=item["band"],
            dimensions=[DimensionScore(**d) for d in item.get("dimensions", [])],
            findings=[Finding(**f) for f in item.get("findings", [])],
            metrics=item.get("metrics", {}),
        )
        for item in payload.get("files", [])
    ]
    findings = [Finding(**f) for f in payload.get("findings", [])]
    return ProjectScore(
        score=payload["score"],
        band=payload["band"],
        files=files,
        findings=findings,
        tools=payload.get("tools", {}),
    )


def _rationale(finding: Finding) -> str:
    return (
        f"{finding.rule} affects the {finding.dimension} dimension. "
        "The research corpus links this dimension to defect risk and change "
        f"cost; the finding is reported at {finding.file}:{finding.start_line}."
    )


class MaintainabilityEngine:
    def __init__(
        self,
        config: Config | None = None,
        history: HistoryStore | None = None,
    ):
        self.config = config or Config.load()
        self.config.validate()
        self.history = history or HistoryStore(self.config.history_path)
        self.analyzers = build_analyzers(self.config)
        self.scoring = ScoringEngine(self.config)
        self.feedback = FeedbackEngine(self.config)
        self.guide_engine = GuideEngine(self.config, self.history)
        self._last_findings: dict[str, Finding] = {}

    def scan(
        self,
        paths: list[str],
        diff: str | None = None,
        repo: str = ".",
    ) -> ProjectScore:
        files = resolve_files(paths, self.config)
        diff_map = parse_diff(diff) if diff else None
        if diff_map is not None:
            files = [file for file in files if _matches_diff_file(file, diff_map)]

        findings: list[Finding] = []
        metrics_by_file: dict[str, dict[str, float]] = {
            str(file): {} for file in files
        }
        tools: dict[str, str] = {}

        for analyzer in self.analyzers:
            if analyzer.name == "duplication":
                continue
            if not analyzer.available():
                tools[analyzer.name] = "unavailable"
                continue
            tools[analyzer.name] = "ok"
            for file in files:
                result = analyzer.analyze(file)
                findings.extend(result.findings)
                metrics_by_file[str(file)].update(result.metrics)

        duplication = next(
            (analyzer for analyzer in self.analyzers if analyzer.name == "duplication"),
            None,
        )
        if duplication is not None and duplication.available():
            duplication_results, duplication_findings = duplication.analyze_files(files)
            findings.extend(duplication_findings)
            for file, result in duplication_results.items():
                metrics_by_file.setdefault(file, {}).update(result.metrics)
            tools[duplication.name] = "ok"

        if diff_map is not None:
            findings = [finding for finding in findings if _in_diff(finding, diff_map)]

        unique: dict[str, Finding] = {}
        for finding in findings:
            unique.setdefault(finding.id, finding)
        findings = list(unique.values())

        file_scores = []
        for file in files:
            file_findings = [f for f in findings if f.file == str(file)]
            file_scores.append(
                self.scoring.score_file(
                    str(file),
                    metrics_by_file.get(str(file), {}),
                    file_findings,
                )
            )

        project = self.scoring.score_project(file_scores, findings, tools)
        self._last_findings = {finding.id: finding for finding in findings}
        self.history.record_scan(repo, project.score, project.band, project.to_dict())
        return project

    def score(
        self,
        paths: list[str],
        diff: str | None = None,
        repo: str = ".",
    ) -> ProjectScore:
        return self.scan(paths, diff, repo)

    def explain(self, finding_id: str) -> dict[str, Any]:
        finding = self._last_findings.get(finding_id)
        if finding is None:
            return {"error": f"unknown finding id: {finding_id}"}
        return {
            "finding": finding.to_dict(),
            "rationale": _rationale(finding),
            "suggested_fix": finding.suggested_fix,
        }

    def suggest(
        self,
        paths: list[str],
        budget: int = 5,
        diff: str | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        project = self.scan(paths, diff, repo)
        return {
            "score": project.score,
            "band": project.band,
            "suggestions": self.feedback.suggest(project.findings, budget),
        }

    def compare(
        self,
        before: str,
        after: str,
        threshold: float | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        before_score = self._load_or_scan(before, repo)
        after_score = self._load_or_scan(after, repo)
        return self.feedback.compare(before_score, after_score, threshold)

    def guide(
        self,
        paths: list[str],
        task: str = "",
        standards: list[str] | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        return self.guide_engine.guide(paths, task, standards, repo)

    def baseline(self, paths: list[str], repo: str = ".") -> dict[str, Any]:
        project = self.scan(paths, repo=repo)
        self.history.record_baseline(repo, project.score, project.to_dict())
        return {"repo": repo, "score": project.score, "band": project.band}

    def trend(self, repo: str = ".", limit: int = 20) -> dict[str, Any]:
        return {"repo": repo, "scans": self.history.recent_scans(repo, limit)}

    def close(self) -> None:
        self.history.close()

    def _load_or_scan(self, value: str, repo: str) -> ProjectScore:
        if value == "baseline":
            row = self.history.latest_baseline(repo)
            if row is None:
                raise ValueError("no baseline recorded for this repo")
            return _project_from_dict(json.loads(row["payload"]))
        path = Path(value)
        if path.exists():
            return self.scan([value], repo=repo)
        raise ValueError(f"cannot load revision: {value}")
