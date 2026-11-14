import json
import tempfile
import unittest
from pathlib import Path

from cpp_maintainability_mcp.includes import (
    build_header_tu_map,
    choose_tu_per_header,
    parse_includes,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_compile_commands(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries), encoding="utf-8")


class IncludeTests(unittest.TestCase):
    def test_parse_quoted_and_angle(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = Path(tmp) / "a.h"
            write(header, '#include "local.h"\n#include <vector>\n')
            self.assertEqual(
                parse_includes(header),
                [(True, "local.h"), (False, "vector")],
            )

    def test_transitive_headers_map_to_tu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "tu.cpp", '#include "a.h"\n')
            write(root / "a.h", '#include "b.h"\n')
            write(root / "b.h", "int b = 0;\n")
            database = root / "compile_commands.json"
            write_compile_commands(
                database,
                [
                    {
                        "directory": str(root),
                        "arguments": ["clang++", "-I", ".", "-c", "tu.cpp"],
                        "file": "tu.cpp",
                    }
                ],
            )
            mapping = build_header_tu_map(database)
            tu = (root / "tu.cpp").resolve()
            self.assertEqual(mapping[(root / "a.h").resolve()], [tu])
            self.assertEqual(mapping[(root / "b.h").resolve()], [tu])

    def test_include_cycle_terminates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "tu.cpp", '#include "a.h"\n')
            write(root / "a.h", '#include "b.h"\n')
            write(root / "b.h", '#include "a.h"\n')
            database = root / "compile_commands.json"
            write_compile_commands(
                database,
                [
                    {
                        "directory": str(root),
                        "arguments": ["clang++", "-I", ".", "-c", "tu.cpp"],
                        "file": "tu.cpp",
                    }
                ],
            )
            mapping = build_header_tu_map(database)
            self.assertIn((root / "a.h").resolve(), mapping)
            self.assertIn((root / "b.h").resolve(), mapping)

    def test_choose_tu_per_header_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header = root / "a.h"
            first = root / "b.cpp"
            second = root / "a.cpp"
            mapping = {header: [first, second]}
            chosen = choose_tu_per_header(mapping, {header})
            self.assertEqual(chosen[header], second)

    def test_system_headers_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "tu.cpp", "#include <vector>\n")
            database = root / "compile_commands.json"
            write_compile_commands(
                database,
                [
                    {
                        "directory": str(root),
                        "arguments": ["clang++", "-c", "tu.cpp"],
                        "file": "tu.cpp",
                    }
                ],
            )
            self.assertEqual(build_header_tu_map(database), {})


if __name__ == "__main__":
    unittest.main()
