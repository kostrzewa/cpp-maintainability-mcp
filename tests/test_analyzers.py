import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cpp_maintainability_mcp.analyzers.clang_tidy_analyzer import ClangTidyAnalyzer
from cpp_maintainability_mcp.analyzers.cppcheck_analyzer import CppcheckAnalyzer


class AnalyzerCommandTests(unittest.TestCase):
    def test_clang_tidy_command_uses_versioned_tool_and_standard(self):
        analyzer = ClangTidyAnalyzer(
            "/usr/bin/clang-tidy-22",
            "c++20",
            "bugprone-*",
            {"LD_LIBRARY_PATH": None},
            ["include"],
            ["-DFOO=1"],
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze(Path("foo.cpp"))
            command = run.call_args.args[0]
            self.assertEqual(command[0], "/usr/bin/clang-tidy-22")
            self.assertIn("-checks=bugprone-*", command)
            self.assertIn("-std=c++20", command)
            self.assertIn("-Iinclude", command)
            self.assertIn("-DFOO=1", command)
            self.assertEqual(
                run.call_args.kwargs["env"], {"LD_LIBRARY_PATH": None}
            )

    def test_clang_tidy_omits_checks_when_project_config_exists(self):
        analyzer = ClangTidyAnalyzer(
            "/usr/bin/clang-tidy-22", "c++20", None, {}
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze(Path("foo.cpp"))
            command = run.call_args.args[0]
            self.assertFalse(any(item.startswith("-checks=") for item in command))

    def test_cppcheck_command_uses_sarif_and_standard(self):
        analyzer = CppcheckAnalyzer(
            "/usr/bin/cppcheck", "c++20", {}, ["include"], ["-DFOO=1"]
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            analyzer.analyze(Path("foo.cpp"))
            command = run.call_args.args[0]
            self.assertEqual(command[0], "/usr/bin/cppcheck")
            self.assertIn("--output-format=sarif", command)
            self.assertIn("--std=c++20", command)
            self.assertIn("-Iinclude", command)
            self.assertIn("-DFOO=1", command)

    def test_unavailable_when_executable_missing(self):
        self.assertFalse(ClangTidyAnalyzer(None).available())
        self.assertFalse(CppcheckAnalyzer(None).available())

    def test_low_priority_checks_are_deprioritized(self):
        analyzer = ClangTidyAnalyzer(
            "/usr/bin/clang-tidy-22", "c++20", "bugprone-*", {}
        )
        output = (
            "a.cpp:1:1: warning: swap "
            "[bugprone-easily-swappable-parameters]\n"
            "a.cpp:2:1: warning: magic "
            "[cppcoreguidelines-avoid-magic-numbers,readability-magic-numbers]\n"
        )
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout=output, stderr="", returncode=0)
            result = analyzer.analyze(Path("a.cpp"))
        by_rule = {finding.rule: finding for finding in result.findings}
        swap = by_rule["clang-tidy:bugprone-easily-swappable-parameters"]
        magic = by_rule[
            "clang-tidy:cppcoreguidelines-avoid-magic-numbers,"
            "readability-magic-numbers"
        ]
        self.assertEqual(swap.effort, "M")
        self.assertLess(sum(swap.impact.values()), 1.0)
        self.assertEqual(magic.effort, "S")
        self.assertLess(sum(magic.impact.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
