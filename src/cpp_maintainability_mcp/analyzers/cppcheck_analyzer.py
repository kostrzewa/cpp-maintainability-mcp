"""Optional cppcheck adapter (SARIF output)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..models import AnalysisResult, make_finding
from ..paths import is_header
from .base import Analyzer

INFORMATIONAL_CHECKS = {"normalCheckLevelMaxBranches", "checkersReport"}


class CppcheckAnalyzer(Analyzer):
    name = "cppcheck"

    def __init__(
        self,
        executable: str | None = "cppcheck",
        cxx_standard: str = "c++20",
        env: dict[str, str] | None = None,
        compile_commands: Path | None = None,
        include_paths: list[str] | None = None,
    ):
        self.executable = executable
        self.cxx_standard = cxx_standard
        self.env = env
        self.compile_commands = compile_commands
        self.include_paths = include_paths or []

    def available(self) -> bool:
        return bool(self.executable) and shutil.which(self.executable) is not None

    def analyze(self, path: Path) -> AnalysisResult:
        if self.compile_commands:
            return self.analyze_project([path])
        return self.analyze_direct(path)

    def analyze_project(self, files: list[Path]) -> AnalysisResult:
        command = [
            self.executable,
            f"--project={self.compile_commands}",
            "--enable=warning,style,performance,portability",
            "--output-format=sarif",
            "--quiet",
        ]
        return self._run(command, files)

    def analyze_direct(self, path: Path) -> AnalysisResult:
        command = [
            self.executable,
            "--enable=warning,style,performance,portability",
            "--output-format=sarif",
            f"--std={self.cxx_standard}",
            "--quiet",
        ]
        if is_header(path):
            command.append("--language=c++")
        command += [f"-I{include}" for include in self.include_paths]
        command.append(str(path))
        return self._run(command, [path])

    def _run(self, command: list[str], files: list[Path]) -> AnalysisResult:
        if not self.executable:
            return AnalysisResult(status="unavailable")
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=self.env,
            )
        except (OSError, subprocess.TimeoutExpired):
            return AnalysisResult(status="error")

        items = self._parse_sarif(proc.stderr) or self._parse_sarif(proc.stdout)
        items = self._filter(items, files)
        findings = []
        for item in items:
            severity = item.get("severity", "warning")
            if severity not in ("error", "warning"):
                continue
            check = item.get("id", "cppcheck")
            if check in INFORMATIONAL_CHECKS:
                continue
            dimension = (
                "resource_safety"
                if any(key in check for key in ("mem", "resource", "leak"))
                else "static_analysis"
            )
            file = (item.get("file") or "").removeprefix("file://")
            findings.append(
                make_finding(
                    file=file,
                    rule=f"cppcheck:{check}",
                    dimension=dimension,
                    severity=severity,
                    message=item.get("message", "cppcheck finding"),
                    start_line=int(item.get("line", 1) or 1),
                    start_col=int(item.get("column", 1) or 1),
                    end_line=item.get("endLine"),
                    end_col=item.get("endColumn"),
                    evidence={"id": check, "severity": severity},
                    suggested_fix=(
                        "Address the reported issue; see the cppcheck "
                        "documentation for this check."
                    ),
                    impact={"defects": 0.4, "time": 0.3, "predictability": 0.3},
                    effort="S",
                    confidence=0.8,
                    analyzer=self.name,
                )
            )
        return AnalysisResult(findings=findings)

    @staticmethod
    def _filter(items: list[dict], files: list[Path]) -> list[dict]:
        wanted = {str(path.resolve()) for path in files}
        result = []
        seen_unused_members: set[tuple[str, str]] = set()
        for item in items:
            file = (item.get("file") or "").removeprefix("file://")
            if wanted and str(Path(file).resolve()) not in wanted:
                continue
            if item.get("id") == "unusedStructMember":
                key = (file, "unusedStructMember")
                if key in seen_unused_members:
                    continue
                seen_unused_members.add(key)
            result.append(item)
        return result

    @staticmethod
    def _parse_sarif(output: str) -> list[dict]:
        start = output.find("{")
        if start < 0:
            return []
        try:
            data = json.loads(output[start:])
        except json.JSONDecodeError:
            return []
        items = []
        for run in data.get("runs", []):
            for result in run.get("results", []):
                locations = result.get("locations") or []
                physical = (
                    (locations[0].get("physicalLocation") if locations else {})
                    or {}
                )
                artifact = physical.get("artifactLocation") or {}
                region = physical.get("region") or {}
                items.append(
                    {
                        "file": artifact.get("uri"),
                        "line": region.get("startLine", 1),
                        "column": region.get("startColumn", 1),
                        "endLine": region.get("endLine"),
                        "endColumn": region.get("endColumn"),
                        "severity": result.get("level", "warning"),
                        "message": (result.get("message") or {}).get("text", ""),
                        "id": result.get("ruleId", "cppcheck"),
                    }
                )
        return items
