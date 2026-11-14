import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cpp_maintainability_mcp.analyzers.cppcheck_analyzer import CppcheckAnalyzer


def result(level: str, line: int, rule: str, message: str) -> dict:
    return {
        "level": level,
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": "a.cpp"},
                    "region": {"startLine": line},
                }
            }
        ],
        "message": {"text": message},
        "ruleId": rule,
    }


SARIF = json.dumps(
    {
        "runs": [
            {
                "results": [
                    result("note", 1, "normalCheckLevelMaxBranches", "info"),
                    result("warning", 2, "unusedStructMember", "unused 1"),
                    result("warning", 3, "unusedStructMember", "unused 2"),
                    result("error", 4, "memleak", "leak"),
                ]
            }
        ]
    }
)


class CppcheckFilterTests(unittest.TestCase):
    def test_filters_info_and_dedupes_members(self):
        analyzer = CppcheckAnalyzer("/usr/bin/cppcheck", "c++20", {})
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", stderr=SARIF, returncode=0)
            result = analyzer.analyze(Path("a.cpp"))
        rules = [finding.rule for finding in result.findings]
        self.assertNotIn("cppcheck:normalCheckLevelMaxBranches", rules)
        self.assertEqual(rules.count("cppcheck:unusedStructMember"), 1)
        self.assertIn("cppcheck:memleak", rules)


if __name__ == "__main__":
    unittest.main()
