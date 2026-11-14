import tempfile
import unittest
from pathlib import Path

from cpp_maintainability_mcp.analyzers.headers import HeaderAnalyzer


class HeaderTests(unittest.TestCase):
    def test_missing_guard_and_hygiene_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = Path(tmp) / "foo.h"
            header.write_text("#include <vector>\nusing namespace std;\n")
            result = HeaderAnalyzer().analyze(header)
            rules = {finding.rule for finding in result.findings}
            self.assertIn("missing-include-guard", rules)
            self.assertIn("using-namespace-in-header", rules)
            self.assertIn("heavy-include-in-header", rules)

    def test_guarded_header_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = Path(tmp) / "foo.h"
            header.write_text("#pragma once\nstruct Foo { int value; };\n")
            result = HeaderAnalyzer().analyze(header)
            self.assertFalse(result.findings)

    def test_non_header_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "foo.cpp"
            source.write_text("using namespace std;\n")
            result = HeaderAnalyzer().analyze(source)
            self.assertFalse(result.findings)


if __name__ == "__main__":
    unittest.main()
