#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
DEV=0
CLANG=1

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap.sh [options]

Create .venv, install the maintainability MCP server, and check the toolchain.

Options:
  --dev        also install development dependencies (pytest, ruff)
  --no-clang   skip the Python clang bindings (disables libclang analysis)
  --python P   Python interpreter to use (default: python3)
  -h, --help   show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev)
      DEV=1
      shift
      ;;
    --no-clang)
      CLANG=0
      shift
      ;;
    --python)
      PYTHON="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "error: $PYTHON not found" >&2
  exit 1
fi

"$PYTHON" - <<'PY'
import sys

if sys.version_info < (3, 11):
    raise SystemExit(
        f"error: Python 3.11+ required, found {sys.version.split()[0]}"
    )
PY

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "Creating .venv..."
  "$PYTHON" -m venv "$ROOT/.venv"
fi

VENV_PY="$ROOT/.venv/bin/python"
echo "Upgrading pip..."
"$VENV_PY" -m pip install --quiet --upgrade pip

EXTRAS=""
if [[ "$CLANG" -eq 1 ]]; then
  EXTRAS="clang"
fi
if [[ "$DEV" -eq 1 ]]; then
  if [[ -n "$EXTRAS" ]]; then
    EXTRAS="$EXTRAS,dev"
  else
    EXTRAS="dev"
  fi
fi

if [[ -n "$EXTRAS" ]]; then
  echo "Installing maintainability-mcp[$EXTRAS]..."
  (cd "$ROOT" && "$VENV_PY" -m pip install --quiet -e ".[$EXTRAS]")
else
  echo "Installing maintainability-mcp..."
  (cd "$ROOT" && "$VENV_PY" -m pip install --quiet -e ".")
fi

echo
"$VENV_PY" "$ROOT/scripts/check_toolchain.py" || true

cat <<EOF

Bootstrap complete.

Next steps:
  1. Optional: copy the example config into your C++ project:
       cp "$ROOT/maintainability.example.json" /path/to/cpp-project/maintainability.json

  2. Add the MCP server to opencode (1.19.5 legacy shape):

       "mcp": {
         "maintainability": {
           "type": "local",
           "command": ["$VENV_PY", "-m", "maintainability_mcp"],
           "environment": {"PYTHONPATH": "$ROOT/src"},
           "enabled": true
         }
       }

     Or generate it with:
       "$VENV_PY" "$ROOT/scripts/opencode_config.py" --project /path/to/cpp-project

  3. Restart opencode and verify with: opencode mcp list
EOF
