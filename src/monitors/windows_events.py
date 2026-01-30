"""Windows Event Log scraping."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from typing import Any, Optional

from config import Config


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _result(success: bool, data: dict[str, Any], error: Optional[str], error_type: Optional[str]) -> dict[str, Any]:
    return {
        "success": success,
        "data": data,
        "error": error,
        "error_type": error_type,
        "timestamp": _utc_now(),
    }


def get_recent_system_events(timeout: int = Config.DEEP_TIMEOUT_SECONDS) -> dict[str, Any]:
    query = "*[System[(Level=1 or Level=2 or Level=3) and TimeCreated[timediff(@SystemTime) <= 300000]]]"
    result = _run(
        ["wevtutil", "qe", "System", "/q:" + query, "/f:text", "/c:50"],
        timeout,
    )
    if result.returncode == 0:
        return _result(True, {"system_events": result.stdout.strip()}, None, None)
    return _result(False, {}, result.stderr.strip(), "command_failed")
