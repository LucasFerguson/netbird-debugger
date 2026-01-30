"""Orchestrate routine diagnostic checks."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from monitors.deep_network import (
    get_active_connections,
    get_dns_servers,
    get_network_adapters,
    get_routing_table,
)
from monitors.network_monitor import check_dns, check_internet, check_services
from monitors.process_monitor import check_netbird_running
from monitors.windows_events import get_recent_system_events


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_routine_checks() -> dict[str, Any]:
    start = time.monotonic()
    process = check_netbird_running()
    internet = check_internet()
    dns = check_dns()
    services = check_services()

    data = {
        "timestamp": _utc_now(),
        "check_type": "routine",
        "process": process,
        "internet": internet,
        "dns": dns,
        "services": services,
        "check_duration_ms": int((time.monotonic() - start) * 1000),
    }
    return data


def summarize_health_check(results: dict[str, Any], status: str) -> dict[str, Any]:
    process = results.get("process", {}).get("data", {})
    internet = results.get("internet", {}).get("data", {})
    dns = results.get("dns", {}).get("data", {})
    services = results.get("services", {}).get("data", {}).get("services", {})

    return {
        "timestamp": results.get("timestamp", _utc_now()),
        "check_type": results.get("check_type", "routine"),
        "netbird_running": process.get("running"),
        "netbird_pid": process.get("pid"),
        "netbird_uptime_seconds": process.get("uptime_seconds"),
        "netbird_cpu_percent": process.get("cpu_percent"),
        "netbird_memory_mb": process.get("memory_mb"),
        "internet_reachable": internet.get("internet_reachable"),
        "dns_working": dns.get("dns_working"),
        "services_status": services,
        "system_healthy": status == "healthy",
        "check_duration_ms": results.get("check_duration_ms"),
    }


def assess_health(results: dict[str, Any]) -> str:
    process = results.get("process", {}).get("data", {})
    services = results.get("services", {}).get("data", {}).get("services", {})

    netbird_running = process.get("running") is True
    reachable = [svc.get("reachable") for svc in services.values()]
    any_services = any(reachable) if reachable else False
    all_services = all(reachable) if reachable else False

    if not netbird_running or (netbird_running and not any_services):
        return "failed"
    if netbird_running and not all_services:
        return "degraded"
    return "healthy"


def run_deep_checks() -> dict[str, Any]:
    return {
        "timestamp": _utc_now(),
        "network_adapters": get_network_adapters(),
        "routing_table": get_routing_table(),
        "dns_servers": get_dns_servers(),
        "active_connections": get_active_connections(),
        "windows_events": get_recent_system_events(),
    }
