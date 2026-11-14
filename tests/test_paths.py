import json
import tempfile
import unittest
from pathlib import Path

from cpp_maintainability_mcp.config import Config
from cpp_maintainability_mcp.paths import (
    compile_flags_for_file,
    defines_from_entry,
    find_compile_commands,
    include_paths_from_entry,
    load_compile_commands,
    resolve_defines,
    resolve_include_paths,
)


def write_compile_commands(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries), encoding="utf-8")


class PathTests(unittest.TestCase):
    def test_find_explicit_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compile_commands.json"
            write_compile_commands(path, [])
            config = Config(compile_commands=str(path))
            self.assertEqual(find_compile_commands(config, []), path.resolve())

    def test_find_explicit_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compile_commands.json"
            write_compile_commands(path, [])
            config = Config(compile_commands=tmp)
            self.assertEqual(find_compile_commands(config, []), path.resolve())

    def test_find_build_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compile_commands.json"
            write_compile_commands(path, [])
            config = Config(build_dir=tmp)
            self.assertEqual(find_compile_commands(config, []), path.resolve())

    def test_find_auto_discover(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            path = project / "compile_commands.json"
            write_compile_commands(path, [])
            self.assertEqual(
                find_compile_commands(Config(), [str(project)]),
                path.resolve(),
            )

    def test_load_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compile_commands.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(TypeError):
                load_compile_commands(path)

    def test_include_paths_from_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            entry = {
                "directory": str(directory),
                "arguments": [
                    "clang++",
                    "-I",
                    "include",
                    "-isystem",
                    "system",
                    "-iquote",
                    "quote",
                    "-Iinline",
                    "-c",
                    "a.cpp",
                ],
            }
            paths = include_paths_from_entry(entry)
            self.assertIn(str((directory / "include").resolve()), paths)
            self.assertIn(str((directory / "system").resolve()), paths)
            self.assertIn(str((directory / "quote").resolve()), paths)
            self.assertIn(str((directory / "inline").resolve()), paths)

    def test_defines_from_entry(self):
        entry = {
            "arguments": [
                "clang++",
                "-DFOO=1",
                "-D",
                "BAR=2",
                "-UBAZ",
                "-c",
                "a.cpp",
            ]
        }
        self.assertEqual(
            defines_from_entry(entry), ["-DFOO=1", "-DBAR=2", "-UBAZ"]
        )

    def test_resolve_include_paths_merges_config_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compile_commands.json"
            write_compile_commands(
                path,
                [
                    {
                        "directory": tmp,
                        "arguments": ["clang++", "-I", "json", "-c", "a.cpp"],
                        "file": "a.cpp",
                    }
                ],
            )
            config = Config(include_paths=["config"])
            paths = resolve_include_paths(config, path)
            self.assertIn(str((Path.cwd() / "config").resolve()), paths)
            self.assertIn(str((Path(tmp) / "json").resolve()), paths)

    def test_resolve_defines_merges_config_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compile_commands.json"
            write_compile_commands(
                path,
                [
                    {
                        "directory": tmp,
                        "arguments": ["clang++", "-DJSON=1", "-c", "a.cpp"],
                        "file": "a.cpp",
                    }
                ],
            )
            config = Config(defines=["-DCONFIG=1"])
            self.assertEqual(
                resolve_defines(config, path), ["-DCONFIG=1", "-DJSON=1"]
            )

    def test_compile_flags_for_source_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "a.cpp"
            source.write_text("")
            entry = {
                "directory": str(root),
                "arguments": [
                    "clang++",
                    "-std=c++17",
                    "-I",
                    "include",
                    "-DFOO=1",
                    "-c",
                    "a.cpp",
                ],
                "file": "a.cpp",
            }
            config = Config(
                include_paths=["config"],
                defines=["-DBAR=2"],
                cxx_standard="c++20",
            )
            flags = compile_flags_for_file(config, [entry], source)
            self.assertEqual(flags.standard, "c++17")
            self.assertIn(str((root / "include").resolve()), flags.include_paths)
            self.assertIn(str((Path.cwd() / "config").resolve()), flags.include_paths)
            self.assertIn("-DFOO=1", flags.defines)
            self.assertIn("-DBAR=2", flags.defines)

    def test_compile_flags_for_header_union(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header = root / "a.h"
            header.write_text("")
            entries = [
                {
                    "directory": str(root),
                    "arguments": ["clang++", "-I", "one", "-DONE=1", "-c", "a.cpp"],
                    "file": "a.cpp",
                },
                {
                    "directory": str(root),
                    "arguments": ["clang++", "-I", "two", "-DTWO=1", "-c", "b.cpp"],
                    "file": "b.cpp",
                },
            ]
            flags = compile_flags_for_file(Config(), entries, header)
            self.assertIn(str((root / "one").resolve()), flags.include_paths)
            self.assertIn(str((root / "two").resolve()), flags.include_paths)
            self.assertIn("-DONE=1", flags.defines)
            self.assertIn("-DTWO=1", flags.defines)
            self.assertEqual(flags.standard, "c++20")

    def test_compile_flags_without_database(self):
        config = Config(
            include_paths=["include"],
            defines=["-DFOO=1"],
            cxx_standard="c++17",
        )
        flags = compile_flags_for_file(config, None, Path("a.cpp"))
        self.assertEqual(
            flags.include_paths, [str(Path("include").resolve())]
        )
        self.assertEqual(flags.defines, ["-DFOO=1"])
        self.assertEqual(flags.standard, "c++17")


if __name__ == "__main__":
    unittest.main()
