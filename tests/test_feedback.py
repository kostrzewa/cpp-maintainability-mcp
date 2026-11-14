import unittest

from maintainability_mcp.config import Config
from maintainability_mcp.feedback import FeedbackEngine
from maintainability_mcp.models import ProjectScore, make_finding


class FeedbackTests(unittest.TestCase):
    def test_rank_prefers_high_impact_low_effort(self):
        low = make_finding(
            file="a.cpp",
            rule="low",
            dimension="complexity",
            severity="warning",
            message="low",
            impact={"defects": 0.1},
            effort="L",
        )
        high = make_finding(
            file="b.cpp",
            rule="high",
            dimension="complexity",
            severity="warning",
            message="high",
            impact={"defects": 0.9},
            effort="S",
        )
        ranked = FeedbackEngine(Config()).rank([low, high], budget=1)
        self.assertEqual(ranked[0].id, high.id)

    def test_compare_reports_delta_and_gate(self):
        before = ProjectScore(8.0, "healthy", [], [])
        after = ProjectScore(7.0, "warning", [], [])
        result = FeedbackEngine(Config()).compare(before, after, threshold=8.0)
        self.assertEqual(result["delta"], -1.0)
        self.assertFalse(result["gate"]["passed"])

    def test_compare_detects_new_finding(self):
        finding = make_finding(
            file="a.cpp",
            rule="new",
            dimension="complexity",
            severity="error",
            message="new",
        )
        before = ProjectScore(8.0, "healthy", [], [])
        after = ProjectScore(8.5, "healthy", [], [finding])
        result = FeedbackEngine(Config()).compare(before, after, threshold=8.0)
        self.assertEqual(len(result["new"]), 1)
        self.assertFalse(result["gate"]["passed"])


if __name__ == "__main__":
    unittest.main()
