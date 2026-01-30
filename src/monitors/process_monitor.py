"""Process-level checks for NetBird."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

import psutil


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_netbird_running(process_name: str = "netbird") -> dict[str, Any]:
    """Return status information for the NetBird process."""
    start = time.monotonic()
    try:
        for proc in psutil.process_iter(["pid", "name", "create_time", "memory_info", "cpu_percent", "num_threads"]):
            name = (proc.info.get("name") or "").lower()
            if process_name.lower() in name:
                uptime_seconds = int(time.time() - float(proc.info.get("create_time") or time.time()))
                cpu_percent = proc.cpu_percent(interval=0.1)
                memory_info = proc.info.get("memory_info")
                memory_mb = round(memory_info.rss / (1024 * 1024), 2) if memory_info else None
                data = {
                    "running": True,
                    "pid": proc.info.get("pid"),
                    "uptime_seconds": uptime_seconds,
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "threads": proc.info.get("num_threads"),
                    "check_duration_ms": int((time.monotonic() - start) * 1000),
                }
                return {"success": True, "data": data, "error": None, "error_type": None, "timestamp": _utc_now()}

        data = {
            "running": False,
            "pid": None,
            "uptime_seconds": None,
            "cpu_percent": None,
            "memory_mb": None,
            "threads": None,
            "check_duration_ms": int((time.monotonic() - start) * 1000),
        }
        return {"success": True, "data": data, "error": None, "error_type": None, "timestamp": _utc_now()}
    except Exception as exc:
        return {
            "success": False,
            "data": {},
            "error": str(exc),
            "error_type": "exception",
            "timestamp": _utc_now(),
        }
