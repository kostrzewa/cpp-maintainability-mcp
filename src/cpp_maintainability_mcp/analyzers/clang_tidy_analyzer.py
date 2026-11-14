"""Optional clang-tidy adapter."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..models import AnalysisResult, make_finding
from .base import Analyzer

DIAGNOSTIC_RE = re.compile(
    r"^(.*?):(\d+):(\d+): (warning|error|note): (.*?) \[([^\]]+)\]$"
)


class ClangTidyAnalyzer(Analyzer):
    name = "clang_tidy"

    def __init__(
        self,
        executable: str | None = "clang-tidy",
        build_dir: str | None = None,
        cxx_standard: str = "c++20",
        checks: str | None = None,
        env: dict[str, str] | None = None,
    ):
        self.executable = executable
        self.build_dir = build_dir
        self.cxx_standard = cxx_standard
        self.checks = checks
        self.env = env

    def available(self) -> bool:
        return bool(self.executable) and shutil.which(self.executable) is not None

    def analyze(self, path: Path) -> AnalysisResult:
        if not self.executable:
            return AnalysisResult(status="unavailable")
        command = [self.executable]
        if self.build_dir:
            command += ["-p", self.build_dir]
        if self.checks:
            command += [f"-checks={self.checks}"]
        command += [str(path), "--", f"-std={self.cxx_standard}"]
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
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
                    impact={"defects": 0.4, "time": 0.3, "predictability": 0.3},
                    effort="S",
                    confidence=0.85,
                    analyzer=self.name,
                )
            )
        return AnalysisResult(
            findings=findings, metrics={"static_analysis": float(len(findings))}
        )

    @staticmethod
    def _dimension(check: str) -> str:
        if check.startswith("readability-"):
            return "cognitive_intent"
        if check.startswith(("cppcoreguidelines-", "cert-")):
            return "resource_safety"
        return "static_analysis"
