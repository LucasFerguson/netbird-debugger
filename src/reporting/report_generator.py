"""Generate a summary report from collected diagnostics."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import subprocess
import socket

from config import Config
from diagnostics.collector import run_deep_checks
from recovery.netbird_restart import get_netbird_status
from storage.database import db


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_services_status(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _detect_issues(checks: list[dict[str, Any]]) -> list[str]:
    if not checks:
        return ["No health checks found yet."]

    internet_fail = 0
    dns_fail = 0
    process_down = 0
    all_services_down = 0
    hostname_up_ip_down = 0
    hostname_down_ip_up = 0

    for check in checks:
        if check.get("internet_reachable") is False:
            internet_fail += 1
        if check.get("dns_working") is False:
            dns_fail += 1
        if check.get("netbird_running") is False:
            process_down += 1

        services = _load_services_status(check.get("services_status"))
        if services:
            reachables = [v.get("reachable") for v in services.values() if isinstance(v, dict)]
            if reachables and not any(reachables):
                all_services_down += 1

            hostname_reach = []
            ip_reach = []
            for key, value in services.items():
                if not isinstance(value, dict):
                    continue
                if any(ch.isalpha() for ch in key):
                    hostname_reach.append(value.get("reachable"))
                else:
                    ip_reach.append(value.get("reachable"))
            if hostname_reach and ip_reach:
                if any(hostname_reach) and not any(ip_reach):
                    hostname_up_ip_down += 1
                if not any(hostname_reach) and any(ip_reach):
                    hostname_down_ip_up += 1

    issues: list[str] = []
    total = len(checks)
    if process_down:
        issues.append(f"NetBird process not running in {process_down}/{total} checks.")
    if internet_fail:
        issues.append(f"Internet connectivity failed in {internet_fail}/{total} checks.")
    if dns_fail:
        issues.append(f"DNS resolution failed in {dns_fail}/{total} checks.")
    if all_services_down:
        issues.append(f"All monitored services unreachable in {all_services_down}/{total} checks.")
    if hostname_down_ip_up:
        issues.append("Hostname services down while IP services up: likely DNS or hostname routing issue.")
    if hostname_up_ip_down:
        issues.append("Hostname services up while IP services down: possible DNS override or IP routing issue.")

    if not issues:
        issues.append("No obvious failures detected in recent checks.")
    return issues


def _summarize_services(checks: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, Counter] = {}
    for check in checks:
        services = _load_services_status(check.get("services_status"))
        for name, info in services.items():
            if not isinstance(info, dict):
                continue
            counts.setdefault(name, Counter())
            counts[name]["reachable"] += 1 if info.get("reachable") else 0
            counts[name]["unreachable"] += 0 if info.get("reachable") else 1
            if "tcp_reachable" in info:
                counts[name]["tcp_samples"] += 1
            if info.get("tcp_reachable") is True:
                counts[name]["tcp_ok"] += 1
            if info.get("tcp_reachable") is False:
                counts[name]["tcp_fail"] += 1
            if "http_reachable" in info:
                counts[name]["http_samples"] += 1
            if info.get("http_reachable") is True:
                counts[name]["http_ok"] += 1
            if info.get("http_reachable") is False:
                counts[name]["http_fail"] += 1
    return {k: dict(v) for k, v in counts.items()}


def _summarize_stack(checks: list[dict[str, Any]]) -> list[str]:
    if not checks:
        return ["No health checks available for stack analysis."]

    tcp_fail_total = 0
    http_fail_total = 0
    service_points = 0

    for check in checks:
        services = _load_services_status(check.get("services_status"))
        for info in services.values():
            if not isinstance(info, dict):
                continue
            service_points += 1
            if info.get("tcp_reachable") is False:
                tcp_fail_total += 1
            if info.get("http_reachable") is False:
                http_fail_total += 1

    lines = []
    if service_points:
        lines.append(f"Service probes: {service_points}")
        lines.append(f"TCP failures: {tcp_fail_total}/{service_points}")
        lines.append(f"HTTP failures: {http_fail_total}/{service_points}")
    return lines


def _parse_quantum_status(status_text: str) -> dict[str, Any]:
    quantum = None
    peers = None
    for line in status_text.splitlines():
        if line.lower().startswith("quantum resistance:"):
            quantum = line.split(":", 1)[1].strip().lower() == "true"
        if line.lower().startswith("peers count:"):
            peers = line.split(":", 1)[1].strip()
    return {"quantum_resistance": quantum, "peers_count": peers}


def _run_cmd(command: list[str], timeout: int = 10) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {"success": False, "stdout": "", "stderr": str(exc), "returncode": None}


def _resolve_services(services: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for entry in services:
        host = entry.split(":")[0]
        try:
            ip = socket.gethostbyname(host)
            results[host] = {"resolved": True, "ip": ip}
        except Exception as exc:
            results[host] = {"resolved": False, "error": str(exc)}
    return results


def generate_report() -> Path:
    db.initialize()
    checks = [dict(r) for r in db.get_recent_health_checks()]
    failures = [dict(r) for r in db.get_recent_failures()]

    issues = _detect_issues(checks)
    services_summary = _summarize_services(checks)
    stack_summary = _summarize_stack(checks)

    deep: dict[str, Any] = {}
    if failures:
        latest = failures[0]
        try:
            diagnostics = json.loads(latest.get("diagnostics") or "{}")
            deep = diagnostics.get("deep", {}) if isinstance(diagnostics, dict) else {}
        except Exception:
            deep = {}
    if not deep:
        deep = run_deep_checks()

    report_lines = []
    report_lines.append("NetBird Sentinel Report")
    report_lines.append(f"Generated: {_utc_now()}")
    report_lines.append("")
    report_lines.append(f"Health checks captured: {len(checks)}")
    report_lines.append(f"Failures captured: {len(failures)}")
    report_lines.append("")
    report_lines.append("Likely Issues")
    for item in issues:
        report_lines.append(f"- {item}")
    report_lines.append("")

    status = get_netbird_status()
    quantum_info = _parse_quantum_status(status.get("stdout", ""))
    if quantum_info.get("quantum_resistance") is True and "All monitored services unreachable" in " ".join(issues):
        report_lines.append("Likely Root Cause")
        report_lines.append(
            "- Quantum resistance is enabled; peers that do not support it may fail to connect to the data plane."
        )
        if quantum_info.get("peers_count"):
            report_lines.append(f"- Peers count: {quantum_info.get('peers_count')}")
        report_lines.append("")
    report_lines.append("Service Reachability Summary")
    for name, summary in services_summary.items():
        report_lines.append(f"- {name}: {summary}")
    report_lines.append("")
    report_lines.append("Network Stack Summary")
    for line in stack_summary:
        report_lines.append(f"- {line}")
    report_lines.append("")
    report_lines.append("Raw Attachments")

    report_dir = Path(Config.REPORTS_DIR)
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = f"report-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.txt"
    path = report_dir / filename

    def write_raw(suffix: str, content: str) -> Path:
        attachment = report_dir / f"{path.stem}-{suffix}"
        attachment.write_text(content or "EMPTY", encoding="utf-8")
        report_lines.append(f"- {attachment.name}")
        return attachment

    if deep:
        adapters = deep.get("network_adapters", {}).get("data", {}).get("adapters_json", "")
        dns_servers = deep.get("dns_servers", {}).get("data", {}).get("dns_servers_json", "")
        routing_table = deep.get("routing_table", {}).get("data", {}).get("routing_table", "")
        netstat = deep.get("active_connections", {}).get("data", {}).get("netstat", "")
        system_events = deep.get("windows_events", {}).get("data", {}).get("system_events", "")

        write_raw("adapters.json", adapters)
        write_raw("dns_servers.json", dns_servers)
        write_raw("routing_table.txt", routing_table)
        write_raw("netstat.txt", netstat)
        write_raw("windows_events.txt", system_events)
    else:
        report_lines.append("- No deep diagnostics available.")

    write_raw(
        "netbird_status.txt",
        status.get("stdout", "") + ("\n" + status.get("stderr", "") if status.get("stderr") else ""),
    )

    status_json = _run_cmd(["netbird", "status", "--json"])
    write_raw(
        "netbird_status.json",
        status_json.get("stdout", "") + ("\n" + status_json.get("stderr", "") if status_json.get("stderr") else ""),
    )

    routes_list = _run_cmd(["netbird", "routes", "list"])
    write_raw(
        "netbird_routes_list.txt",
        routes_list.get("stdout", "") + ("\n" + routes_list.get("stderr", "") if routes_list.get("stderr") else ""),
    )

    dns_map = _resolve_services(Config.SERVICES)
    write_raw("dns_resolution.json", json.dumps(dns_map, indent=2))

    report_lines.append("")

    if failures:
        latest = failures[0]
        report_lines.append("Latest Failure Snapshot")
        report_lines.append(f"- timestamp: {latest.get('timestamp')}")
        report_lines.append(f"- failure_type: {latest.get('failure_type')}")
        report_lines.append(f"- severity: {latest.get('severity')}")
        report_lines.append(f"- restart_successful: {latest.get('restart_successful')}")
        notes = latest.get("notes")
        if notes:
            report_lines.append("- notes:")
            report_lines.append(notes)

    path.write_text("\n".join(report_lines), encoding="utf-8")
    return path
