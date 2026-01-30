# NetBird Sentinel - Project Plan

## Mission Statement

**NetBird Sentinel** is a Windows-native monitoring and diagnostic tool designed to automatically detect, document, and recover from NetBird agent failures. Beyond immediate problem-solving, this project serves a larger career goal: establishing a systematic approach to identifying, documenting, and reporting software failures in open-source projects.

This tool is the first in a planned framework of diagnostic utilities that will enable high-quality bug reports and GitHub issue contributions, demonstrating real-world debugging skills and community engagement that sets me apart as a software engineer.

---

## Core Philosophy

### 1. Data Collection First, Analysis Later
- Build robust data collection infrastructure before creating reporting tools
- Store structured data (JSON, SQLite) that can be processed by future scripts
- Understand failure patterns through data before automating issue generation

### 2. Assume Nothing Works Perfectly
- Every diagnostic check can fail or return unexpected output
- Validate all outputs against expected schemas
- Log when our own tools fail to collect data
- Graceful degradation: partial data is better than no data

### 3. Deep Diagnostics Only When Needed
- Lightweight checks run continuously (every 30-60s)
- Deep, expensive diagnostics trigger only on detected anomalies
- Balance thoroughness with system resource usage

### 4. Windows-First, Multi-Layer Analysis
NetBird failures on Windows can occur at multiple layers:
- **Process layer**: NetBird.exe crashes or hangs
- **Network driver layer**: Windows network stack issues, VPN conflicts
- **DNS layer**: Cannot resolve `*.netbird.cloud` domains
- **Firewall layer**: Windows Defender or other security software blocking
- **Resource layer**: Out of memory, CPU saturation
- **Service dependency layer**: WinSock, TAP adapter, routing issues

The tool must collect data across ALL these layers to enable correlation and root cause analysis.

---

## Project Goals

### Immediate Goals
1. **Automatic recovery**: Detect NetBird failures and restart the service automatically
2. **Service monitoring**: Track reachability of critical services (gitea.netbird.cloud, pve4.netbird.cloud, caddy.netbird.cloud)
3. **System tray presence**: Provide visual status indicator and manual controls
4. **Failure documentation**: Collect comprehensive diagnostic data when failures occur

### Long-Term Goals
1. **Pattern detection**: Identify correlations (e.g., "NetBird fails every time Windows updates network profile")
2. **GitHub issue generation**: Template-based issue creator using collected diagnostic data
3. **Framework generalization**: Extract reusable patterns for monitoring other flaky software
4. **Career differentiation**: Build portfolio of open-source contributions backed by data-driven bug reports

---

## Architecture Overview

```
netbird-sentinel/
├── src/
│   ├── main.py                      # Entry point, orchestration loop
│   ├── config.py                    # Configuration (check intervals, services to monitor)
│   │
│   ├── monitors/                    # Diagnostic check modules
│   │   ├── __init__.py
│   │   ├── process_monitor.py      # NetBird process health checks
│   │   ├── network_monitor.py      # Basic connectivity (ping, DNS, HTTP)
│   │   ├── deep_network.py         # Advanced diagnostics (routes, adapters, firewall)
│   │   └── windows_events.py       # Windows Event Log scraping
│   │
│   ├── diagnostics/                 # Check execution & validation
│   │   ├── __init__.py
│   │   ├── collector.py            # Runs checks, handles failures gracefully
│   │   ├── validator.py            # Validates check outputs match schemas
│   │   └── schemas.py              # Expected data structures for each check
│   │
│   ├── storage/                     # Data persistence
│   │   ├── __init__.py
│   │   ├── database.py             # SQLite operations
│   │   └── models.py               # Database schema definitions
│   │
│   ├── logger/                      # Application logging
│   │   ├── __init__.py
│   │   ├── app_logger.py           # Logging configuration and utilities
│   │   └── formatters.py           # Log formatting for console/file/DB
│   │
│   ├── recovery/                    # Failure recovery
│   │   ├── __init__.py
│   │   └── netbird_restart.py      # NetBird service restart logic
│   │
│   └── ui/                          # User interface
│       ├── __init__.py
│       └── tray_icon.py            # System tray icon and menu
│
├── logs/                            # Rotating log files
├── data/                            # SQLite database storage
├── requirements.txt                 # Python dependencies
└── README.md                        # Setup and usage instructions
```

---

## Data Model

### SQLite Schema

#### `health_checks` - Continuous monitoring data
```sql
CREATE TABLE health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    check_type TEXT NOT NULL,  -- 'routine' or 'deep'
    
    -- Process status
    netbird_running BOOLEAN,
    netbird_pid INTEGER,
    netbird_uptime_seconds INTEGER,
    netbird_cpu_percent REAL,
    netbird_memory_mb REAL,
    
    -- Network connectivity
    internet_reachable BOOLEAN,
    dns_working BOOLEAN,
    services_status TEXT,  -- JSON: {"gitea": true, "pve4": false, "caddy": true}
    
    -- Overall assessment
    system_healthy BOOLEAN,
    
    -- Metadata
    check_duration_ms INTEGER
);
```

