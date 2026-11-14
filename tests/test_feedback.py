import unittest

from cpp_maintainability_mcp.config import Config
from cpp_maintainability_mcp.feedback import FeedbackEngine
from cpp_maintainability_mcp.models import FileScore, ProjectScore, make_finding


def distribution(**counts: int) -> dict[str, int]:
    base = {"excellent": 0, "good": 0, "fair": 0, "poor": 0, "bad": 0}
    base.update(counts)
    return base


def file_score(name: str, score: float, band: str, grade: str) -> FileScore:
    return FileScore(
        file=name,
        score=score,
        band=band,
        grade=grade,
        dimensions=[],
        findings=[],
    )


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

    def test_low_priority_findings_rank_below_genuine(self):
        low = make_finding(
            file="a.cpp",
            rule="low",
            dimension="static_analysis",
            severity="warning",
            message="low",
            impact={"defects": 0.1, "time": 0.1, "predictability": 0.1},
            effort="M",
        )
        genuine = make_finding(
            file="b.cpp",
            rule="genuine",
            dimension="static_analysis",
            severity="warning",
            message="genuine",
            impact={"defects": 0.4, "time": 0.3, "predictability": 0.3},
            effort="S",
        )
        ranked = FeedbackEngine(Config()).rank([low, genuine], budget=2)
        self.assertEqual(ranked[0].id, genuine.id)

    def test_compare_reports_regression(self):
        before = ProjectScore(
            8.0,
            "good",
            distribution(good=1),
            [],
            [],
            [file_score("a.cpp", 8.0, "healthy", "good")],
            [],
        )
        after = ProjectScore(
            7.0,
            "fair",
            distribution(fair=1),
            [],
            [],
            [file_score("a.cpp", 7.0, "warning", "fair")],
            [],
        )
        result = FeedbackEngine(Config()).compare(before, after, tolerance=0.5)
        self.assertEqual(result["median_delta"], -1.0)
        self.assertFalse(result["gate"]["passed"])
        self.assertEqual(len(result["regressions"]), 1)

    def test_compare_detects_new_finding(self):
        finding = make_finding(
            file="a.cpp",
            rule="new",
            dimension="complexity",
            severity="error",
            message="new",
        )
        before = ProjectScore(
            8.0, "good", distribution(good=1), [], [], [], []
        )
        after = ProjectScore(
            8.5, "good", distribution(good=1), [], [], [], [finding]
        )
        result = FeedbackEngine(Config()).compare(before, after)
        self.assertEqual(len(result["new"]), 1)
        self.assertFalse(result["gate"]["passed"])

    def test_compare_fails_on_new_bad_file(self):
        before = ProjectScore(
            8.0,
            "good",
            distribution(good=1),
            [],
            [],
            [file_score("a.cpp", 8.0, "healthy", "good")],
            [],
        )
        after = ProjectScore(
            3.0,
            "bad",
            distribution(bad=1),
            [],
            [],
            [file_score("a.cpp", 3.0, "alert", "bad")],
            [],
        )
        result = FeedbackEngine(Config()).compare(before, after, tolerance=10.0)
        self.assertFalse(result["gate"]["passed"])
        self.assertEqual(len(result["new_bad_files"]), 1)


if __name__ == "__main__":
    unittest.main()
