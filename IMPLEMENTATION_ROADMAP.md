# NetBird Sentinel - Implementation Roadmap

## Overview
This document breaks down the NetBird Sentinel project into manageable stages. Each stage builds upon the previous, with clear deliverables and validation criteria.

---

## Stage 0: Project Setup (1-2 hours)

### Tasks
- [ ] Initialize Git repository
- [ ] Create project directory structure
- [ ] Set up Python virtual environment with `uv`
- [ ] Install core dependencies
- [ ] Create `requirements.txt`
- [ ] Write basic `README.md` with setup instructions

### Deliverables
- Working Python environment
- Project skeleton with all folders created
- Dependencies installed and importable

### Validation
```bash
# Can import all dependencies without errors
python -c "import psutil, sqlite3, requests"
```

---

## Stage 1: Core Infrastructure (3-4 hours)

### 1.1 Application Logger
- [ ] Create `logger/app_logger.py` with custom logger
- [ ] Configure logging to console (color-coded by level)
- [ ] Configure logging to rotating file (`logs/sentinel-YYYY-MM-DD.log`)
- [ ] Configure logging to SQLite `meta_logs` table
- [ ] Add contextual logging helpers (log with component name)

**Validation:**
```python
from logger.app_logger import logger
logger.info("Test message")
logger.error("Test error", extra={"component": "test", "details": {"foo": "bar"}})
# Should appear in console, log file, and database
```

### 1.2 Database Layer
- [ ] Create `storage/database.py` with SQLite connection manager
- [ ] Define schema in `storage/models.py`
- [ ] Create initialization function (creates tables if not exist)
- [ ] Write helper functions for common queries
  - `log_health_check(data)`
  - `log_failure(data)`
  - `log_windows_event(data)`
  - `get_recent_failures(limit=10)`

**Validation:**
```python
from storage.database import db
db.initialize()
db.log_health_check({...})  # Should insert successfully
recent = db.get_recent_failures()  # Should return list
```

### 1.3 Configuration
- [ ] Create `config.py` with all configurable values
  - Check intervals (routine: 60s, deep: on-demand)
  - Services to monitor (gitea, pve4, caddy)
  - Timeout values
  - Log retention settings
- [ ] Use environment variables for sensitive config (if any)
- [ ] Provide sensible defaults

**Validation:**
```python
from config import Config
assert Config.ROUTINE_CHECK_INTERVAL == 60
assert "gitea.netbird.cloud" in Config.SERVICES
```

---

## Stage 2: Basic Monitoring (4-6 hours)

### 2.1 Process Monitor
- [ ] Create `monitors/process_monitor.py`
- [ ] Implement `check_netbird_running()` → returns ProcessInfo dict
  - Use `psutil` to find NetBird process
  - Get PID, uptime, CPU%, memory
- [ ] Handle case when NetBird not running (return structured error)
- [ ] Add timeout (5s)
- [ ] Validate output schema

**Output schema:**
```python
{
    "success": True,
    "data": {
        "running": True,
        "pid": 12345,
        "uptime_seconds": 3600,
        "cpu_percent": 2.3,
        "memory_mb": 145.2,
        "threads": 8
    },
    "timestamp": "2026-01-29T14:23:45.123Z"
}
```

### 2.2 Network Monitor (Basic)
- [ ] Create `monitors/network_monitor.py`
- [ ] Implement `check_internet()` → ping 8.8.8.8
- [ ] Implement `check_dns()` → resolve google.com
- [ ] Implement `check_services()` → HTTP check for each configured service
  - Use `requests.get()` with timeout
  - Return dict of {service_name: {reachable, error, latency_ms}}
- [ ] Handle timeouts and exceptions gracefully

**Output schema:**
```python
{
    "success": True,
    "data": {
        "internet_reachable": True,
        "dns_working": True,
        "services": {
            "gitea.netbird.cloud:3000": {"reachable": True, "latency_ms": 45, "error": None},
            "pve4.netbird.cloud": {"reachable": False, "latency_ms": None, "error": "timeout"},
            "caddy.netbird.cloud": {"reachable": True, "latency_ms": 32, "error": None}
        }
    },
    "timestamp": "2026-01-29T14:23:45.123Z"
}
```

