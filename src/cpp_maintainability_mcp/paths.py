"""Filesystem, compile-command, and compile-flag helpers."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path

from .config import Config

HEADER_EXTENSIONS = {".h", ".hpp", ".hxx", ".hh"}
SOURCE_EXTENSIONS = {".cpp", ".cc", ".cxx", ".c++"}


def is_header(path: str | Path) -> bool:
    return Path(path).suffix.lower() in HEADER_EXTENSIONS


def is_source(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SOURCE_EXTENSIONS


def find_compile_commands(config: Config, roots: list[str]) -> Path | None:
    if config.compile_commands:
        path = Path(config.compile_commands)
        if path.is_dir():
            path = path / "compile_commands.json"
        if path.is_file():
            return path.resolve()
    if config.build_dir:
        path = Path(config.build_dir) / "compile_commands.json"
        if path.is_file():
            return path.resolve()
    for root in roots:
        base = Path(root)
        base = base if base.is_dir() else base.parent
        for parent in (base, *base.parents):
            candidate = parent / "compile_commands.json"
            if candidate.is_file():
                return candidate.resolve()
    return None


def load_compile_commands(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TypeError(f"{path} is not a compile_commands.json array")
    return data


def entry_arguments(entry: dict) -> list[str]:
    if "arguments" in entry:
        return [str(arg) for arg in entry["arguments"]]
    command = entry.get("command")
    return shlex.split(command) if command else []


def entry_directory(entry: dict) -> Path:
    return Path(entry.get("directory", ".")).resolve()


def entry_file(entry: dict) -> Path | None:
    file = entry.get("file")
    if not file:
        return None
    path = Path(file)
    return path if path.is_absolute() else entry_directory(entry) / path


def include_paths_from_entry(entry: dict) -> list[str]:
    directory = entry_directory(entry)
    paths: list[str] = []
    arguments = entry_arguments(entry)
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in ("-I", "-isystem", "-iquote"):
            if index + 1 < len(arguments):
                paths.append(str((directory / arguments[index + 1]).resolve()))
                index += 2
                continue
        elif argument.startswith("-I") and len(argument) > 2:
            paths.append(str((directory / argument[2:]).resolve()))
        elif argument.startswith("-isystem") and len(argument) > len("-isystem"):
            paths.append(str((directory / argument[len("-isystem") :]).resolve()))
        elif argument.startswith("-iquote") and len(argument) > len("-iquote"):
            paths.append(str((directory / argument[len("-iquote") :]).resolve()))
        index += 1
    return list(dict.fromkeys(paths))


def defines_from_entry(entry: dict) -> list[str]:
    defines: list[str] = []
    arguments = entry_arguments(entry)
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in ("-D", "-U"):
            if index + 1 < len(arguments):
                defines.append(f"{argument}{arguments[index + 1]}")
                index += 2
                continue
        elif argument.startswith(("-D", "-U")):
            defines.append(argument)
        index += 1
    return list(dict.fromkeys(defines))


def standard_from_entry(entry: dict) -> str | None:
    for argument in entry_arguments(entry):
        if argument.startswith("-std="):
            return argument[len("-std=") :]
    return None


def _merge(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item not in merged:
                merged.append(item)
    return merged


def include_paths_from_entries(entries: list[dict]) -> list[str]:
    return _merge(*(include_paths_from_entry(entry) for entry in entries))


def defines_from_entries(entries: list[dict]) -> list[str]:
    return _merge(*(defines_from_entry(entry) for entry in entries))


def resolve_include_paths(
    config: Config, compile_commands_path: Path | None
) -> list[str]:
    paths = [str(Path(path).resolve()) for path in config.include_paths]
    if compile_commands_path:
        try:
            entries = load_compile_commands(compile_commands_path)
        except (OSError, TypeError, ValueError):
            entries = []
        paths = _merge(paths, include_paths_from_entries(entries))
    return paths


def resolve_defines(
    config: Config, compile_commands_path: Path | None
) -> list[str]:
    defines = list(config.defines)
    if compile_commands_path:
        try:
            entries = load_compile_commands(compile_commands_path)
        except (OSError, TypeError, ValueError):
            entries = []
        defines = _merge(defines, defines_from_entries(entries))
    return defines


@dataclass
class CompileFlags:
    include_paths: list[str]
    defines: list[str]
    standard: str


def compile_flags_for_file(
    config: Config,
    entries: list[dict] | None,
    file: Path,
) -> CompileFlags:
    config_includes = [str(Path(path).resolve()) for path in config.include_paths]
    if not entries:
        return CompileFlags(
            include_paths=config_includes,
            defines=list(config.defines),
            standard=config.cxx_standard,
        )
    if is_source(file):
        resolved = file.resolve()
        for entry in entries:
            entry_path = entry_file(entry)
            if entry_path is not None and entry_path.resolve() == resolved:
                return CompileFlags(
                    include_paths=_merge(
                        config_includes, include_paths_from_entry(entry)
                    ),
                    defines=_merge(config.defines, defines_from_entry(entry)),
                    standard=standard_from_entry(entry) or config.cxx_standard,
                )
    return CompileFlags(
        include_paths=_merge(config_includes, include_paths_from_entries(entries)),
        defines=_merge(config.defines, defines_from_entries(entries)),
        standard=config.cxx_standard,
    )
