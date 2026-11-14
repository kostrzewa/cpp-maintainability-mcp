import asyncio
import tempfile
import unittest
from pathlib import Path

from cpp_maintainability_mcp.config import Config
from cpp_maintainability_mcp.engine import MaintainabilityEngine
from cpp_maintainability_mcp.server import _Server, create_server

EXPECTED_TOOLS = {
    "guide",
    "maintainability_scan",
    "maintainability_score",
    "explain_finding",
    "suggest_refactorings",
    "compare_revisions",
    "track_trend",
    "baseline",
}


@unittest.skipIf(_Server is None, "mcp SDK not installed")
class ServerTests(unittest.TestCase):
    def test_tools_registered(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(history_path=str(Path(tmp) / "history.sqlite3"))
            engine = MaintainabilityEngine(config=config)
            server = create_server(engine)
            tools = asyncio.run(server.list_tools())
            self.assertEqual({tool.name for tool in tools}, EXPECTED_TOOLS)
            engine.close()


if __name__ == "__main__":
    unittest.main()
