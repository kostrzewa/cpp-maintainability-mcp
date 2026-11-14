# C++ Maintainability MCP Server

An MCP server that evaluates and improves the maintainability of C++ code
written by agents. It produces a composite 1–10 score, explains findings, ranks
refactorings, and closes the loop with a baseline/compare regression gate.

It runs as a **local stdio process** — no Docker, no hosted service.

## Features

- **Composite score** with Code Health–style bands: Healthy ≥ 8.0, Warning
  4.0–8.0, Alert < 4.0.
- **Analyzers**: clang-tidy, cppcheck (SARIF), libclang, lizard, duplication,
  header hygiene, cognitive/intent debt, and testability heuristics.
- **Version-aware tool discovery**: finds `clang-tidy-22`, `clang-22`,
  `llvm-config-22`, and `libclang-22` automatically.
- **Guide + Verify**: inject conventions before generation, scan the diff after.
- **Baseline and regression gate**: fail when the score drops, a new error
  appears, or a file enters the alert band.
- **History**: SQLite scan history for trends.
- **Graceful degradation**: the pure-Python analyzers keep working when clang
  tools are missing.

## Requirements

- Python **3.11+**
- Linux or macOS
- Optional but recommended:
  - clang 22 (`clang-tidy-22`, `clang-22`, `llvm-config-22`)
  - cppcheck 2.17+
  - libclang 22
  - the Python `clang` bindings (`clang>=21`), installed by the bootstrap
- opencode 1.19.5+ (legacy MCP config) or a newer V2 build

## Quick start

```sh
# 1. Bootstrap the Python environment and check the toolchain
./scripts/bootstrap.sh

# 2. Optional: tune the server for your C++ project
cp cpp-maintainability.example.json /path/to/cpp-project/cpp-maintainability.json

# 3. Add the MCP server to opencode (see below), restart opencode, then:
opencode mcp list
```

`bootstrap.sh` creates `.venv`, installs the package with the `clang` extra,
runs `scripts/check_toolchain.py`, and prints the exact opencode snippet with
resolved absolute paths.

### Bootstrap options

```sh
./scripts/bootstrap.sh --dev        # also install pytest and ruff
./scripts/bootstrap.sh --no-clang   # skip the Python clang bindings
./scripts/bootstrap.sh --python /usr/bin/python3.13
```

## Manual installation

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[clang]'
```

For development:

```sh
.venv/bin/pip install -e '.[clang,dev]'
```

Verify the toolchain:

```sh
.venv/bin/python scripts/check_toolchain.py
.venv/bin/python scripts/check_toolchain.py --strict   # fail if a tool is missing
.venv/bin/python scripts/check_toolchain.py --json
```

Start the server directly (it speaks MCP over stdio; Ctrl-C to stop):

```sh
.venv/bin/python -m cpp_maintainability_mcp
```

## Configure opencode

The server is a local MCP server. Add it to the **project** config
(`opencode.json` in the C++ project root) or the **global** config
(`~/.config/opencode/opencode.jsonc`).

### opencode 1.19.5 (legacy shape)

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cpp-maintainability": {
      "type": "local",
      "command": [
        "/path/to/cpp-maintainability-mcp/.venv/bin/python",
        "-m",
        "cpp_maintainability_mcp"
      ],
      "environment": {
        "PYTHONPATH": "/path/to/cpp-maintainability-mcp/src"
      },
      "enabled": true
    }
  }
}
```

