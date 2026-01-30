"""Deep network diagnostics."""

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


def get_network_adapters(timeout: int = Config.DEEP_TIMEOUT_SECONDS) -> dict[str, Any]:
    result = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-NetAdapter | ConvertTo-Json -Depth 3"],
        timeout,
    )
    if result.returncode == 0:
        return _result(True, {"adapters_json": result.stdout.strip()}, None, None)
    return _result(False, {}, result.stderr.strip(), "command_failed")


def get_routing_table(timeout: int = Config.DEEP_TIMEOUT_SECONDS) -> dict[str, Any]:
    result = _run(["route", "print"], timeout)
    if result.returncode == 0:
        return _result(True, {"routing_table": result.stdout.strip()}, None, None)
    return _result(False, {}, result.stderr.strip(), "command_failed")


def get_dns_servers(timeout: int = Config.DEEP_TIMEOUT_SECONDS) -> dict[str, Any]:
    result = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-DnsClientServerAddress | ConvertTo-Json -Depth 3"],
        timeout,
    )
    if result.returncode == 0:
        return _result(True, {"dns_servers_json": result.stdout.strip()}, None, None)
    return _result(False, {}, result.stderr.strip(), "command_failed")


def get_active_connections(timeout: int = Config.DEEP_TIMEOUT_SECONDS) -> dict[str, Any]:
    result = _run(["netstat", "-ano"], timeout)
    if result.returncode == 0:
        return _result(True, {"netstat": result.stdout.strip()}, None, None)
    return _result(False, {}, result.stderr.strip(), "command_failed")