### 2.3 Diagnostic Collector
- [ ] Create `diagnostics/collector.py`
- [ ] Implement `run_routine_checks()` → orchestrates all basic monitors
  - Calls process_monitor, network_monitor
  - Collects results into single health check dict
  - Handles if individual checks fail/timeout
  - Returns complete picture of system health
- [ ] Add `assess_health()` → determines if system is healthy/degraded/failed
  - Logic: Red if process dead OR (process alive AND no services reachable)
  - Yellow if some but not all services reachable
  - Green if all good

**Validation:**
```python
from diagnostics.collector import run_routine_checks, assess_health
results = run_routine_checks()
status = assess_health(results)  # Returns 'healthy', 'degraded', or 'failed'
```

---

## Stage 3: Monitoring Loop & Storage (3-4 hours)

### 3.1 Main Loop
- [ ] Create `main.py` with monitoring loop
- [ ] Run routine checks every 60 seconds
- [ ] Store results to `health_checks` table
- [ ] Print status to console (can be removed later)
- [ ] Handle KeyboardInterrupt gracefully

**Minimal main.py:**
```python
import time
from diagnostics.collector import run_routine_checks, assess_health
from storage.database import db
from logger.app_logger import logger

def main():
    logger.info("NetBird Sentinel started")
    db.initialize()
    
    while True:
        results = run_routine_checks()
        status = assess_health(results)
        db.log_health_check({**results, "status": status})
        
        logger.info(f"Status: {status}")
        time.sleep(60)

if __name__ == "__main__":
    main()
```

### 3.2 Data Validation
- [ ] Create `diagnostics/schemas.py` with expected schemas
- [ ] Create `diagnostics/validator.py` with validation functions
- [ ] Validate each monitor's output against schema
- [ ] Log to `meta_logs` when validation fails

**Example:**
```python
from diagnostics.schemas import PROCESS_SCHEMA
from diagnostics.validator import validate

result = check_netbird_running()
is_valid = validate(result["data"], PROCESS_SCHEMA)
if not is_valid:
    logger.error("Process check output invalid", extra={
        "check_name": "process_monitor.check_netbird_running",
        "error_type": "validation_failed"
    })
```

---

## Stage 4: Auto-Recovery (2-3 hours)

### 4.1 NetBird Restart Logic
- [ ] Create `recovery/netbird_restart.py`
- [ ] Implement `restart_netbird_service()` for Windows
  - Use PowerShell: `Restart-Service netbird` (requires admin)
  - OR: `net stop netbird && net start netbird`
- [ ] Handle errors (permission denied, service not found)
- [ ] Return success/failure status
- [ ] Log restart attempts to database

### 4.2 Integrate Recovery into Main Loop
- [ ] Modify main loop to trigger restart when status = 'failed'
- [ ] Log failure to `failures` table BEFORE restart attempt
- [ ] Wait for NetBird to come back up (poll process for 30s)
- [ ] Update failure record with restart success/failure

**Updated main.py logic:**
```python
if status == "failed":
    # Log the failure with basic diagnostics
    failure_id = db.log_failure({
        "failure_type": "auto_detected",
        "diagnostics": results,
        "auto_restart_attempted": True
    })
    
    # Attempt restart
    restart_success = restart_netbird_service()
    
    # Update failure record
    db.update_failure(failure_id, {
        "restart_successful": restart_success,
        "recovery_timestamp": datetime.now().isoformat()
    })
```

---

## Stage 5: Deep Diagnostics (4-6 hours)

### 5.1 Deep Network Diagnostics
- [ ] Create `monitors/deep_network.py`
- [ ] Implement `get_network_adapters()` → PowerShell `Get-NetAdapter`
- [ ] Implement `get_routing_table()` → `route print` or PowerShell
- [ ] Implement `get_dns_servers()` → `ipconfig /all` parsing
- [ ] Implement `get_active_connections()` → `netstat -ano` or equivalent
- [ ] Each function should have 30s timeout
- [ ] Validate outputs and log if parsing fails

### 5.2 Windows Event Log Scraping
- [ ] Create `monitors/windows_events.py`
- [ ] Use `pywin32` to query Windows Event Log
- [ ] Get last 5 minutes of events from:
  - System log (filter: network-related sources)
  - Application log (filter: NetBird if available)
