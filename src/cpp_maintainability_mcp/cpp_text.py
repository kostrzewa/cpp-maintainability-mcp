"""C++ text helpers shared by analyzers."""

from __future__ import annotations


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
