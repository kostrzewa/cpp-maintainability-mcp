#!/usr/bin/env python3
"""Check the C++ analyzer toolchain used by the maintainability MCP server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maintainability_mcp.config import Config
from maintainability_mcp.toolchain import (
    detect_clang_version,
    resolve_clang_tidy,
    resolve_cppcheck,
    resolve_libclang,
)


def check_libclang_bindings(library: str | None) -> tuple[bool, str]:
    try:
        import clang.cindex as ci
    except ImportError:
        return False, "clang Python bindings not installed (pip install 'clang>=21')"
    try:
        if library:
            ci.Config.set_library_file(library)
        ci.Index.create()
        return True, "loaded"
    except Exception as exc:  # noqa: BLE001 - libclang raises backend-specific errors
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("maintainability.json"),
        help="path to maintainability.json (default: ./maintainability.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if a required tool is missing",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON",
    )
    args = parser.parse_args()

    config = Config.load(args.config)
    version = detect_clang_version(config)
    clang_tidy = resolve_clang_tidy(config)
    cppcheck = resolve_cppcheck(config)
    libclang = resolve_libclang(config)
    bindings_ok, bindings_detail = check_libclang_bindings(libclang)

    checks = [
        ("clang version", version or "not detected", bool(version)),
        ("clang-tidy", clang_tidy or "not found", bool(clang_tidy)),
        ("cppcheck", cppcheck or "not found", bool(cppcheck)),
        ("libclang", libclang or "not found", bool(libclang)),
        ("clang.cindex", bindings_detail, bindings_ok),
    ]

    if args.json:
        print(
            json.dumps(
                {
                    "clang_version": version,
                    "clang_tidy": clang_tidy,
                    "cppcheck": cppcheck,
                    "libclang": libclang,
                    "clang_cindex": {
                        "ok": bindings_ok,
                        "detail": bindings_detail,
                    },
                },
                indent=2,
            )
        )
    else:
        print("Maintainability MCP toolchain\n")
        for name, value, ok in checks:
            status = "ok" if ok else "missing"
            print(f"  {name:<14} {status:<8} {value}")
        print()
        if all(ok for _, _, ok in checks):
            print("All tools are available.")
        else:
            print("Some tools are missing. The server still runs with the")
            print("pure-Python fallbacks, but clang-tidy/cppcheck/libclang")
            print("findings will be unavailable.")

    required = [bool(clang_tidy), bool(cppcheck), bool(libclang), bindings_ok]
    if args.strict and not all(required):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
