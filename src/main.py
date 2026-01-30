"""NetBird Sentinel entry point."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from config import Config
from diagnostics.collector import (
    assess_health,
    run_deep_checks,
    run_routine_checks,
    summarize_health_check,
)
from logger.app_logger import logger
from reporting.report_generator import generate_report
from recovery.netbird_restart import get_netbird_status, restart_netbird_service
from storage.database import db


def main() -> None:
    logger.info("NetBird Sentinel started", extra={"component": "main"})
    db.initialize()
    failed_count = 0
    start_time = time.monotonic()
    report_generated = False

    try:
        while True:
            results = run_routine_checks()
            status = assess_health(results)
            record = summarize_health_check(results, status)
            db.log_health_check(record)

            logger.info(
                "Status: %s (duration_ms=%s)",
                status,
                results.get("check_duration_ms"),
                extra={"component": "main"},
            )

            services = results.get("services", {}).get("data", {}).get("services", {})
            if services:
                for name, info in services.items():
                    tcp_ok = info.get("tcp_reachable") is True
                    http_ok = info.get("http_reachable") is True
                    tcp_tag = "OK" if tcp_ok else "FAIL"
                    http_tag = "OK" if http_ok else "FAIL"
                    tcp_latency = info.get("tcp_latency_ms")
                    http_latency = info.get("latency_ms")
                    tcp_err = info.get("tcp_error")
                    http_err = info.get("error")
                    logger.info(
                        "Service %s | TCP=%s (%sms) HTTP=%s (%sms) tcp_err=%s http_err=%s",
                        name,
                        tcp_tag,
                        tcp_latency if tcp_latency is not None else "-",
                        http_tag,
                        http_latency if http_latency is not None else "-",
                        tcp_err or "-",
                        http_err or "-",
                        extra={"component": "main"},
                    )
            if status == "failed":
                failed_count += 1
                logger.warning(
                    "Consecutive failed checks: %s/%s",
                    failed_count,
                    Config.RESTART_FAILURE_THRESHOLD,
                    extra={"component": "main"},
                )
            else:
                failed_count = 0

            if status == "failed" and failed_count >= Config.RESTART_FAILURE_THRESHOLD:
                deep_results = run_deep_checks()
                failure_id = db.log_failure(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "failure_type": "auto_detected",
                        "severity": "critical",
                        "diagnostics": {"routine": results, "deep": deep_results},
                        "auto_restart_attempted": Config.AUTO_RESTART_ENABLED,
                    }
                )

                if Config.AUTO_RESTART_ENABLED:
                    logger.warning("Attempting NetBird restart", extra={"component": "main"})
                    restart_result = restart_netbird_service()
                    logger.warning(
                        "Restart result: %s",
                        restart_result,
                        extra={"component": "main", "details": restart_result},
                    )

                    status_result = get_netbird_status()
                    logger.info(
                        "NetBird status after restart: %s",
                        status_result,
                        extra={"component": "main", "details": status_result},
                    )
                    db.update_failure(
                        failure_id,
                        {
                            "restart_successful": restart_result.get("success"),
                            "recovery_timestamp": datetime.now(timezone.utc).isoformat(),
                            "notes": restart_result.get("stderr") or restart_result.get("stdout"),
                        },
                    )
                    time.sleep(Config.RESTART_WAIT_SECONDS)
                else:
                    logger.info("Auto-restart disabled", extra={"component": "main"})

                failed_count = 0

            if not report_generated and (time.monotonic() - start_time) >= Config.REPORT_INTERVAL_SECONDS:
                report_path = generate_report()
                logger.info(
                    "Report generated at %s",
                    report_path,
                    extra={"component": "main"},
                )
                report_generated = True
            time.sleep(Config.ROUTINE_CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("NetBird Sentinel stopped", extra={"component": "main"})


if __name__ == "__main__":
    main()
