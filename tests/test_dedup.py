import unittest

from cpp_maintainability_mcp.engine import _dedupe_findings
from cpp_maintainability_mcp.models import make_finding


def finding(
    rule: str,
    *,
    line: int = 1,
    dimension: str = "static_analysis",
    severity: str = "warning",
    confidence: float = 0.8,
):
    return make_finding(
        file="a.cpp",
        rule=rule,
        dimension=dimension,
        severity=severity,
        message=rule,
        start_line=line,
        confidence=confidence,
    )


class DedupTests(unittest.TestCase):
    def test_keeps_higher_confidence(self):
        low = finding("rule", confidence=0.5)
        high = finding("rule", confidence=0.9)
        result = _dedupe_findings([low, high])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].confidence, 0.9)

    def test_dedupes_magic_number_rules(self):
        first = finding("magic-number", dimension="cognitive_intent")
        second = finding(
            "clang-tidy:cppcoreguidelines-avoid-magic-numbers",
            dimension="cognitive_intent",
        )
        result = _dedupe_findings([first, second])
        self.assertEqual(len(result), 1)

    def test_keeps_distinct_rules_at_same_location(self):
        first = finding("missing-include-guard", dimension="header_hygiene")
        second = finding("heavy-include-in-header", dimension="header_hygiene")
        result = _dedupe_findings([first, second])
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
