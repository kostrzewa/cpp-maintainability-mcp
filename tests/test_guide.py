import tempfile
import unittest
from pathlib import Path

from maintainability_mcp.config import Config
from maintainability_mcp.engine import MaintainabilityEngine


class GuideTests(unittest.TestCase):
    def test_guide_returns_core_guidelines(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(history_path=str(Path(tmp) / "history.sqlite3"))
            engine = MaintainabilityEngine(config=config)
            result = engine.guide([tmp], task="refactor memory handling")
            ids = {guideline["id"] for guideline in result["guidelines"]}
            self.assertIn("F.1", ids)
            self.assertIn("R.1", ids)
            self.assertTrue(result["checklist"])
            engine.close()

    def test_guide_detects_clang_tidy(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".clang-tidy").write_text(
                "Checks: 'bugprone-*,readability-*'\n"
            )
            config = Config(history_path=str(Path(tmp) / "history.sqlite3"))
            engine = MaintainabilityEngine(config=config)
            result = engine.guide([tmp])
            self.assertEqual(
                result["conventions"]["clang_tidy_checks"],
                "bugprone-*,readability-*",
            )
            engine.close()


if __name__ == "__main__":
    unittest.main()
