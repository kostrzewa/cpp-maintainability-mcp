"""Version-aware discovery of clang, cppcheck, and libclang."""

from __future__ import annotations

import ctypes.util
import os
import re
import shutil
import subprocess
from pathlib import Path

from .config import Config

DEFAULT_CLANG_TIDY_CHECKS = (
    "bugprone-*,readability-*,performance-*,cppcoreguidelines-*"
)


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _candidate_versions() -> list[str]:
    versions: set[str] = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(directory)
        if not path.is_dir():
            continue
        try:
            entries = list(path.iterdir())
        except OSError:
            continue
        for entry in entries:
            match = re.fullmatch(r"clang(?:-tidy)?-(\d+(?:\.\d+)*)", entry.name)
            if match:
                versions.add(match.group(1))
    for directory in Path("/usr/lib").glob("llvm-*"):
        match = re.fullmatch(r"llvm-(\d+(?:\.\d+)*)", directory.name)
        if match:
            versions.add(match.group(1))
    return sorted(versions, key=_version_key, reverse=True)


def detect_clang_version(config: Config) -> str | None:
    if config.clang_version:
        return config.clang_version
    versions = _candidate_versions()
    return versions[0] if versions else None


def resolve_executable(
    name: str, version: str | None, configured: str | None = None
) -> str | None:
    if configured:
        path = Path(configured)
        if path.is_file():
            return str(path)
        found = shutil.which(configured)
        if found:
            return found
    if version:
        found = shutil.which(f"{name}-{version}")
        if found:
            return found
    found = shutil.which(name)
    if found:
        return found
    if version:
        candidate = Path(f"/usr/lib/llvm-{version}/bin/{name}")
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_clang_tidy(config: Config) -> str | None:
    return resolve_executable(
        "clang-tidy",
        detect_clang_version(config),
        config.tool_paths.get("clang_tidy"),
    )


def resolve_cppcheck(config: Config) -> str | None:
    return resolve_executable(
        "cppcheck",
        detect_clang_version(config),
        config.tool_paths.get("cppcheck"),
    )


def resolve_clang(config: Config) -> str | None:
    return resolve_executable(
        "clang",
        detect_clang_version(config),
        config.tool_paths.get("clang"),
    )


def resolve_scan_build(config: Config) -> str | None:
    return resolve_executable(
        "scan-build",
        detect_clang_version(config),
        config.tool_paths.get("scan_build"),
    )


def _llvm_libdir(version: str) -> Path | None:
    llvm_config = shutil.which(f"llvm-config-{version}") or shutil.which(
        "llvm-config"
    )
    if not llvm_config:
        return None
    try:
        proc = subprocess.run(
            [llvm_config, "--libdir"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip())


def resolve_libclang(config: Config) -> str | None:
    if config.libclang_library:
        path = Path(config.libclang_library)
        if path.is_file():
            return str(path)
    version = detect_clang_version(config)
    candidates: list[Path] = []
    if version:
        candidates += [
            Path(f"/usr/lib/llvm-{version}/lib/libclang.so"),
            Path(f"/usr/lib/llvm-{version}/lib/libclang-{version}.so"),
            Path(f"/usr/lib/x86_64-linux-gnu/libclang-{version}.so.1"),
        ]
        libdir = _llvm_libdir(version)
        if libdir:
            candidates.append(libdir / "libclang.so")
    candidates += [
        Path("/usr/lib/llvm/lib/libclang.so"),
        Path("/usr/lib/x86_64-linux-gnu/libclang.so.1"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ctypes.util.find_library("clang")


def tool_environment(config: Config) -> dict[str, str]:
    env = os.environ.copy()
    if config.clean_env:
        for name in config.clean_env_vars:
            env.pop(name, None)
    env.update(config.tool_env)
    return env


def default_checks(config: Config, project_root: Path | None = None) -> str | None:
    if config.clang_tidy_checks:
        return config.clang_tidy_checks
    root = project_root or Path.cwd()
    if (root / ".clang-tidy").is_file():
        return None
    return DEFAULT_CLANG_TIDY_CHECKS