#### `failures` - Detected failures with full diagnostic context
```sql
CREATE TABLE failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    
    -- Failure classification
    failure_type TEXT NOT NULL,  -- 'process_dead', 'network_unreachable', 'service_timeout', etc.
    severity TEXT,  -- 'critical', 'warning', 'info'
    
    -- Diagnostic data (comprehensive JSON blob)
    diagnostics TEXT NOT NULL,  -- JSON with all collected data
    
    -- Recovery actions
    auto_restart_attempted BOOLEAN,
    restart_successful BOOLEAN,
    recovery_timestamp TEXT,
    
    -- Analysis
    notes TEXT  -- For manual annotations
);
```

#### `windows_events` - Relevant Windows Event Log entries
```sql
CREATE TABLE windows_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_timestamp TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    event_id INTEGER,
    source TEXT,
    level TEXT,  -- 'Error', 'Warning', 'Information'
    message TEXT,
    
    -- Link to failure if correlated
    related_failure_id INTEGER,
    FOREIGN KEY (related_failure_id) REFERENCES failures(id)
);
```

#### `meta_logs` - Logs about the monitoring tool itself
```sql
CREATE TABLE meta_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    component TEXT,  -- Which module generated this log
    message TEXT,
    details TEXT,  -- JSON with additional context
    
    -- For tracking our own failures
    check_name TEXT,  -- If a specific check failed
    error_type TEXT   -- 'parse_error', 'timeout', 'validation_failed', etc.
);
```

### Diagnostic Data Structure (JSON stored in `failures.diagnostics`)
```json
{
  "timestamp": "2026-01-29T14:23:45.123Z",
  "failure_type": "network_unreachable",
  
  "process": {
    "running": true,
    "pid": 12345,
    "uptime_seconds": 3842,
    "cpu_percent": 2.3,
    "memory_mb": 145.2,
    "threads": 8
  },
  
  "network": {
    "internet_reachable": true,
    "dns_resolves": false,
    "dns_servers": ["8.8.8.8", "1.1.1.1"],
    "active_adapters": [
      {"name": "Ethernet", "status": "up", "ipv4": "192.168.1.100"},
      {"name": "NetBird", "status": "up", "ipv4": "100.64.0.5"}
    ],
    "routing_table": "...",  -- Full route print output
    "service_checks": {
      "gitea.netbird.cloud:3000": {"reachable": false, "error": "timeout", "latency_ms": null},
      "pve4.netbird.cloud": {"reachable": false, "error": "dns_failed", "latency_ms": null},
      "caddy.netbird.cloud": {"reachable": false, "error": "connection_refused", "latency_ms": null}
    }
  },
  
  "system": {
    "os_version": "Windows 11 Pro 23H2",
    "uptime_hours": 72.5,
    "cpu_usage_percent": 45.2,
    "memory_usage_percent": 68.4,
    "disk_usage_percent": 82.1
  },
  
  "windows_events": [
    {
      "timestamp": "2026-01-29T14:22:10Z",
      "event_id": 4202,
      "source": "Tcpip",
      "level": "Warning",
      "message": "The system detected that network adapter NetBird..."
    }
  ],
  
  "check_metadata": {
    "checks_attempted": ["process", "network_basic", "network_deep", "windows_events"],
    "checks_succeeded": ["process", "network_basic", "network_deep"],
    "checks_failed": ["windows_events"],
    "check_failures": {
      "windows_events": {
        "error": "PowerShell command timed out after 30s",
        "error_type": "timeout"
      }
    }
  }
}
```

---

## Component Specifications

### 1. Monitoring Loop
- **Routine checks**: Every 30-60 seconds
  - Is NetBird process running?
  - Can we reach any netbird.cloud service?
  - Basic internet connectivity (ping 8.8.8.8)
  
- **Deep diagnostics trigger**: When ANY of these occur:
  - NetBird process dies
  - All netbird.cloud services unreachable (but internet works)
  - Pattern of intermittent failures detected
  
- **Deep diagnostics collect**:
  - Full network adapter details
  - Routing table
  - Windows Event Log entries (last 5 minutes, network-related)
  - Active connections (`netstat` equivalent)
  - Firewall rules (if accessible)

### 2. Service Health Logic
**Three-tier assessment:**

1. ✅ **Healthy (Green)**: NetBird running + all services reachable
2. ⚠️ **Degraded (Yellow)**: NetBird running + some services unreachable
   - *Action*: Log but don't restart (likely individual service issues)
3. 🔴 **Failed (Red)**: NetBird dead OR NetBird running but NO services reachable
   - *Action*: Trigger deep diagnostics + auto-restart NetBird

### 3. Validation & Error Handling
Every diagnostic check must:
1. Return a structured result: `{success: bool, data: dict, error: str, error_type: str}`
2. Have a timeout (30s max for deep checks, 5s for routine)
3. Validate output against expected schema
4. Log to `meta_logs` when validation fails

