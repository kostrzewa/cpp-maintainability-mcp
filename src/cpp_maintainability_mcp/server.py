"""MCP server exposing the maintainability engine as tools."""

from __future__ import annotations

from typing import Any

from .engine import MaintainabilityEngine

try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
except ImportError:  # pragma: no cover - depends on the installed SDK
    try:  # mcp 2.x
        from mcp.server.mcpserver import MCPServer as _Server
    except ImportError:
        _Server = None


def create_server(engine: MaintainabilityEngine | None = None):
    if _Server is None:
        raise RuntimeError(
            "The 'mcp' package is required. Install with: pip install mcp"
        )
    engine = engine or MaintainabilityEngine()
    server = _Server("cpp-maintainability")

    @server.tool()
    def guide(
        paths: list[str],
        task: str = "",
        standards: list[str] | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        """Return conventions, C++ guidelines, and prior findings before generation."""
        return engine.guide(paths, task, standards, repo)

    @server.tool()
    def maintainability_scan(
        paths: list[str],
        diff: str | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        """Scan C++ files and return a composite score plus findings."""
        return engine.scan(paths, diff, repo).to_dict()

    @server.tool()
    def maintainability_score(
        paths: list[str],
        diff: str | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        """Return the composite score and per-file breakdown."""
        project = engine.scan(paths, diff, repo)
        return {
            "median": project.median,
            "grade": project.grade,
            "distribution": project.distribution,
            "worst_files": [summary.to_dict() for summary in project.worst_files],
            "best_files": [summary.to_dict() for summary in project.best_files],
            "files": [file.to_dict() for file in project.files],
            "tools": project.tools,
        }

    @server.tool()
    def explain_finding(finding_id: str) -> dict[str, Any]:
        """Explain a finding from the most recent scan."""
        return engine.explain(finding_id)

    @server.tool()
    def suggest_refactorings(
        paths: list[str],
        budget: int = 5,
        diff: str | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        """Return the highest-impact, lowest-effort refactorings."""
        return engine.suggest(paths, budget, diff, repo)

    @server.tool()
    def compare_revisions(
        before: str,
        after: str,
        tolerance: float | None = None,
        repo: str = ".",
    ) -> dict[str, Any]:
        """Compare two revisions (paths or 'baseline') and apply the regression gate."""
        return engine.compare(before, after, tolerance, repo)

    @server.tool()
    def track_trend(repo: str = ".", limit: int = 20) -> dict[str, Any]:
        """Return recent scan history."""
        return engine.trend(repo, limit)

    @server.tool()
    def baseline(paths: list[str], repo: str = ".") -> dict[str, Any]:
        """Record a baseline snapshot for regression gating."""
        return engine.baseline(paths, repo)

    return server


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
