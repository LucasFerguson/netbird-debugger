"""NetBird Sentinel entry point."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from config import Config
from diagnostics.collector import assess_health, run_routine_checks, summarize_health_check
from logger.app_logger import logger
from recovery.netbird_restart import get_netbird_status, restart_netbird_service
from storage.database import db


def main() -> None:
    logger.info("NetBird Sentinel started", extra={"component": "main"})
    db.initialize()

    try:
        while True:
            results = run_routine_checks()
            status = assess_health(results)
            record = summarize_health_check(results, status)
            db.log_health_check(record)

            logger.info("Status: %s", status, extra={"component": "main"})
            if status == "failed":
                failure_id = db.log_failure(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "failure_type": "auto_detected",
                        "severity": "critical",
                        "diagnostics": results,
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
            time.sleep(Config.ROUTINE_CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("NetBird Sentinel stopped", extra={"component": "main"})


if __name__ == "__main__":
    main()
