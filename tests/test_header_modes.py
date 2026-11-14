import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cpp_maintainability_mcp.analyzers.clang_tidy_analyzer import ClangTidyAnalyzer
from cpp_maintainability_mcp.analyzers.cppcheck_analyzer import CppcheckAnalyzer
from cpp_maintainability_mcp.analyzers.libclang_analyzer import LibclangAnalyzer


class HeaderModeTests(unittest.TestCase):
    def test_clang_tidy_direct_header(self):
        analyzer = ClangTidyAnalyzer(
            "/usr/bin/clang-tidy-22",
            "c++20",
            "bugprone-*",
            {},
            ["include"],
            ["-DFOO=1"],
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze(Path("a.h"))
            command = run.call_args.args[0]
            self.assertIn("-x", command)
            self.assertIn("c++-header", command)
            self.assertIn("-std=c++20", command)
            self.assertIn("-Iinclude", command)
            self.assertIn("-DFOO=1", command)

    def test_cppcheck_direct_header(self):
        analyzer = CppcheckAnalyzer(
            "/usr/bin/cppcheck", "c++20", {}, ["include"], ["-DFOO=1"]
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze(Path("a.h"))
            command = run.call_args.args[0]
            self.assertIn("--language=c++", command)
            self.assertIn("-Iinclude", command)
            self.assertIn("-DFOO=1", command)

    def test_cppcheck_project_mode(self):
        analyzer = CppcheckAnalyzer(
            "/usr/bin/cppcheck", "c++20", {}, [], [], jobs=4
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze_project(Path("build/compile_commands.json"), [Path("a.cpp")])
            command = run.call_args.args[0]
            self.assertTrue(any(arg.startswith("--project=") for arg in command))
            self.assertIn("-j4", command)

    def test_libclang_header_args(self):
        analyzer = LibclangAnalyzer(
            "/usr/lib/libclang.so", "c++20", ["include"], ["-DFOO=1"]
        )
        args = analyzer._parse_args(Path("a.h"))
        self.assertEqual(args[:3], ["-x", "c++-header", "-std=c++20"])
        self.assertIn("-Iinclude", args)
        self.assertIn("-DFOO=1", args)


if __name__ == "__main__":
    unittest.main()