- [ ] Parse events into structured format
- [ ] Store in `windows_events` table

**Example query:**
```python
# Pseudo-code
events = get_events(
    log_name="System",
    time_range=last_5_minutes,
    sources=["Tcpip", "NetBT", "NDIS", "Wlansvc"]
)
```

### 5.3 Trigger Deep Diagnostics
- [ ] Modify `diagnostics/collector.py` to add `run_deep_checks()`
- [ ] Call deep checks only when failure detected
- [ ] Merge deep diagnostic results into failure record

**Updated failure logging:**
```python
if status == "failed":
    # Run deep diagnostics
    deep_results = run_deep_checks()
    
    # Combine basic + deep diagnostics
    full_diagnostics = {**results, **deep_results}
    
    failure_id = db.log_failure({
        "failure_type": "auto_detected",
        "diagnostics": full_diagnostics,
        "auto_restart_attempted": True
    })
```

---

## Stage 6: System Tray UI (3-4 hours)

### 6.1 Basic Tray Icon
- [ ] Create `ui/tray_icon.py`
- [ ] Initialize `pystray` system tray icon
- [ ] Create 3 icon states (green, yellow, red) using Pillow
- [ ] Display icon with initial status
- [ ] Add quit option to menu

**Basic tray setup:**
```python
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

def create_icon(color):
    # Create simple colored circle
    image = Image.new('RGB', (64, 64), color)
    draw = ImageDraw.Draw(image)
    draw.ellipse([10, 10, 54, 54], fill=color)
    return image

icon = Icon(
    "netbird-sentinel",
    create_icon("green"),
    menu=Menu(MenuItem("Quit", on_quit))
)
icon.run()
```

### 6.2 Dynamic Status Updates
- [ ] Run monitoring loop in separate thread
- [ ] Update tray icon color based on current status
- [ ] Add tooltip showing current status text

### 6.3 Enhanced Menu
- [ ] "View Status" → Print recent health check to console window
- [ ] "Force Check Now" → Trigger immediate deep diagnostic
- [ ] "Restart NetBird" → Manual restart button
- [ ] "View Recent Failures" → Print last 10 failures from DB
- [ ] "Open Logs Folder" → Open file explorer to logs directory

---

## Stage 7: Polish & Documentation (2-3 hours)

### 7.1 Error Handling Review
- [ ] Audit all monitor functions for error handling
- [ ] Ensure all exceptions are caught and logged
- [ ] Add retry logic where appropriate (e.g., transient network errors)
- [ ] Test with NetBird intentionally stopped

### 7.2 Documentation
- [ ] Update README.md with:
  - Installation instructions
  - Usage guide
  - Configuration options
  - Troubleshooting common issues
- [ ] Add docstrings to all public functions
- [ ] Create example queries for SQLite data analysis

**Example queries to include:**
```sql
-- Find most common failure types
SELECT failure_type, COUNT(*) as count
FROM failures
GROUP BY failure_type
ORDER BY count DESC;

-- Failures by hour of day
SELECT strftime('%H', timestamp) as hour, COUNT(*) as failures
FROM failures
GROUP BY hour
ORDER BY hour;

-- Average time between failures
SELECT AVG(time_diff) as avg_hours_between_failures
FROM (
    SELECT (julianday(timestamp) - julianday(LAG(timestamp) OVER (ORDER BY timestamp))) * 24 as time_diff
    FROM failures
);
```

### 7.3 Testing
- [ ] Test on clean Windows system
- [ ] Test with NetBird not installed (should handle gracefully)
- [ ] Test with NetBird stopped (should restart it)
- [ ] Test with network disconnected
- [ ] Verify all data is being logged correctly

---

## Stage 8: Initial Data Collection (1-2 weeks)

### 8.1 Production Run
- [ ] Deploy tool on primary Windows laptop
- [ ] Let it run for 1-2 weeks
- [ ] Collect real failure data
- [ ] Do NOT build issue generator yet

### 8.2 Data Analysis
- [ ] Export failure data from SQLite
- [ ] Identify patterns manually:
  - Time-based patterns
  - Event correlation
  - Common failure types
