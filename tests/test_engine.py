import shutil
import tempfile
import unittest
from pathlib import Path

from maintainability_mcp.config import Config
from maintainability_mcp.engine import MaintainabilityEngine


def make_engine(tmp: str) -> MaintainabilityEngine:
    config = Config(
        history_path=str(Path(tmp) / "history.sqlite3"),
        enabled_analyzers=[
            "heuristic",
            "duplication",
            "headers",
            "cognitive",
            "testability",
        ],
    )
    return MaintainabilityEngine(config=config)


class EngineTests(unittest.TestCase):
    def test_scan_small_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.cpp"
            source.write_text("int add(int a, int b) { return a + b; }\n")
            engine = make_engine(tmp)
            project = engine.scan([str(source)], repo="test")
            self.assertGreaterEqual(project.score, 1.0)
            self.assertLessEqual(project.score, 10.0)
            self.assertEqual(len(project.files), 1)
            engine.close()
            self.assertIn("heuristic", project.tools)
            engine.close()

    def test_scan_finds_long_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "long.cpp"
            body = "\n".join(f"    value += {i};" for i in range(120))
            source.write_text(f"int process(int value) {{\n{body}\n    return value;\n}}\n")
            engine = make_engine(tmp)
            project = engine.scan([str(source)], repo="test")
            rules = {finding.rule for finding in project.findings}
            self.assertIn("long-function", rules)
            engine.close()

    def test_baseline_and_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.cpp"
            source.write_text("int add(int a, int b) { return a + b; }\n")
            engine = make_engine(tmp)
            engine.baseline([str(source)], repo="test")
            result = engine.compare("baseline", str(source), repo="test")
            self.assertEqual(result["delta"], 0.0)
            self.assertTrue(result["gate"]["passed"])
            engine.close()

    def test_diff_filters_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.cpp"
            source.write_text("int add(int a, int b) { return a + b; }\n")
            engine = make_engine(tmp)
            diff = (
                f"--- a/{source}\n+++ b/{source}\n"
                "@@ -1,1 +1,1 @@\n-int add(int a, int b) { return a + b; }\n"
                "+int add(int a, int b) { return a + b + 1; }\n"
            )
            project = engine.scan([str(source)], diff=diff, repo="test")
            self.assertEqual(len(project.files), 1)
            engine.close()

    @unittest.skipUnless(
        shutil.which("clang-tidy-22") and shutil.which("cppcheck"),
        "clang-tidy-22 and cppcheck are required",
    )
    def test_real_toolchain(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "leak.cpp"
            source.write_text(
                "#include <vector>\nusing namespace std;\n"
                "int main() { int* p = new int; return 0; }\n"
            )
            config = Config(
                history_path=str(Path(tmp) / "history.sqlite3"),
                clang_version="22",
                cxx_standard="c++20",
            )
            engine = MaintainabilityEngine(config=config)
            project = engine.scan([str(source)], repo="test")
            self.assertEqual(project.tools.get("clang_tidy"), "ok")
            self.assertEqual(project.tools.get("cppcheck"), "ok")
            rules = {finding.rule for finding in project.findings}
            self.assertTrue(any(rule.startswith("cppcheck:") for rule in rules))
            engine.close()


if __name__ == "__main__":
    unittest.main()
