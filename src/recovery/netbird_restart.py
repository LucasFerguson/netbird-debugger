"""NetBird service restart logic (Windows)."""

from __future__ import annotations

import subprocess
from typing import Any


def _run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def get_netbird_status() -> dict[str, Any]:
    """Return output from the NetBird CLI status command."""
    result = _run(["netbird", "status"])
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "returncode": result.returncode,
    }


def restart_netbird_service() -> dict[str, Any]:
    """Attempt to restart the NetBird Windows service."""
    # Prefer PowerShell Restart-Service for simplicity.
    ps = _run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Restart-Service -Name netbird -ErrorAction Stop",
        ]
    )
    if ps.returncode == 0:
        return {
            "success": True,
            "error": None,
            "stdout": ps.stdout.strip(),
            "stderr": ps.stderr.strip(),
            "method": "powershell_restart_service",
        }

    # Fallback to net stop/start.
    stop = _run(["net", "stop", "netbird"])
    start = _run(["net", "start", "netbird"])
    if stop.returncode == 0 and start.returncode == 0:
        return {
            "success": True,
            "error": None,
            "stdout": (stop.stdout + start.stdout).strip(),
            "stderr": (stop.stderr + start.stderr).strip(),
            "method": "net_stop_start",
        }

    return {
        "success": False,
        "error": "restart_failed",
        "stdout": (ps.stdout + stop.stdout + start.stdout).strip(),
        "stderr": (ps.stderr + stop.stderr + start.stderr).strip(),
        "method": "failed",
    }
