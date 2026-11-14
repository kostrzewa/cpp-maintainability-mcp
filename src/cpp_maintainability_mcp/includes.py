"""Static include graph used to decide whether a header is covered by a TU."""

from __future__ import annotations

import re
from pathlib import Path

from .paths import (
    HEADER_EXTENSIONS,
    entry_file,
    include_paths_from_entry,
    load_compile_commands,
)

INCLUDE_RE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', re.MULTILINE)
SYSTEM_PREFIXES = ("/usr/", "/opt/", "/lib/", "/lib64/")


def parse_includes(path: Path) -> list[tuple[bool, str]]:
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    return [
        (match.group(1) == '"', match.group(2))
        for match in INCLUDE_RE.finditer(text)
    ]


def resolve_include(
    is_quoted: bool,
    include: str,
    including_file: Path,
    include_paths: list[Path],
) -> Path | None:
    candidates: list[Path] = []
    if is_quoted:
        candidates.append(including_file.parent / include)
    candidates.extend(base / include for base in include_paths)
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def _is_system(path: Path) -> bool:
    text = str(path)
    return any(text.startswith(prefix) for prefix in SYSTEM_PREFIXES)


def build_header_tu_map(compile_commands_path: Path) -> dict[Path, list[Path]]:
    mapping: dict[Path, list[Path]] = {}
    for entry in load_compile_commands(compile_commands_path):
        tu = entry_file(entry)
        if tu is None:
            continue
        tu = tu.resolve()
        include_paths = [Path(path) for path in include_paths_from_entry(entry)]
        visited: set[Path] = set()
        stack = [tu]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for is_quoted, include in parse_includes(current):
                resolved = resolve_include(
                    is_quoted, include, current, include_paths
                )
                if resolved is None or _is_system(resolved):
                    continue
                if resolved.suffix.lower() in HEADER_EXTENSIONS:
                    mapping.setdefault(resolved, [])
                    if tu not in mapping[resolved]:
                        mapping[resolved].append(tu)
                stack.append(resolved)
    return mapping


def choose_tu_per_header(
    header_map: dict[Path, list[Path]], headers: set[Path]
) -> dict[Path, Path]:
    return {
        header: min(header_map[header])
        for header in headers
        if header in header_map
    }