Example validation failure log:
```python
logger.error(
    "Route table parsing failed",
    extra={
        "check_name": "deep_network.get_routes",
        "expected_format": "JSON with keys: destination, gateway, interface",
        "received": raw_output[:200],  # First 200 chars
        "error_type": "parse_error"
    }
)
```

### 4. Logging Strategy
**Three logging outputs:**
1. **Console**: Real-time for development/debugging
2. **File**: Rotating daily logs in `logs/sentinel-YYYY-MM-DD.log`
3. **Database**: `meta_logs` table for programmatic analysis

**Log what matters:**
- When checks fail to execute
- When output doesn't match schema
- When auto-restart is triggered
- When patterns are detected (future enhancement)

**Don't log:**
- Successful routine checks (clutters logs)
- Raw diagnostic output (goes in SQLite instead)

### 5. System Tray UI
**Status indicator:**
- Green icon: All systems healthy
- Yellow icon: Degraded (some services down)
- Red icon: Failed (NetBird issue detected)

**Menu options:**
- "View Status" → Opens detailed view (console window or simple GUI)
- "Force Check Now" → Triggers immediate deep diagnostic
- "Restart NetBird" → Manual restart
- "View Recent Failures" → Shows last 10 failures from DB
- "Open Logs Folder"
- "Quit"

---

## Technology Stack

### Core Dependencies
- **Python 3.10+**: Language
- **sqlite3**: Built-in, database storage
- **psutil**: Process and system monitoring
- **requests**: HTTP service checks
- **pystray + Pillow**: System tray icon
- **pywin32**: Windows API access (Event Log, services)

### Development Tools
- **uv**: Fast Python package manager
- **black**: Code formatting
- **pytest**: Testing framework (for validators, schemas)

---

## Key Design Decisions

### Why Python?
Despite personal preference for TypeScript:
- Mature Windows system monitoring libraries (`psutil`, `pywin32`, `wmi`)
- Extensive documentation for Windows API interactions
- Large community with solved edge cases
- Fast time-to-working-prototype

### Why SQLite?
- Lightweight, no separate database process
- Built-in to Python
- Easy to query for pattern analysis
- Can be backed up by simply copying file
- Future scripts can read it easily

### Why Structured JSON in diagnostics column?
- Flexible schema evolution (add new diagnostic data without migrations)
- Easy to parse in future analysis scripts
- Can still query with SQLite's JSON functions if needed
- Human-readable when exported

### Why Separate Routine vs Deep Checks?
- System resources: Running full diagnostics every 30s would be excessive
- Signal-to-noise: Most checks will be healthy, don't waste CPU
- Targeted data: Deep diagnostics when you actually have a failure to investigate

---

## Future Enhancements (Post-MVP)

### Phase 2: Analysis & Reporting
- Pattern detection: "Fails every Tuesday at 3 AM" (Windows Update?)
- Correlation analysis: Link failures to Windows events
- GitHub issue template generator using collected data
- Export functionality: Generate markdown reports from SQLite

### Phase 3: Framework Generalization
- Abstract monitoring framework for any flaky service
- Plugin architecture for different software (PostgreSQL, Docker, etc.)
- Shared diagnostic library
- Centralized failure database across multiple tools

### Phase 4: Career Portfolio
- Blog posts about findings from NetBird monitoring
- Contributed GitHub issues with data-backed repro steps
- Open-source the framework itself
- Case studies of bugs discovered and fixed

---

## Success Metrics

### Technical Success
- ✅ NetBird uptime improves (fewer manual restarts needed)
- ✅ Failures are captured with full diagnostic context
- ✅ Can identify root cause of >80% of failures from data

### Career Success
- ✅ Submit at least 3 high-quality bug reports to NetBird repo
- ✅ Demonstrate systematic debugging approach in interviews
- ✅ Portfolio project showcases: monitoring, data analysis, Windows internals

### Learning Success
- ✅ Understand NetBird's failure modes deeply
- ✅ Gain expertise in Windows networking stack
- ✅ Build reusable diagnostic patterns for other projects

---

## Notes for Future LLM Agents

### Context for Handoff
This project was conceived as both a practical tool (fix flaky NetBird) and a career investment (demonstrate SWE skills through open-source contribution). The creator is a senior CS student graduating soon, looking to stand out in job applications.

### Key Constraints
- **Windows-specific for now**: Linux NetBird works fine
- **Data collection before automation**: Don't build issue generator until we understand failure patterns
- **Robustness over features**: Tool must not fail when collecting diagnostics

### Creator's Preferences
- Loves TypeScript but willing to use Python for pragmatism
- Values structured data and future extensibility
- Wants comprehensive logging to understand tool's own failures
- Appreciates staged development over big-bang delivery

### Important Philosophy
The creator wants to build skills in:
1. Systematic debugging
2. Technical writing (bug reports)
3. Open-source contribution
4. Standing out as a junior engineer

Keep this larger mission in mind when making technical decisions.
