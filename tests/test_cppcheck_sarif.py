import unittest

from cpp_maintainability_mcp.analyzers.cppcheck_analyzer import CppcheckAnalyzer

SARIF = """
Checking foo.cpp ...
{
  "runs": [
    {
      "results": [
        {
          "level": "warning",
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": {"uri": "foo.cpp"},
                "region": {
                  "startLine": 6,
                  "startColumn": 5,
                  "endLine": 6,
                  "endColumn": 10
                }
              }
            }
          ],
          "message": {"text": "Memory leak: p"},
          "ruleId": "memleak"
        }
      ]
    }
  ]
}
"""


class CppcheckSarifTests(unittest.TestCase):
    def test_parse_sarif(self):
        items = CppcheckAnalyzer._parse_sarif(SARIF)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "memleak")
        self.assertEqual(items[0]["file"], "foo.cpp")
        self.assertEqual(items[0]["line"], 6)
        self.assertEqual(items[0]["column"], 5)
        self.assertEqual(items[0]["message"], "Memory leak: p")

    def test_parse_empty(self):
        self.assertEqual(CppcheckAnalyzer._parse_sarif(""), [])

    def test_parse_invalid(self):
        self.assertEqual(CppcheckAnalyzer._parse_sarif("not json"), [])


if __name__ == "__main__":
    unittest.main()
