"""Basic network connectivity checks."""

from __future__ import annotations

import socket
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from config import Config


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result(success: bool, data: dict[str, Any], error: Optional[str], error_type: Optional[str]) -> dict[str, Any]:
    return {
        "success": success,
        "data": data,
        "error": error,
        "error_type": error_type,
        "timestamp": _utc_now(),
    }


def check_internet(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> dict[str, Any]:
    start = time.monotonic()
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        latency_ms = int((time.monotonic() - start) * 1000)
        return _result(True, {"internet_reachable": True, "latency_ms": latency_ms}, None, None)
    except Exception as exc:
        return _result(
            True,
            {"internet_reachable": False, "latency_ms": None},
            str(exc),
            "connection_failed",
        )


def check_dns(domain: str = "google.com", timeout: int = 3) -> dict[str, Any]:
    start = time.monotonic()
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(domain)
        latency_ms = int((time.monotonic() - start) * 1000)
        return _result(True, {"dns_working": True, "latency_ms": latency_ms}, None, None)
    except Exception as exc:
        return _result(
            True,
            {"dns_working": False, "latency_ms": None},
            str(exc),
            "dns_failed",
        )


def _service_url(service: str) -> str:
    if "://" in service:
        return service
    if ":" in service:
        return f"http://{service}"
    return f"http://{service}"


def check_services(services: Optional[list[str]] = None, timeout: int = 5) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for service in services or Config.SERVICES:
        url = _service_url(service)
        start = time.monotonic()
        try:
            response = requests.get(url, timeout=timeout)
            latency_ms = int((time.monotonic() - start) * 1000)
            results[service] = {
                "reachable": response.ok,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "error": None,
            }
        except Exception as exc:
            results[service] = {
                "reachable": False,
                "status_code": None,
                "latency_ms": None,
                "error": str(exc),
            }
    return _result(True, {"services": results}, None, None)
