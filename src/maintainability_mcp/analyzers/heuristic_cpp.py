"""Pure-Python C++ heuristics used when lizard/libclang are unavailable.

The parser is deliberately approximate: it finds function-like definitions,
matches braces, and computes size, parameter count, decision count, and nesting
depth. It is good enough to drive the score and to produce actionable findings;
it is not a C++ front end.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import AnalysisResult
from ._function_rules import function_findings
from .base import Analyzer

CONTROL_NAMES = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "sizeof",
    "decltype",
    "alignof",
    "static_assert",
    "do",
    "else",
}

FUNCTION_RE = re.compile(
    r"(?m)^[ \t]*(?:template\s*<[^>{}]*>\s*)?"
    r"(?:[\w:<>,*&\s~]*?)\s*"
    r"(~?\w+)\s*"
    r"\(([^;{}]*)\)\s*"
    r"(?:const\s*)?(?:noexcept(?:\s*\([^)]*\))?\s*)?"
    r"(?:override\s*)?(?:final\s*)?"
    r"(?:->\s*[^{;]+)?"
    r"\{"
)

DECISION_RE = re.compile(r"\b(if|for|while|case|catch)\b|&&|\|\||\?")


def strip_comments_and_strings(text: str) -> str:
    """Replace comments and string/char literals with spaces, keeping newlines."""
    out: list[str] = []
    i = 0
    state = "code"
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                state = "line_comment"
                out.append("  ")
                i += 2
                continue
            if char == "/" and nxt == "*":
                state = "block_comment"
                out.append("  ")
                i += 2
                continue
            if char == '"':
                state = "string"
                out.append(" ")
                i += 1
                continue
            if char == "'":
                state = "char"
                out.append(" ")
                i += 1
                continue
            out.append(char)
            i += 1
            continue
        if state == "line_comment":
            if char == "\n":
                state = "code"
                out.append("\n")
            else:
                out.append(" ")
            i += 1
            continue
        if state == "block_comment":
            if char == "*" and nxt == "/":
                state = "code"
                out.append("  ")
                i += 2
                continue
            out.append("\n" if char == "\n" else " ")
            i += 1
            continue
        if state in ("string", "char"):
            if char == "\\":
                out.append("  ")
                i += 2
                continue
            if (state == "string" and char == '"') or (
                state == "char" and char == "'"
            ):
                state = "code"
                out.append(" ")
                i += 1
                continue
            out.append("\n" if char == "\n" else " ")
            i += 1
            continue
    return "".join(out)


def matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def count_parameters(params: str) -> int:
    params = params.strip()
    if not params or params == "void":
        return 0
    depth = 0
    count = 1
    for char in params:
        if char in "<([{":
            depth += 1
        elif char in ">)]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            count += 1
    return count


def max_nesting_depth(body: str) -> int:
    depth = 0
    maximum = 0
    for char in body:
        if char == "{":
            depth += 1
            maximum = max(maximum, depth)
        elif char == "}":
            depth = max(0, depth - 1)
    return maximum


class HeuristicCppAnalyzer(Analyzer):
    name = "heuristic"

    def analyze(self, path: Path) -> AnalysisResult:
        text = path.read_text(errors="replace")
        clean = strip_comments_and_strings(text)
        findings = []
        max_complexity = 0
        max_length = 0
        max_params = 0
        max_nesting = 0

        for match in FUNCTION_RE.finditer(clean):
            name = match.group(1)
            if name in CONTROL_NAMES:
                continue
            open_pos = match.end() - 1
            close_pos = matching_brace(clean, open_pos)
            if close_pos < 0:
                continue
            start_line = clean.count("\n", 0, match.start()) + 1
            end_line = clean.count("\n", 0, close_pos) + 1
            length = end_line - start_line + 1
            params = count_parameters(match.group(2))
            body = clean[open_pos + 1 : close_pos]
            complexity = 1 + len(DECISION_RE.findall(body))
            nesting = max_nesting_depth(body)

            max_complexity = max(max_complexity, complexity)
            max_length = max(max_length, length)
            max_params = max(max_params, params)
            max_nesting = max(max_nesting, nesting)

            findings.extend(
                function_findings(
                    path=str(path),
                    name=name,
                    start_line=start_line,
                    end_line=end_line,
                    length=length,
                    params=params,
                    complexity=complexity,
                    nesting=nesting,
                    analyzer=self.name,
                )
            )

        nloc = sum(1 for line in clean.splitlines() if line.strip())
        metrics = {
            "complexity": float(max_complexity),
            "size": float(max_length),
            "parameters": float(max_params),
            "nesting": float(max_nesting),
            "nloc": float(nloc),
        }
        return AnalysisResult(findings=findings, metrics=metrics)
