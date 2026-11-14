import tempfile
import unittest
from pathlib import Path

from cpp_maintainability_mcp.history import HistoryStore


class HistoryTests(unittest.TestCase):
    def test_record_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(Path(tmp) / "history.sqlite3")
            store.record_scan(
                "demo", 8.5, "healthy", {"findings": [{"id": "a"}]}
            )
            store.record_baseline("demo", 8.5, {"score": 8.5})
            self.assertEqual(len(store.recent_scans("demo")), 1)
            self.assertEqual(store.recent_findings("demo")[0]["id"], "a")
            self.assertIsNotNone(store.latest_baseline("demo"))
            store.close()

    def test_unknown_repo_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(Path(tmp) / "history.sqlite3")
            self.assertEqual(store.recent_scans("missing"), [])
            self.assertEqual(store.recent_findings("missing"), [])
            self.assertIsNone(store.latest_baseline("missing"))
            store.close()


if __name__ == "__main__":
    unittest.main()