### opencode V2 (newer builds)

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "cpp-maintainability": {
        "type": "local",
        "command": [
          "/path/to/cpp-maintainability-mcp/.venv/bin/python",
          "-m",
          "cpp_maintainability_mcp"
        ],
        "environment": {
          "PYTHONPATH": "/path/to/cpp-maintainability-mcp/src"
        },
        "codemode": false
      }
    }
  }
}
```

Generate the project config automatically:

```sh
.venv/bin/python scripts/opencode_config.py --project /path/to/cpp-project
.venv/bin/python scripts/opencode_config.py --project /path/to/cpp-project --v2
.venv/bin/python scripts/opencode_config.py --global   # prints the snippet
```

The script backs up an existing `opencode.json` before writing. For the global
JSONC file it prints the snippet instead of editing, because comments make safe
merging fragile.

### Global vs project

- **Project config** (`opencode.json` in the C++ project root) applies only to
  that project.
- **Global config** (`~/.config/opencode/opencode.jsonc`) applies everywhere.
- Omit `cwd` so the server runs in the current workspace and reads that
  project's `cpp-maintainability.json` and `.clang-tidy`.
- A project entry with the same server name replaces the global one.

Restart opencode after editing. Verify with `opencode mcp list` or `/mcps`.

## Tools

| Tool | Purpose |
|---|---|
| `guide` | C++ guidelines, project conventions, and prior findings before generation |
| `maintainability_scan` | Full or incremental scan; returns score, band, and findings |
| `maintainability_score` | Score and per-file breakdown only |
| `explain_finding` | Explain one finding ID and give a suggested fix |
| `suggest_refactorings` | Top-N highest-impact, lowest-effort refactorings |
| `compare_revisions` | Compare two paths or `"baseline"` and apply the gate |
| `track_trend` | Recent scan history |
| `baseline` | Record a snapshot for later comparison |

### Example prompts

- **Before coding**
  > Use the maintainability server to call `guide` for `src/` with task
  > "add a parser backend" and follow the returned guidelines.

- **After coding**
  > Scan the current diff with `maintainability_scan` and summarize the score
  > and top findings.

- **Targeted fixes**
  > Call `suggest_refactorings` on `src/` with budget 3 and apply the smallest
  > fix first.

- **Regression gate**
  > Record a `baseline`, then after my changes call `compare_revisions` with
  > `before="baseline"` and `after="src/"` and tell me if the gate passes.

- **Explain a finding**
  > Call `explain_finding` for finding `<id>` and explain why it matters.

### Recommended loop

```
guide → agent writes C++ → maintainability_scan(diff)
      → suggest_refactorings → agent fixes
      → compare_revisions(before="baseline", after=".")
      → repeat until the gate passes
