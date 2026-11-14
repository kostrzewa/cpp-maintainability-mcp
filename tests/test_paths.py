import json
import tempfile
import unittest
from pathlib import Path

from cpp_maintainability_mcp.config import Config
from cpp_maintainability_mcp.paths import (
    find_compile_commands,
    include_paths_from_entry,
    load_compile_commands,
    resolve_include_paths,
    tu_files,
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

    def test_tu_files_resolves_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compile_commands.json"
            write_compile_commands(
                path,
                [{"directory": tmp, "command": "clang++ -c a.cpp", "file": "a.cpp"}],
            )
            self.assertEqual(tu_files(path), [(Path(tmp) / "a.cpp").resolve()])

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


if __name__ == "__main__":
    unittest.main()
