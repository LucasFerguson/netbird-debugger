"""Configuration defaults for NetBird Sentinel."""

from __future__ import annotations

import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Config:
    BASE_DIR = Path(__file__).resolve().parents[1]
    DATA_DIR = os.getenv("NETBIRD_DATA_DIR", str(BASE_DIR / "data"))
    LOG_DIR = os.getenv("NETBIRD_LOG_DIR", str(BASE_DIR / "logs"))
    REPORTS_DIR = os.getenv("NETBIRD_REPORTS_DIR", str(BASE_DIR / "reports"))
    DB_PATH = os.getenv("NETBIRD_DB_PATH", str(Path(DATA_DIR) / "sentinel.db"))

    LOG_LEVEL = os.getenv("NETBIRD_LOG_LEVEL", "INFO").upper()
    LOG_RETENTION_DAYS = _env_int("NETBIRD_LOG_RETENTION_DAYS", 7)

    ROUTINE_CHECK_INTERVAL = _env_int("NETBIRD_ROUTINE_CHECK_INTERVAL", 1)
    ROUTINE_TIMEOUT_SECONDS = _env_int("NETBIRD_ROUTINE_TIMEOUT_SECONDS", 2)
    DEEP_TIMEOUT_SECONDS = _env_int("NETBIRD_DEEP_TIMEOUT_SECONDS", 30)

    AUTO_RESTART_ENABLED = os.getenv("NETBIRD_AUTO_RESTART_ENABLED", "true").lower() == "true"
    RESTART_WAIT_SECONDS = _env_int("NETBIRD_RESTART_WAIT_SECONDS", 10)
    RESTART_FAILURE_THRESHOLD = _env_int("NETBIRD_RESTART_FAILURE_THRESHOLD", 10)
    REPORT_INTERVAL_SECONDS = _env_int("NETBIRD_REPORT_INTERVAL_SECONDS", 120)

    SERVICES = [
        "gitea.netbird.cloud:3000",
        "pve4.netbird.cloud",
        "caddy.netbird.cloud",
    ]
    SERVICE_IPS = [
        "100.71.7.102:3000",  # gitea.netbird.cloud
        "100.71.244.136",  # caddy.netbird.cloud
    ]
