import shutil
import tempfile
import unittest
from pathlib import Path

from cpp_maintainability_mcp.config import Config
from cpp_maintainability_mcp.engine import MaintainabilityEngine

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def libclang_available() -> bool:
    try:
        import clang.cindex  # noqa: F401

        return True
    except ImportError:
        return False


def scan(paths, tmp, analyzers, **config_kwargs):
    if isinstance(paths, (str, Path)):
        paths = [str(paths)]
    config = Config(
        history_path=str(Path(tmp) / "history.sqlite3"),
        enabled_analyzers=analyzers,
        **config_kwargs,
    )
    engine = MaintainabilityEngine(config=config)
    project = engine.scan([str(path) for path in paths], repo="fixtures")
    engine.close()
    return project


class FixtureTests(unittest.TestCase):
    def test_clean_fixture_has_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = scan(
                FIXTURES / "clean.cpp",
                tmp,
                [
                    "heuristic",
                    "duplication",
                    "headers",
                    "cognitive",
                    "testability",
                    "lizard",
                ],
            )
            self.assertEqual(project.findings, [])
            self.assertEqual(project.score, 10.0)

    def test_long_function_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = scan(FIXTURES / "long_function.cpp", tmp, ["heuristic"])
            rules = {finding.rule for finding in project.findings}
            self.assertIn("high-cyclomatic-complexity", rules)

    def test_bad_header_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = scan(FIXTURES / "bad_header.h", tmp, ["headers"])
            rules = {finding.rule for finding in project.findings}
            self.assertIn("missing-include-guard", rules)
            self.assertIn("using-namespace-in-header", rules)
            self.assertIn("heavy-include-in-header", rules)

    def test_duplicate_pair_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = scan(
                [FIXTURES / "duplicate_a.cpp", FIXTURES / "duplicate_b.cpp"],
                tmp,
                ["duplication"],
            )
            rules = {finding.rule for finding in project.findings}
            self.assertIn("duplicate-block", rules)

    @unittest.skipUnless(shutil.which("cppcheck"), "cppcheck not installed")
    def test_memory_leak_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = scan(FIXTURES / "memory_leak.cpp", tmp, ["cppcheck"])
            rules = {finding.rule for finding in project.findings}
            self.assertIn("cppcheck:memleak", rules)

    @unittest.skipUnless(
        libclang_available(), "clang Python bindings not installed"
    )
    def test_god_class_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = scan(
                FIXTURES / "god_class.cpp",
                tmp,
                ["libclang"],
                clang_version="22",
            )
            rules = {finding.rule for finding in project.findings}
            self.assertIn("god-class", rules)

    @unittest.skipUnless(
        (shutil.which("clang-tidy-22") or shutil.which("clang-tidy"))
        and shutil.which("cppcheck"),
        "clang-tidy and cppcheck are required",
    )
    def test_direct_header_fallback_has_no_mode_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = scan(
                FIXTURES / "bad_header.h",
                tmp,
                ["clang_tidy", "cppcheck"],
            )
            rules = {finding.rule for finding in project.findings}
            self.assertNotIn("clang-tidy:clang-diagnostic-error", rules)
            self.assertNotIn("cppcheck:syntaxError", rules)


if __name__ == "__main__":
    unittest.main()
