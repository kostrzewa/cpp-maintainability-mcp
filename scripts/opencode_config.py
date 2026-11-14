#!/usr/bin/env python3
"""Write or print the opencode MCP server configuration."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "bin" / "python"
SRC = ROOT / "src"


def server_entry() -> dict:
    return {
        "type": "local",
        "command": [str(VENV_PY), "-m", "maintainability_mcp"],
        "environment": {"PYTHONPATH": str(SRC)},
    }


def legacy_snippet() -> dict:
    entry = server_entry()
    entry["enabled"] = True
    return {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {"maintainability": entry},
    }


def v2_snippet() -> dict:
    entry = server_entry()
    entry["codemode"] = False
    return {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {"servers": {"maintainability": entry}},
    }


def merge_legacy(existing: dict) -> dict:
    existing.setdefault("$schema", "https://opencode.ai/config.json")
    mcp = existing.setdefault("mcp", {})
    servers = mcp.get("servers")
    if isinstance(servers, dict):
        servers.pop("maintainability", None)
        if not servers:
            mcp.pop("servers", None)
    mcp["maintainability"] = legacy_snippet()["mcp"]["maintainability"]
    return existing


def merge_v2(existing: dict) -> dict:
    existing.setdefault("$schema", "https://opencode.ai/config.json")
    mcp = existing.setdefault("mcp", {})
    mcp.pop("maintainability", None)
    servers = mcp.setdefault("servers", {})
    servers["maintainability"] = v2_snippet()["mcp"]["servers"]["maintainability"]
    return existing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="project root (default: current directory)",
    )
    parser.add_argument(
        "--v2",
        action="store_true",
        help="use the V2 mcp.servers shape",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the result without writing",
    )
    parser.add_argument(
        "--global",
        dest="global_config",
        action="store_true",
        help="print the global config snippet instead of editing a project",
    )
    args = parser.parse_args()

    if args.global_config:
        snippet = v2_snippet() if args.v2 else legacy_snippet()
        print(json.dumps(snippet, indent=2))
        print(
            "\nAdd this under the top-level \"mcp\" key in "
            "~/.config/opencode/opencode.jsonc.",
            file=sys.stderr,
        )
        return 0

    project = args.project.resolve()
    config_path = project / "opencode.json"
    if not config_path.exists() and (project / ".opencode" / "opencode.json").exists():
        config_path = project / ".opencode" / "opencode.json"

    existing: dict = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"error: {config_path} is not valid JSON: {exc}", file=sys.stderr)
            print(
                "Edit it manually or use --dry-run to print the snippet.",
                file=sys.stderr,
            )
            return 1

    merged = merge_v2(existing) if args.v2 else merge_legacy(existing)
    text = json.dumps(merged, indent=2) + "\n"

    if args.dry_run:
        print(text, end="")
        return 0

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        shutil.copy2(config_path, config_path.with_suffix(config_path.suffix + ".bak"))
    config_path.write_text(text, encoding="utf-8")
    print(f"Wrote {config_path}")
    print("Restart opencode to load the MCP server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
