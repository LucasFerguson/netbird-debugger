# NetBird Sentinel

Windows-native monitoring and diagnostic tool for NetBird agent failures.

## Requirements

- Windows 10/11
- Python 3.10+
- NetBird CLI installed and available in `PATH`

## Setup

1) Create virtual environment

```powershell
python -m venv .venv
```

2) Activate

```powershell
.\.venv\Scripts\Activate.ps1
```

3) Install dependencies

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python src\main.py
```

Use environment variables to override defaults:

```powershell
$env:NETBIRD_ROUTINE_CHECK_INTERVAL="1"
$env:NETBIRD_ROUTINE_TIMEOUT_SECONDS="2"
$env:NETBIRD_RESTART_FAILURE_THRESHOLD="10"
$env:NETBIRD_AUTO_RESTART_ENABLED="false"
$env:NETBIRD_REPORT_INTERVAL_SECONDS="120"
python src\main.py
```

## Reports

Reports are generated after `NETBIRD_REPORT_INTERVAL_SECONDS` and written to `reports/`.
Each report includes raw attachments for deep diagnostics and NetBird CLI outputs.

## Clear the database

This deletes all rows in the SQLite database:

```powershell
python -c "import sys; sys.path.append('src'); from storage.database import db; db.initialize(); db.clear_all(); print('cleared')"
```

## Notes

- Restarting the NetBird service requires an elevated PowerShell.
- Service reachability checks include TCP + HTTP; TLS cert errors are reported but do not mark the service as unreachable.
