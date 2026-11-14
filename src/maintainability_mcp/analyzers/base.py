"""Analyzer interface."""

from __future__ import annotations

from pathlib import Path

from ..models import AnalysisResult


class Analyzer:
    name = "base"

    def available(self) -> bool:
        return True

    def analyze(self, path: Path) -> AnalysisResult:
        raise NotImplementedError
