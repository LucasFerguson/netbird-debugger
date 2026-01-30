"""SQLite database helpers."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterable, Optional

from config import Config
from storage.models import schema_statements


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Database:
    path: str
    _conn: Optional[sqlite3.Connection] = None
    _lock: Lock = Lock()

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self) -> None:
        conn = self.connect()
        with self._lock:
            for stmt in schema_statements():
                conn.execute(stmt)
            conn.commit()

    def _execute(
        self, query: str, params: Iterable[Any] | None = None
    ) -> sqlite3.Cursor:
        conn = self.connect()
        with self._lock:
            cursor = conn.execute(query, params or [])
            conn.commit()
        return cursor

    def log_health_check(self, data: dict[str, Any]) -> int:
        cursor = self._execute(
            """
            INSERT INTO health_checks (
                timestamp, check_type,
                netbird_running, netbird_pid, netbird_uptime_seconds,
                netbird_cpu_percent, netbird_memory_mb,
                internet_reachable, dns_working, services_status,
                system_healthy, check_duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                data.get("timestamp", _utc_now()),
                data.get("check_type", "routine"),
                data.get("netbird_running"),
                data.get("netbird_pid"),
                data.get("netbird_uptime_seconds"),
                data.get("netbird_cpu_percent"),
                data.get("netbird_memory_mb"),
                data.get("internet_reachable"),
                data.get("dns_working"),
                json.dumps(data.get("services_status", {})),
                data.get("system_healthy"),
                data.get("check_duration_ms"),
            ],
        )
        return int(cursor.lastrowid)

    def log_failure(self, data: dict[str, Any]) -> int:
        cursor = self._execute(
            """
            INSERT INTO failures (
                timestamp, failure_type, severity,
                diagnostics, auto_restart_attempted,
                restart_successful, recovery_timestamp, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                data.get("timestamp", _utc_now()),
                data.get("failure_type", "auto_detected"),
                data.get("severity"),
                json.dumps(data.get("diagnostics", {})),
                data.get("auto_restart_attempted"),
                data.get("restart_successful"),
                data.get("recovery_timestamp"),
                data.get("notes"),
            ],
        )
        return int(cursor.lastrowid)

    def update_failure(self, failure_id: int, updates: dict[str, Any]) -> None:
        if not updates:
            return

        fields = []
        values = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            values.append(value)
        values.append(failure_id)

        self._execute(
            f"UPDATE failures SET {', '.join(fields)} WHERE id = ?",
            values,
        )

    def log_windows_event(self, data: dict[str, Any]) -> int:
        cursor = self._execute(
            """
            INSERT INTO windows_events (
                captured_timestamp, event_timestamp, event_id,
                source, level, message, related_failure_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                data.get("captured_timestamp", _utc_now()),
                data.get("event_timestamp", _utc_now()),
                data.get("event_id"),
                data.get("source"),
                data.get("level"),
                data.get("message"),
                data.get("related_failure_id"),
            ],
        )
        return int(cursor.lastrowid)

    def log_meta_log(
        self,
        *,
        level: str,
        component: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
        check_name: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> int:
        cursor = self._execute(
            """
            INSERT INTO meta_logs (
                timestamp, level, component, message,
                details, check_name, error_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                _utc_now(),
                level,
                component,
                message,
                json.dumps(details) if details else None,
                check_name,
                error_type,
            ],
        )
        return int(cursor.lastrowid)

    def get_recent_failures(self, limit: int = 10) -> list[sqlite3.Row]:
        cursor = self._execute(
            "SELECT * FROM failures ORDER BY timestamp DESC LIMIT ?",
            [limit],
        )
        return list(cursor.fetchall())

    def get_recent_health_checks(self, limit: int = 200) -> list[sqlite3.Row]:
        cursor = self._execute(
            "SELECT * FROM health_checks ORDER BY timestamp DESC LIMIT ?",
            [limit],
        )
        return list(cursor.fetchall())

    def clear_all(self) -> None:
        self._execute("DELETE FROM health_checks")
        self._execute("DELETE FROM failures")
        self._execute("DELETE FROM windows_events")
        self._execute("DELETE FROM meta_logs")


db = Database(Config.DB_PATH)