- [ ] Document findings in notes
- [ ] Determine what data is most valuable for GitHub issues

### 8.3 Refinement
- [ ] Based on collected data, adjust:
  - Check intervals (maybe too frequent/infrequent?)
  - Deep diagnostic triggers
  - What diagnostics to collect (missing useful data?)
- [ ] Add any missing diagnostics discovered during analysis

---

## Future Stages (Beyond MVP)

### Stage 9: Pattern Detection
- [ ] Build analysis scripts to detect patterns
- [ ] Correlate failures with Windows events
- [ ] Identify temporal patterns (time of day, day of week)
- [ ] Generate summary reports

### Stage 10: GitHub Issue Generator
- [ ] Create issue template based on learned patterns
- [ ] Build script to convert failure records to markdown
- [ ] Include relevant diagnostics automatically
- [ ] Filter out noise (e.g., don't include successful checks)

### Stage 11: Framework Generalization
- [ ] Extract monitoring patterns into reusable framework
- [ ] Create plugin architecture
- [ ] Document how to add new software monitors
- [ ] Build example monitors for other tools

---

## Development Tips

### Running During Development
```bash
# Run with verbose logging
python main.py --verbose

# Run with dry-run mode (don't actually restart NetBird)
python main.py --dry-run

# Run single check and exit (for testing)
python main.py --check-once
```

### Debugging Database
```bash
# Open SQLite database
sqlite3 data/sentinel.db

# View recent checks
SELECT * FROM health_checks ORDER BY timestamp DESC LIMIT 10;

# View all failures
SELECT timestamp, failure_type, auto_restart_attempted FROM failures;
```

### Quick Validation Between Stages
After each stage, run this checklist:
- [ ] Code runs without errors
- [ ] Logs appear in expected places
- [ ] Database is being written to
- [ ] No unhandled exceptions in console

---

## Estimated Timeline

| Stage | Time Estimate | Cumulative |
|-------|--------------|------------|
| 0. Setup | 1-2 hours | 2 hours |
| 1. Infrastructure | 3-4 hours | 6 hours |
| 2. Basic Monitoring | 4-6 hours | 12 hours |
| 3. Loop & Storage | 3-4 hours | 16 hours |
| 4. Auto-Recovery | 2-3 hours | 19 hours |
| 5. Deep Diagnostics | 4-6 hours | 25 hours |
| 6. System Tray | 3-4 hours | 29 hours |
| 7. Polish | 2-3 hours | 32 hours |

**Total estimated development time: ~30-35 hours**

This can be done over 1-2 weeks with a few hours per day, or in a focused sprint over 4-5 days.

---

## Success Criteria

### MVP is complete when:
- ✅ Tool runs continuously in system tray
- ✅ Automatically detects NetBird failures
- ✅ Restarts NetBird when needed
- ✅ Collects comprehensive diagnostic data
- ✅ All data is stored in SQLite
- ✅ Can manually trigger checks and restarts
- ✅ Runs for 1 week without crashing

### Ready for GitHub contributions when:
- ✅ Have collected 2+ weeks of real failure data
- ✅ Can identify common failure patterns
- ✅ Have identified 3+ distinct root causes
- ✅ Have documented reproduction steps for failures
- ✅ Can generate well-formatted issue reports from data

---

## Notes for Implementation

### When You Get Stuck
1. Check `meta_logs` table for tool's own errors
2. Review validation failures - is output schema wrong?
3. Test individual monitor functions in isolation
4. Add more logging (can always reduce later)

### Code Quality Guidelines
- **Type hints**: Use them for function signatures
- **Docstrings**: Every public function needs one
- **Error messages**: Should explain what failed AND what was expected
- **Magic numbers**: Put in `config.py`, not hardcoded

### Common Pitfalls to Avoid
- Don't collect too much data initially (you'll drown in it)
- Don't build the issue generator before you understand the failures
- Don't assume Windows commands will work (they might need admin privileges)
- Don't forget to validate outputs (your code will have bugs too)

### Remember the Goal
This is about:
1. **Solving the immediate problem** (NetBird restarts)
2. **Collecting data** for future analysis
3. **Building career skills** in debugging and open source

The quality of your bug reports will directly correlate with the quality of data you collect now. Take time to get the diagnostics right.
