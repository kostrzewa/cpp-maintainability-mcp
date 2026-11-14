"""SQLite-backed scan history and baselines."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class HistoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                score REAL NOT NULL,
                band TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                score REAL NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def record_scan(
        self, repo: str, median: float, grade: str, payload: dict[str, Any]
    ) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO scans (repo, timestamp, score, band, payload) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    repo,
                    datetime.now(UTC).isoformat(),
                    median,
                    grade,
                    json.dumps(payload),
                ),
            )
            self.connection.commit()

    def record_baseline(
        self, repo: str, median: float, payload: dict[str, Any]
    ) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO baselines (repo, timestamp, score, payload) "
                "VALUES (?, ?, ?, ?)",
                (
                    repo,
                    datetime.now(UTC).isoformat(),
                    median,
                    json.dumps(payload),
                ),
            )
            self.connection.commit()

    def latest_baseline(self, repo: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM baselines WHERE repo = ? ORDER BY id DESC LIMIT 1",
                (repo,),
            ).fetchone()
        return dict(row) if row else None

    def recent_scans(self, repo: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT id, timestamp, score, band, payload FROM scans "
                "WHERE repo = ? ORDER BY id DESC LIMIT ?",
                (repo, limit),
            ).fetchall()
        scans = []
        for row in rows:
            payload = json.loads(row["payload"])
            scans.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "median": row["score"],
                    "grade": row["band"],
                    "distribution": payload.get("distribution", {}),
                }
            )
        return scans

    def recent_findings(self, repo: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            row = self.connection.execute(
                "SELECT payload FROM scans WHERE repo = ? ORDER BY id DESC LIMIT 1",
                (repo,),
            ).fetchone()
        if not row:
            return []
        payload = json.loads(row["payload"])
        return payload.get("findings", [])[:limit]

    def close(self) -> None:
        with self._lock:
            self.connection.close()
