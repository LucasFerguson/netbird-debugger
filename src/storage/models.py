"""SQLite schema definitions."""

HEALTH_CHECKS_TABLE = """
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    check_type TEXT NOT NULL,

    netbird_running BOOLEAN,
    netbird_pid INTEGER,
    netbird_uptime_seconds INTEGER,
    netbird_cpu_percent REAL,
    netbird_memory_mb REAL,

    internet_reachable BOOLEAN,
    dns_working BOOLEAN,
    services_status TEXT,

    system_healthy BOOLEAN,

    check_duration_ms INTEGER
);
"""

FAILURES_TABLE = """
CREATE TABLE IF NOT EXISTS failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,

    failure_type TEXT NOT NULL,
    severity TEXT,

    diagnostics TEXT NOT NULL,

    auto_restart_attempted BOOLEAN,
    restart_successful BOOLEAN,
    recovery_timestamp TEXT,

    notes TEXT
);
"""

WINDOWS_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS windows_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_timestamp TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    event_id INTEGER,
    source TEXT,
    level TEXT,
    message TEXT,

    related_failure_id INTEGER,
    FOREIGN KEY (related_failure_id) REFERENCES failures(id)
);
"""

META_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS meta_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT,
    component TEXT,
    message TEXT,
    details TEXT,
    check_name TEXT,
    error_type TEXT
);
"""


def schema_statements() -> list[str]:
    return [
        HEALTH_CHECKS_TABLE,
        FAILURES_TABLE,
        WINDOWS_EVENTS_TABLE,
        META_LOGS_TABLE,
    ]
