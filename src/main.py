"""NetBird Sentinel entry point."""

from __future__ import annotations

import time

from config import Config
from diagnostics.collector import assess_health, run_routine_checks, summarize_health_check
from logger.app_logger import logger
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
            time.sleep(Config.ROUTINE_CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("NetBird Sentinel stopped", extra={"component": "main"})


if __name__ == "__main__":
    main()
