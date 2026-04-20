from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import EngineSnapshot, LiveEvent


class SQLiteRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS engine_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                as_of TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                player_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                value REAL NOT NULL
            )
            """
        )
        self.conn.commit()

    def persist_events(self, events: list[LiveEvent], max_rows: int) -> None:
        if not events:
            return

        with self.conn:
            self.conn.executemany(
                "INSERT INTO live_events (timestamp, player_id, event_type, value) VALUES (?, ?, ?, ?)",
                [(e.timestamp.isoformat(), e.player_id, e.event_type.value, e.value) for e in events],
            )
            self.conn.execute(
                """
                DELETE FROM live_events
                WHERE id NOT IN (
                    SELECT id FROM live_events ORDER BY id DESC LIMIT ?
                )
                """,
                (max_rows,),
            )

    def persist_snapshot(self, snapshot: EngineSnapshot, max_rows: int) -> None:
        payload_json = json.dumps(snapshot.model_dump(mode="json"))
        with self.conn:
            self.conn.execute(
                "INSERT INTO engine_snapshots (as_of, iteration, payload_json) VALUES (?, ?, ?)",
                (snapshot.as_of.isoformat(), snapshot.iteration, payload_json),
            )
            self.conn.execute(
                """
                DELETE FROM engine_snapshots
                WHERE id NOT IN (
                    SELECT id FROM engine_snapshots ORDER BY id DESC LIMIT ?
                )
                """,
                (max_rows,),
            )

    def latest_snapshot(self) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload_json FROM engine_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def close(self) -> None:
        self.conn.close()
