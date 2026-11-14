import unittest

from cpp_maintainability_mcp.config import Config
from cpp_maintainability_mcp.models import band_for, make_finding
from cpp_maintainability_mcp.scoring import ScoringEngine


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.engine = ScoringEngine(Config())

    def test_band_thresholds(self):
        self.assertEqual(band_for(8.0), "healthy")
        self.assertEqual(band_for(7.99), "warning")
        self.assertEqual(band_for(4.0), "warning")
        self.assertEqual(band_for(3.99), "alert")

    def test_clean_file_scores_ten(self):
        score = self.engine.score_file(
            "clean.cpp",
            {
                "complexity": 1,
                "size": 10,
                "nesting": 1,
                "parameters": 1,
                "duplication": 0.0,
                "nloc": 20,
            },
            [],
        )
        self.assertEqual(score.score, 10.0)
        self.assertEqual(score.band, "healthy")

    def test_bad_file_scores_alert(self):
        score = self.engine.score_file(
            "bad.cpp",
            {
                "complexity": 30,
                "size": 200,
                "nesting": 7,
                "parameters": 8,
                "duplication": 0.2,
                "god_class": 1.0,
                "static_analysis": 20,
                "resource_safety": 10,
                "header_hygiene": 10,
                "cognitive_intent": 5,
                "testability": 5,
                "build_weight": 10,
                "nloc": 200,
            },
            [],
        )
        self.assertLess(score.score, 4.0)
        self.assertEqual(score.band, "alert")

    def test_findings_without_metrics_are_counted(self):
        finding = make_finding(
            file="x.cpp",
            rule="r",
            dimension="static_analysis",
            severity="warning",
            message="m",
        )
        score = self.engine.score_file("x.cpp", {}, [finding])
        dimension = next(
            d for d in score.dimensions if d.name == "static_analysis"
        )
        self.assertGreater(dimension.penalty, 0.0)

    def test_project_score_weights_by_nloc(self):
        small = self.engine.score_file("small.cpp", {"nloc": 10}, [])
        large = self.engine.score_file("large.cpp", {"nloc": 1000}, [])
        large.score = 2.0
        project = self.engine.score_project([small, large], [])
        self.assertLess(project.score, 3.0)


if __name__ == "__main__":
    unittest.main()