```

## Configuration

The server reads `cpp-maintainability.json` from its working directory (the C++
project root when `cwd` is omitted). Start from
[`cpp-maintainability.example.json`](cpp-maintainability.example.json):

```json
{
  "clang_version": "22",
  "cxx_standard": "c++20",
  "clang_tidy_checks": "bugprone-*,readability-*,performance-*,cppcoreguidelines-*",
  "clean_env": true,
  "clean_env_vars": ["LD_LIBRARY_PATH"]
}
```

| Field | Default | Description |
|---|---|---|
| `clang_version` | auto-detect | Preferred clang version, e.g. `"22"` |
| `cxx_standard` | `"c++20"` | Standard passed to clang-tidy, cppcheck, and libclang |
| `clang_tidy_checks` | project `.clang-tidy`, else the default set | Explicit clang-tidy checks |
| `clean_env` | `true` | Remove `clean_env_vars` from analyzer subprocesses |
| `clean_env_vars` | `["LD_LIBRARY_PATH"]` | Variables removed when `clean_env` is on |
| `tool_env` | `{}` | Extra environment variables for analyzer subprocesses |
| `tool_paths` | `{}` | Explicit paths for `clang_tidy`, `cppcheck`, `libclang`, `clang`, `scan_build` |
| `libclang_library` | auto-detect | Explicit `libclang.so` path |
| `build_dir` | unset | `compile_commands.json` directory for clang-tidy |
| `enabled_analyzers` | all | Subset of `heuristic`, `duplication`, `headers`, `cognitive`, `testability`, `lizard`, `cppcheck`, `clang_tidy`, `libclang` |
| `weights` | see `config.py` | Per-dimension weights; must sum to 1.0 |
| `thresholds` | see `config.py` | `(good, bad)` thresholds per dimension |
| `gate_threshold` | `8.0` | Minimum score for `compare_revisions` |
| `history_path` | `.cpp-maintainability/history.sqlite3` | SQLite history location |
| `extensions` | C++ source/header suffixes | Files to scan |
| `ignore_patterns` | build/vendor dirs | Directories or globs to skip |
| `max_file_bytes` | `2000000` | Skip larger files |

### `clean_env` scope

`clean_env` applies **only** to the clang-tidy and cppcheck child processes. It
does not change the opencode session, the MCP server process, or your build
commands. Your C++ project keeps whatever modules and `LD_LIBRARY_PATH` it
needs; only the analyzer subprocesses get the sanitized environment.

## Toolchain discovery

The server resolves tools in this order:

1. `tool_paths` / `libclang_library` from `cpp-maintainability.json`.
2. Versioned executable: `clang-tidy-{version}`, `clang-{version}`,
   `scan-build-{version}`, `cppcheck-{version}`.
3. Unversioned executable: `clang-tidy`, `clang`, `scan-build`, `cppcheck`.
4. `/usr/lib/llvm-{version}/bin/{name}`.

libclang is resolved from:

1. `libclang_library`.
2. `/usr/lib/llvm-{version}/lib/libclang.so`.
3. `/usr/lib/x86_64-linux-gnu/libclang-{version}.so.1`.
4. `llvm-config-{version} --libdir`.
5. `ctypes.util.find_library("clang")`.

The Python bindings are loaded in-process with
`clang.cindex.Config.set_library_file(...)`.

## Troubleshooting

**`opencode mcp list` shows the server disconnected**

- Check the `command` and `PYTHONPATH` paths in `opencode.json`.
- Ensure `.venv/bin/python` exists and `python -m cpp_maintainability_mcp` starts.
- Run `opencode --print-logs --log-level DEBUG`.
- Restart opencode after config changes.

**`clang-tidy-22` fails with `CXXABI_1.3.15` or a `libstdc++` error**

- A module environment is shadowing the system `libstdc++`.
- `clean_env` already removes `LD_LIBRARY_PATH` for analyzer subprocesses.
- If it still fails, launch opencode from a clean shell.

**cppcheck reports `--output-format=json` is invalid**

- cppcheck 2.17+ uses SARIF. The adapter already passes
  `--output-format=sarif` and reads it from stderr.

**libclang is unavailable**

- Install the bindings: `.venv/bin/pip install 'clang>=21'`.
- Set `libclang_library` if auto-detection picks the wrong library.

**clang-tidy produces no findings**

- clang-tidy enables no checks without a config. Add a `.clang-tidy` to the
  project or set `clang_tidy_checks`.

**The score seems too high or too low**

- The weights are a starting point, not a calibrated truth. See
  [`references/SYNTHESIS.md`](references/SYNTHESIS.md) for the calibration plan.

**Where is history stored?**

- `.cpp-maintainability/history.sqlite3` under the server's working directory.

## Development

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
.venv/bin/ruff check src tests
.venv/bin/python scripts/check_toolchain.py
```

Project layout:

```
src/cpp_maintainability_mcp/
  server.py          # MCP tools
  engine.py          # orchestration
  scoring.py         # composite score
  config.py          # configuration
  toolchain.py       # version-aware tool discovery
  feedback.py        # ranking and regression gate
  guide.py           # pre-generation guidance
  history.py         # SQLite history
  analyzers/         # clang-tidy, cppcheck, libclang, heuristics
tests/               # unittest suite
tests/fixtures/      # C++ baseline samples (god class, leak, duplication, ...)
scripts/             # bootstrap, toolchain check, opencode config
references/          # paper corpus and design synthesis
```

## Design and references

- [`references/SYNTHESIS.md`](references/SYNTHESIS.md) — how the Code Health
  research maps to the server design.
- [`references/README.md`](references/README.md) — the reference corpus,
  including the *Code Red* paper and its citations.
- [`references/manifest.json`](references/manifest.json) — machine-readable
  citation and download status.

## License

MIT. See `pyproject.toml`.
