"""Configuration for the maintainability engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_WEIGHTS: dict[str, float] = {
    "complexity": 0.24,
    "size": 0.10,
    "nesting": 0.08,
    "parameters": 0.05,
    "duplication": 0.15,
    "god_class": 0.10,
    "static_analysis": 0.06,
    "resource_safety": 0.08,
    "header_hygiene": 0.05,
    "cognitive_intent": 0.05,
    "testability": 0.02,
    "build_weight": 0.02,
}

DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "complexity": (10.0, 30.0),
    "size": (50.0, 200.0),
    "nesting": (3.0, 7.0),
    "parameters": (4.0, 8.0),
    "duplication": (0.03, 0.20),
    "god_class": (0.0, 1.0),
    "static_analysis": (0.0, 20.0),
    "resource_safety": (0.0, 10.0),
    "header_hygiene": (0.0, 10.0),
    "cognitive_intent": (0.0, 10.0),
    "testability": (0.0, 5.0),
    "build_weight": (0.0, 10.0),
}

DEFAULT_EXTENSIONS: tuple[str, ...] = (
    ".cpp",
    ".cc",
    ".cxx",
    ".c++",
    ".h",
    ".hpp",
    ".hxx",
    ".hh",
)

DEFAULT_IGNORE: tuple[str, ...] = (
    "build",
    "third_party",
    "vendor",
    "external",
    ".git",
    "cmake-build-*",
)

DEFAULT_ANALYZERS: tuple[str, ...] = (
    "heuristic",
    "duplication",
    "headers",
    "cognitive",
    "testability",
    "lizard",
    "cppcheck",
    "clang_tidy",
    "libclang",
)


@dataclass
class Config:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    thresholds: dict[str, tuple[float, float]] = field(
        default_factory=lambda: dict(DEFAULT_THRESHOLDS)
    )
    enabled_analyzers: list[str] = field(default_factory=lambda: list(DEFAULT_ANALYZERS))
    tool_paths: dict[str, str] = field(default_factory=dict)
    build_dir: str | None = None
    clang_version: str | None = None
    cxx_standard: str = "c++20"
    clang_tidy_checks: str | None = None
    clean_env: bool = True
    clean_env_vars: list[str] = field(
        default_factory=lambda: ["LD_LIBRARY_PATH"]
    )
    tool_env: dict[str, str] = field(default_factory=dict)
    libclang_library: str | None = None
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS
    ignore_patterns: tuple[str, ...] = DEFAULT_IGNORE
    max_file_bytes: int = 2_000_000
    gate_threshold: float = 8.0
    history_path: str = ".cpp-maintainability/history.sqlite3"

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or Path("cpp-maintainability.json")
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        config = cls()
        for key, value in data.items():
            if key == "thresholds":
                config.thresholds = {k: tuple(v) for k, v in value.items()}
            elif hasattr(config, key):
                setattr(config, key, value)
        return config

    def validate(self) -> None:
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0, got {total:.6f}")
        missing = set(self.weights) - set(self.thresholds)
        if missing:
            raise ValueError(f"missing thresholds for: {sorted(missing)}")
        for name, (good, bad) in self.thresholds.items():
            if bad <= good:
                raise ValueError(f"threshold for {name} must have bad > good")
