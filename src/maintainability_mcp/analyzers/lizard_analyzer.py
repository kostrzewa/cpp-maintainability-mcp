"""Optional lizard adapter for complexity and size metrics."""

from __future__ import annotations

from pathlib import Path

from ..models import AnalysisResult
from ._function_rules import function_findings
from .base import Analyzer


class LizardAnalyzer(Analyzer):
    name = "lizard"

    def available(self) -> bool:
        try:
            import lizard  # noqa: F401

            return True
        except ImportError:
            return False

    def analyze(self, path: Path) -> AnalysisResult:
        import lizard

        info = lizard.analyze_file(str(path))
        findings = []
        max_complexity = 0
        max_length = 0
        max_params = 0
        max_nesting = 0
        for function in info.function_list:
            nesting = int(getattr(function, "max_nesting_depth", 0) or 0)
            max_complexity = max(max_complexity, function.cyclomatic_complexity)
            max_length = max(max_length, function.nloc)
            max_params = max(max_params, function.parameter_count)
            max_nesting = max(max_nesting, nesting)
            findings.extend(
                function_findings(
                    path=str(path),
                    name=function.name,
                    start_line=function.start_line,
                    end_line=function.end_line,
                    length=function.nloc,
                    params=function.parameter_count,
                    complexity=function.cyclomatic_complexity,
                    nesting=nesting,
                    analyzer=self.name,
                )
            )
        metrics = {
            "complexity": float(max_complexity),
            "size": float(max_length),
            "parameters": float(max_params),
            "nesting": float(max_nesting),
            "nloc": float(info.nloc),
        }
        return AnalysisResult(findings=findings, metrics=metrics)
