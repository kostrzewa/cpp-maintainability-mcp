"""Engine orchestration: resolve files, run analyzers, score, persist."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import time
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
from .models import (
    DimensionScore,
    FileScore,
    FileSummary,
    Finding,
    ProjectScore,
    grade_for,
)
from .paths import (
    compile_flags_for_file,
    find_compile_commands,
    load_compile_commands,
    resolve_defines,
    resolve_include_paths,
)
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


def cppcheck_jobs(config: Config) -> int:
    if config.cppcheck_jobs > 0:
        return config.cppcheck_jobs
    return max(1, (os.cpu_count() or 1) // 4)


def scan_mode(config: Config, paths: list[str], diff: str | None) -> str:
    if config.scan_mode in ("fast", "direct"):
        return config.scan_mode
    if diff:
        return "direct"
    if all(Path(path).is_file() for path in paths):
        return "direct"
    return "fast"


def build_analyzers(
    config: Config,
    include_paths: list[str] | None = None,
    defines: list[str] | None = None,
) -> list:
    analyzers = []
    env = tool_environment(config)
    checks = default_checks(config)
    include_paths = include_paths or []
    defines = defines or []
    jobs = cppcheck_jobs(config)
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
                    include_paths,
                    defines,
                    timeout=config.cppcheck_timeout,
                    jobs=jobs,
                )
            )
        elif name == "clang_tidy":
            analyzers.append(
                analyzer_class(
                    resolve_clang_tidy(config),
                    config.cxx_standard,
                    checks,
                    env,
                    include_paths,
                    defines,
                    timeout=config.clang_tidy_timeout,
                )
            )
        elif name == "libclang":
            analyzers.append(
                analyzer_class(
                    resolve_libclang(config),
                    config.cxx_standard,
                    include_paths,
                    defines,
                )
            )
        else:
            analyzers.append(analyzer_class())
    if any(analyzer.name == "lizard" and analyzer.available() for analyzer in analyzers):
        analyzers = [analyzer for analyzer in analyzers if analyzer.name != "heuristic"]
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
    for part in path.parts:
        for pattern in patterns:
            if fnmatch.fnmatch(part, pattern.rstrip("/")):
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


def _in_scan_scope(file: str, roots: list[str]) -> bool:
    try:
        path = Path(file).resolve()
    except OSError:
        return False
    for root in roots:
        try:
            base = Path(root).resolve()
        except OSError:
            continue
        if base.is_file():
            if path == base:
                return True
        elif path == base or path.is_relative_to(base):
            return True
    return False


def _finding_priority(finding: Finding) -> tuple[int, float]:
    severity = {"error": 2, "warning": 1, "info": 0}.get(finding.severity, 0)
    return (severity, finding.confidence)


def _dedupe_key(finding: Finding) -> tuple[str, int, str, str]:
    try:
        resolved = str(Path(finding.file).resolve())
    except OSError:
        resolved = finding.file
    rule = "magic-number" if "magic-number" in finding.rule else finding.rule
    return (resolved, finding.start_line, finding.dimension, rule)


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    by_key: dict[tuple[str, int, str, str], Finding] = {}
    for finding in findings:
        key = _dedupe_key(finding)
        current = by_key.get(key)
        if current is None or _finding_priority(finding) > _finding_priority(current):
            by_key[key] = finding
    return list(by_key.values())


def _project_from_dict(payload: dict[str, Any]) -> ProjectScore:
    files = [
        FileScore(
            file=item["file"],
            score=item["score"],
            band=item["band"],
            grade=item.get("grade", grade_for(item["score"])),
            dimensions=[DimensionScore(**d) for d in item.get("dimensions", [])],
            findings=[Finding(**f) for f in item.get("findings", [])],
            metrics=item.get("metrics", {}),
        )
        for item in payload.get("files", [])
    ]
    findings = [Finding(**f) for f in payload.get("findings", [])]
    return ProjectScore(
        median=payload["median"],
        grade=payload["grade"],
        distribution=payload.get("distribution", {}),
        worst_files=[FileSummary(**s) for s in payload.get("worst_files", [])],
        best_files=[FileSummary(**s) for s in payload.get("best_files", [])],
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
        self.analyzers: list = []
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
        deadline = time.monotonic() + self.config.scan_timeout
        files = resolve_files(paths, self.config)
        diff_map = parse_diff(diff) if diff else None
        if diff_map is not None:
            files = [file for file in files if _matches_diff_file(file, diff_map)]

        compile_commands_path = find_compile_commands(self.config, paths)
        entries = None
        if compile_commands_path is not None:
            try:
                entries = load_compile_commands(compile_commands_path)
            except (OSError, TypeError, ValueError):
                compile_commands_path = None
        include_paths = resolve_include_paths(self.config, compile_commands_path)
        defines = resolve_defines(self.config, compile_commands_path)
        mode = scan_mode(self.config, paths, diff)
        self.analyzers = build_analyzers(self.config, include_paths, defines)

        findings: list[Finding] = []
        metrics_by_file: dict[str, dict[str, float]] = {
            str(file.resolve()): {} for file in files
        }
        tools: dict[str, str] = {}
        fast_names = {"heuristic", "lizard", "headers", "cognitive", "testability"}

        for analyzer in self.analyzers:
            if analyzer.name == "duplication":
                continue
            if (
                mode == "fast"
                and analyzer.name not in fast_names
                and analyzer.name != "cppcheck"
            ):
                tools[analyzer.name] = "skipped"
                continue
            if time.monotonic() >= deadline:
                tools[analyzer.name] = "timeout"
                continue
            if not analyzer.available():
                tools[analyzer.name] = "unavailable"
                continue
            tools[analyzer.name] = "ok"
            remaining = max(1.0, deadline - time.monotonic())
            if hasattr(analyzer, "timeout"):
                analyzer.timeout = min(analyzer.timeout, remaining)
            if mode == "fast" and analyzer.name == "cppcheck":
                if compile_commands_path is None:
                    tools[analyzer.name] = "skipped"
                    continue
                findings.extend(
                    analyzer.analyze_project(compile_commands_path, files).findings
                )
                continue
            if mode == "direct":
                for file in files:
                    flags = compile_flags_for_file(self.config, entries, file)
                    if hasattr(analyzer, "include_paths"):
                        analyzer.include_paths = flags.include_paths
                    if hasattr(analyzer, "defines"):
                        analyzer.defines = flags.defines
                    if hasattr(analyzer, "cxx_standard"):
                        analyzer.cxx_standard = flags.standard
                    result = analyzer.analyze(file)
                    findings.extend(result.findings)
                    metrics_by_file[str(file.resolve())].update(result.metrics)
            else:
                for file in files:
                    result = analyzer.analyze(file)
                    findings.extend(result.findings)
                    metrics_by_file[str(file.resolve())].update(result.metrics)

        duplication = next(
            (analyzer for analyzer in self.analyzers if analyzer.name == "duplication"),
            None,
        )
        if duplication is not None and duplication.available():
            duplication_results, duplication_findings = duplication.analyze_files(files)
            findings.extend(duplication_findings)
            for file, result in duplication_results.items():
                metrics_by_file.setdefault(
                    str(Path(file).resolve()), {}
                ).update(result.metrics)
            tools[duplication.name] = "ok"

        if diff_map is not None:
            findings = [finding for finding in findings if _in_diff(finding, diff_map)]
        findings = [
            finding for finding in findings if _in_scan_scope(finding.file, paths)
        ]
        findings = _dedupe_findings(findings)

        file_by_resolved: dict[Path, Path] = {file.resolve(): file for file in files}
        findings_by_resolved: dict[Path, list[Finding]] = {}
        for finding in findings:
            path = Path(finding.file)
            try:
                resolved = path.resolve()
            except OSError:
                continue
            findings_by_resolved.setdefault(resolved, []).append(finding)
            file_by_resolved.setdefault(resolved, path)

        file_scores = []
        for resolved, display in sorted(file_by_resolved.items()):
            file_scores.append(
                self.scoring.score_file(
                    str(display),
                    metrics_by_file.get(str(resolved), {}),
                    findings_by_resolved.get(resolved, []),
                )
            )

        project = self.scoring.score_project(file_scores, findings, tools)
        self._last_findings = {finding.id: finding for finding in findings}
        self.history.record_scan(
            repo, project.median, project.grade, project.to_dict()
        )
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
            "median": project.median,
            "grade": project.grade,
            "suggestions": self.feedback.suggest(project.findings, budget),
        }

    def compare(
        self,
        before: str,
        after: str,
        tolerance: float | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        before_score = self._load_or_scan(before, repo)
        after_score = self._load_or_scan(after, repo)
        return self.feedback.compare(before_score, after_score, tolerance)

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
        self.history.record_baseline(repo, project.median, project.to_dict())
        return {"repo": repo, "median": project.median, "grade": project.grade}

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
