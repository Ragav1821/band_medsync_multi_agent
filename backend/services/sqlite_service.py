"""
SQLiteStorageService — Phase 19
Persists incidents, action plans, agent messages, audit events,
and coordination rounds to a local SQLite database.

Design goals:
- Zero external dependencies (stdlib sqlite3 only)
- Backward-compatible: mirrors the in-memory IncidentStore API
- All reads return plain dicts — identical to the in-memory store
- Thread-safe via sqlite3's check_same_thread=False + WAL mode
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# DB file sits next to main.py (backend directory)
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "medsync.db")


# ── Schema ─────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id         TEXT PRIMARY KEY,
    data       TEXT NOT NULL,          -- JSON blob
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at);

CREATE TABLE IF NOT EXISTS action_plans (
    id          TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    data        TEXT NOT NULL,          -- JSON blob
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plans_incident ON action_plans(incident_id);

CREATE TABLE IF NOT EXISTS agent_messages (
    id          TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    data        TEXT NOT NULL,          -- JSON blob
    timestamp   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msgs_incident ON agent_messages(incident_id);
CREATE INDEX IF NOT EXISTS idx_msgs_timestamp ON agent_messages(timestamp);

CREATE TABLE IF NOT EXISTS audit_events (
    id          TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    data        TEXT NOT NULL,          -- JSON blob
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_incident ON audit_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_audit_created  ON audit_events(created_at);

CREATE TABLE IF NOT EXISTS coordination_rounds (
    incident_id TEXT PRIMARY KEY,
    data        TEXT NOT NULL,          -- JSON blob
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id          TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    data        TEXT NOT NULL,          -- JSON blob
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_incident ON agent_runs(incident_id);
"""


class SQLiteStorageService:
    """
    Persistent storage using a local SQLite file (medsync.db).

    All public methods are synchronous and safe to call from both
    sync and async contexts (FastAPI background tasks use threads).
    """

    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path
        self._conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
            isolation_level=None,   # autocommit — we manage transactions manually
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        logger.info("[SQLite] Storage initialised at %s", db_path)

    # ── Internal helpers ────────────────────────────────────────────────────────

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        try:
            return self._conn.execute(sql, params)
        except sqlite3.Error as exc:
            logger.error("[SQLite] Query error: %s | SQL: %s", exc, sql)
            raise

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    # ── Incidents ───────────────────────────────────────────────────────────────

    def save_incident(self, incident: Dict) -> None:
        """Upsert an incident record."""
        self._exec(
            "INSERT OR REPLACE INTO incidents (id, data, created_at) VALUES (?, ?, ?)",
            (incident["id"], json.dumps(incident), incident.get("created_at", self._now())),
        )

    def load_incident(self, incident_id: str) -> Optional[Dict]:
        row = self._exec(
            "SELECT data FROM incidents WHERE id=?", (incident_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def load_all_incidents(self) -> List[Dict]:
        rows = self._exec(
            "SELECT data FROM incidents ORDER BY created_at DESC"
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Action Plans ────────────────────────────────────────────────────────────

    def save_action_plan(self, plan: Dict) -> None:
        """Upsert an action plan."""
        self._exec(
            "INSERT OR REPLACE INTO action_plans (id, incident_id, data, created_at) VALUES (?, ?, ?, ?)",
            (plan["id"], plan["incident_id"], json.dumps(plan), plan.get("created_at", self._now())),
        )

    def load_action_plan_for_incident(self, incident_id: str) -> Optional[Dict]:
        row = self._exec(
            "SELECT data FROM action_plans WHERE incident_id=? ORDER BY created_at DESC LIMIT 1",
            (incident_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def load_action_plan_by_id(self, plan_id: str) -> Optional[Dict]:
        row = self._exec(
            "SELECT data FROM action_plans WHERE id=?", (plan_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    # ── Agent Messages ──────────────────────────────────────────────────────────

    def save_agent_message(self, msg: Dict) -> None:
        """Persist one AgentMessage dict."""
        self._exec(
            "INSERT OR REPLACE INTO agent_messages (id, incident_id, data, timestamp) VALUES (?, ?, ?, ?)",
            (
                msg.get("id", str(uuid.uuid4())),
                msg["incident_id"],
                json.dumps(msg),
                msg.get("timestamp", self._now()),
            ),
        )

    def load_messages_for_incident(self, incident_id: str) -> List[Dict]:
        rows = self._exec(
            "SELECT data FROM agent_messages WHERE incident_id=? ORDER BY timestamp ASC",
            (incident_id,),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Audit Events ────────────────────────────────────────────────────────────

    def save_audit_event(self, event: Dict) -> None:
        self._exec(
            "INSERT OR IGNORE INTO audit_events (id, incident_id, data, created_at) VALUES (?, ?, ?, ?)",
            (
                event.get("id", str(uuid.uuid4())),
                event["incident_id"],
                json.dumps(event),
                event.get("created_at", self._now()),
            ),
        )

    def load_audit_events_for_incident(self, incident_id: str) -> List[Dict]:
        rows = self._exec(
            "SELECT data FROM audit_events WHERE incident_id=? ORDER BY created_at ASC",
            (incident_id,),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def load_all_audit_events(self) -> List[Dict]:
        rows = self._exec(
            "SELECT data FROM audit_events ORDER BY created_at DESC"
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Coordination Rounds ─────────────────────────────────────────────────────

    def save_coordination_round(self, incident_id: str, round_data: Dict) -> None:
        """Upsert coordination round tracking for an incident."""
        self._exec(
            "INSERT OR REPLACE INTO coordination_rounds (incident_id, data, updated_at) VALUES (?, ?, ?)",
            (incident_id, json.dumps(round_data), self._now()),
        )

    def load_coordination_round(self, incident_id: str) -> Optional[Dict]:
        row = self._exec(
            "SELECT data FROM coordination_rounds WHERE incident_id=?", (incident_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def load_all_coordination_rounds(self) -> List[Dict]:
        rows = self._exec("SELECT data FROM coordination_rounds").fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Agent Runs ──────────────────────────────────────────────────────────────

    def save_agent_run(self, run: Dict) -> None:
        self._exec(
            "INSERT OR REPLACE INTO agent_runs (id, incident_id, data, created_at) VALUES (?, ?, ?, ?)",
            (
                run["id"],
                run["incident_id"],
                json.dumps(run),
                run.get("started_at", self._now()),
            ),
        )

    def load_agent_runs_for_incident(self, incident_id: str) -> List[Dict]:
        rows = self._exec(
            "SELECT data FROM agent_runs WHERE incident_id=? ORDER BY created_at ASC",
            (incident_id,),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]


# ── Singleton ──────────────────────────────────────────────────────────────────
_sqlite_service: Optional[SQLiteStorageService] = None


def get_sqlite_service() -> SQLiteStorageService:
    global _sqlite_service
    if _sqlite_service is None:
        _sqlite_service = SQLiteStorageService()
    return _sqlite_service
