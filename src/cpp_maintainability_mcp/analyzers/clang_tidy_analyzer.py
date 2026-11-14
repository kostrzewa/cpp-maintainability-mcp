"""Optional clang-tidy adapter."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..models import AnalysisResult, make_finding
from ..paths import is_header
from .base import Analyzer

DIAGNOSTIC_RE = re.compile(
    r"^(.*?):(\d+):(\d+): (warning|error|note): (.*?) \[([^\]]+)\]$"
)

LOW_PRIORITY_CHECKS = {
    "bugprone-easily-swappable-parameters": (
        {"defects": 0.1, "time": 0.1, "predictability": 0.1},
        "M",
    ),
    "cppcoreguidelines-avoid-magic-numbers": (
        {"defects": 0.1, "time": 0.1, "predictability": 0.1},
        "S",
    ),
    "readability-magic-numbers": (
        {"defects": 0.1, "time": 0.1, "predictability": 0.1},
        "S",
    ),
}


class ClangTidyAnalyzer(Analyzer):
    name = "clang_tidy"

    def __init__(
        self,
        executable: str | None = "clang-tidy",
        cxx_standard: str = "c++20",
        checks: str | None = None,
        env: dict[str, str] | None = None,
        include_paths: list[str] | None = None,
        defines: list[str] | None = None,
        timeout: float = 120.0,
    ):
        self.executable = executable
        self.cxx_standard = cxx_standard
        self.checks = checks
        self.env = env
        self.include_paths = include_paths or []
        self.defines = defines or []
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.executable) and shutil.which(self.executable) is not None

    def analyze(self, path: Path) -> AnalysisResult:
        if not self.executable:
            return AnalysisResult(status="unavailable")
        command = [self.executable]
        if self.checks:
            command += [f"-checks={self.checks}"]
        if is_header(path):
            command += [f"-header-filter={re.escape(str(path))}"]
        command += [str(path), "--"]
        if is_header(path):
            command += ["-x", "c++-header"]
        command += [f"-std={self.cxx_standard}"]
        command += [f"-I{include}" for include in self.include_paths]
        command += self.defines
        return self._run(command)

    def _run(self, command: list[str]) -> AnalysisResult:
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env=self.env,
            )
        except (OSError, subprocess.TimeoutExpired):
            return AnalysisResult(status="error")

        findings = []
        for line in (proc.stdout + "\n" + proc.stderr).splitlines():
            match = DIAGNOSTIC_RE.match(line)
            if not match:
                continue
            file, line_no, column, severity, message, check = match.groups()
            if severity == "note":
                continue
            impact, effort = self._priority(check)
            findings.append(
                make_finding(
                    file=file,
                    rule=f"clang-tidy:{check}",
                    dimension=self._dimension(check),
                    severity="error" if severity == "error" else "warning",
                    message=message,
                    start_line=int(line_no),
                    start_col=int(column),
                    evidence={"check": check},
                    suggested_fix=(
                        "Apply the clang-tidy fix or refactor the affected code."
                    ),
                    impact=impact,
                    effort=effort,
                    confidence=0.85,
                    analyzer=self.name,
                )
            )
        return AnalysisResult(findings=findings)

    @staticmethod
    def _dimension(check: str) -> str:
        if "magic-number" in check:
            return "cognitive_intent"
        if check.startswith("readability-"):
            return "cognitive_intent"
        if check.startswith(("cppcoreguidelines-", "cert-")):
            return "resource_safety"
        return "static_analysis"

    @staticmethod
    def _priority(check: str) -> tuple[dict[str, float], str]:
        for name, (impact, effort) in LOW_PRIORITY_CHECKS.items():
            if name in check:
                return impact, effort
        return {"defects": 0.4, "time": 0.3, "predictability": 0.3}, "S"
