"""Basic network connectivity checks."""

from __future__ import annotations

import socket
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from requests.exceptions import SSLError

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


def check_internet(host: str = "8.8.8.8", port: int = 53, timeout: int = Config.ROUTINE_TIMEOUT_SECONDS) -> dict[str, Any]:
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


def check_dns(domain: str = "google.com", timeout: int = Config.ROUTINE_TIMEOUT_SECONDS) -> dict[str, Any]:
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


def _parse_service(service: str) -> dict[str, Any]:
    url = _service_url(service)
    parsed = urlparse(url)
    host = parsed.hostname or service
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return {"service": service, "url": url, "host": host, "port": port}


def check_services(
    services: Optional[list[str]] = None,
    timeout: int = Config.ROUTINE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    combined = services or (Config.SERVICES + Config.SERVICE_IPS)
    for service in combined:
        parsed = _parse_service(service)
        url = parsed["url"]
        host = parsed["host"]
        port = parsed["port"]

        tcp_start = time.monotonic()
        tcp_reachable = False
        tcp_latency_ms = None
        tcp_error = None
        try:
            socket.create_connection((host, port), timeout=timeout).close()
            tcp_reachable = True
            tcp_latency_ms = int((time.monotonic() - tcp_start) * 1000)
        except Exception as exc:
            tcp_error = str(exc)

        http_reachable = None
        status_code = None
        http_latency_ms = None
        http_error = None

        try:
            if tcp_reachable:
                http_start = time.monotonic()
                response = requests.get(url, timeout=timeout)
                http_latency_ms = int((time.monotonic() - http_start) * 1000)
                http_reachable = response.ok
                status_code = response.status_code
            else:
                http_reachable = False
                http_error = "tcp_failed"
        except SSLError as exc:
            http_reachable = False
            http_error = f"tls_untrusted: {exc}"
        except Exception as exc:
            http_reachable = False
            http_error = str(exc)

        reachable = tcp_reachable if http_reachable is False and http_error and http_error.startswith("tls_untrusted") else (
            http_reachable if http_reachable is not None else tcp_reachable
        )
        results[service] = {
            "reachable": reachable,
            "tcp_reachable": tcp_reachable,
            "tcp_latency_ms": tcp_latency_ms,
            "tcp_error": tcp_error,
            "http_reachable": http_reachable,
            "status_code": status_code,
            "latency_ms": http_latency_ms,
            "error": http_error,
            "url": url,
            "host": host,
            "port": port,
        }
    return _result(True, {"services": results}, None, None)
