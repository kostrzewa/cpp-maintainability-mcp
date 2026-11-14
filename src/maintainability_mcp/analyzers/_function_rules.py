"""Shared function-level rules for the heuristic and lizard analyzers."""

from __future__ import annotations

from ..models import Finding, make_finding


def function_findings(
    *,
    path: str,
    name: str,
    start_line: int,
    end_line: int,
    length: int,
    params: int,
    complexity: int,
    nesting: int,
    analyzer: str,
) -> list[Finding]:
    findings: list[Finding] = []

    if complexity > 15:
        findings.append(
            make_finding(
                file=path,
                rule="high-cyclomatic-complexity",
                dimension="complexity",
                severity="error" if complexity > 25 else "warning",
                message=f"Function '{name}' has cyclomatic complexity {complexity}.",
                start_line=start_line,
                end_line=end_line,
                evidence={"function": name, "complexity": complexity},
                suggested_fix=(
                    "Extract branches into named helpers or replace conditional "
                    "logic with a table/polymorphism."
                ),
                impact={"defects": 0.8, "time": 0.7, "predictability": 0.6},
                effort="M",
                confidence=0.85,
                analyzer=analyzer,
            )
        )
    if length > 80:
        findings.append(
            make_finding(
                file=path,
                rule="long-function",
                dimension="size",
                severity="error" if length > 150 else "warning",
                message=f"Function '{name}' is {length} lines long.",
                start_line=start_line,
                end_line=end_line,
                evidence={"function": name, "lines": length},
                suggested_fix=(
                    "Extract cohesive steps into helper functions and keep the "
                    "top-level function as orchestration."
                ),
                impact={"defects": 0.5, "time": 0.7, "predictability": 0.5},
                effort="M",
                confidence=0.9,
                analyzer=analyzer,
            )
        )
    if params > 6:
        findings.append(
            make_finding(
                file=path,
                rule="too-many-parameters",
                dimension="parameters",
                severity="error" if params > 10 else "warning",
                message=f"Function '{name}' has {params} parameters.",
                start_line=start_line,
                end_line=end_line,
                evidence={"function": name, "parameters": params},
                suggested_fix=(
                    "Introduce a parameter object or split the function by "
                    "responsibility."
                ),
                impact={"defects": 0.4, "time": 0.5, "predictability": 0.4},
                effort="S",
                confidence=0.9,
                analyzer=analyzer,
            )
        )
    if nesting > 4:
        findings.append(
            make_finding(
                file=path,
                rule="deep-nesting",
                dimension="nesting",
                severity="error" if nesting > 6 else "warning",
                message=f"Function '{name}' nests {nesting} blocks deep.",
                start_line=start_line,
                end_line=end_line,
                evidence={"function": name, "nesting": nesting},
                suggested_fix=(
                    "Use guard clauses and early returns to flatten the control "
                    "flow."
                ),
                impact={"defects": 0.5, "time": 0.6, "predictability": 0.5},
                effort="S",
                confidence=0.85,
                analyzer=analyzer,
            )
        )
    if length > 100 and complexity > 20:
        findings.append(
            make_finding(
                file=path,
                rule="god-function",
                dimension="god_class",
                severity="warning",
                message=(
                    f"Function '{name}' combines {length} lines with complexity "
                    f"{complexity}."
                ),
                start_line=start_line,
                end_line=end_line,
                evidence={
                    "function": name,
                    "lines": length,
                    "complexity": complexity,
                },
                suggested_fix=(
                    "Split the function by responsibility; consider a class or "
                    "strategy if it owns state."
                ),
                impact={"defects": 0.7, "time": 0.8, "predictability": 0.6},
                effort="L",
                confidence=0.8,
                analyzer=analyzer,
            )
        )
    return findings
