import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cpp_maintainability_mcp.analyzers.clang_tidy_analyzer import ClangTidyAnalyzer
from cpp_maintainability_mcp.analyzers.cppcheck_analyzer import CppcheckAnalyzer


class AnalyzerCommandTests(unittest.TestCase):
    def test_clang_tidy_command_uses_versioned_tool_and_standard(self):
        analyzer = ClangTidyAnalyzer(
            "/usr/bin/clang-tidy-22",
            None,
            "c++20",
            "bugprone-*",
            {"LD_LIBRARY_PATH": None},
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze(Path("foo.cpp"))
            command = run.call_args.args[0]
            self.assertEqual(command[0], "/usr/bin/clang-tidy-22")
            self.assertIn("-checks=bugprone-*", command)
            self.assertIn("-std=c++20", command)
            self.assertEqual(
                run.call_args.kwargs["env"], {"LD_LIBRARY_PATH": None}
            )

    def test_clang_tidy_omits_checks_when_project_config_exists(self):
        analyzer = ClangTidyAnalyzer(
            "/usr/bin/clang-tidy-22", None, "c++20", None, {}
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze(Path("foo.cpp"))
            command = run.call_args.args[0]
            self.assertFalse(any(item.startswith("-checks=") for item in command))

    def test_cppcheck_command_uses_sarif_and_standard(self):
        analyzer = CppcheckAnalyzer(
            "/usr/bin/cppcheck", "c++20", {"LD_LIBRARY_PATH": None}
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze(Path("foo.cpp"))
            command = run.call_args.args[0]
            self.assertEqual(command[0], "/usr/bin/cppcheck")
            self.assertIn("--output-format=sarif", command)
            self.assertIn("--std=c++20", command)
            self.assertEqual(
                run.call_args.kwargs["env"], {"LD_LIBRARY_PATH": None}
            )

    def test_unavailable_when_executable_missing(self):
        self.assertFalse(ClangTidyAnalyzer(None).available())
        self.assertFalse(CppcheckAnalyzer(None).available())


if __name__ == "__main__":
    unittest.main()
