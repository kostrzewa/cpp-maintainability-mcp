"""Data models shared by analyzers, scoring, and the MCP server."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

SEVERITIES = ("info", "warning", "error")
BANDS = ("healthy", "warning", "alert")


def band_for(score: float) -> str:
    if score >= 8.0:
        return "healthy"
    if score >= 4.0:
        return "warning"
    return "alert"


def finding_id(file: str, rule: str, line: int, message: str) -> str:
    raw = f"{file}:{rule}:{line}:{message}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


@dataclass
class Finding:
    id: str
    file: str
    rule: str
    dimension: str
    severity: str
    message: str
    start_line: int = 1
    start_col: int = 1
    end_line: int | None = None
    end_col: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_fix: str | None = None
    impact: dict[str, float] = field(default_factory=dict)
    effort: str = "M"
    confidence: float = 0.8
    analyzer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_finding(
    *,
    file: str,
    rule: str,
    dimension: str,
    severity: str,
    message: str,
    start_line: int = 1,
    start_col: int = 1,
    end_line: int | None = None,
    end_col: int | None = None,
    evidence: dict[str, Any] | None = None,
    suggested_fix: str | None = None,
    impact: dict[str, float] | None = None,
    effort: str = "M",
    confidence: float = 0.8,
    analyzer: str = "",
) -> Finding:
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity: {severity}")
    return Finding(
        id=finding_id(file, rule, start_line, message),
        file=file,
        rule=rule,
        dimension=dimension,
        severity=severity,
        message=message,
        start_line=start_line,
        start_col=start_col,
        end_line=end_line,
        end_col=end_col,
        evidence=evidence or {},
        suggested_fix=suggested_fix,
        impact=impact or {},
        effort=effort,
        confidence=confidence,
        analyzer=analyzer,
    )


@dataclass
class AnalysisResult:
    findings: list[Finding] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    status: str = "ok"


@dataclass
class DimensionScore:
    name: str
    value: float
    penalty: float
    weight: float
    findings: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FileScore:
    file: str
    score: float
    band: str
    dimensions: list[DimensionScore]
    findings: list[Finding]
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "score": self.score,
            "band": self.band,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "findings": [f.to_dict() for f in self.findings],
            "metrics": self.metrics,
        }


@dataclass
class ProjectScore:
    score: float
    band: str
    files: list[FileScore]
    findings: list[Finding]
    tools: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "band": self.band,
            "files": [f.to_dict() for f in self.files],
            "findings": [f.to_dict() for f in self.findings],
            "tools": self.tools,
        }
