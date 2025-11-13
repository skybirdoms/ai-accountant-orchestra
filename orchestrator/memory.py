"""Small helpers for paths and timestamps (UTC)."""

from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE_ROOT = Path("workspace")
LOGS_DIR = WORKSPACE_ROOT / "logs"
ERRORS_DIR = WORKSPACE_ROOT / "errors"

def ensure_workspace() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ERRORS_DIR.mkdir(parents=True, exist_ok=True)

def ts_iso_utc() -> str:
    """ISO-8601 with 'Z' suffix, e.g. 2025-11-06T20:15:30.123Z"""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def ts_for_filename() -> str:
    """Filename-friendly timestamp, e.g. 2025-11-06T20-15-30.123Z"""
    return ts_iso_utc().replace(":", "-")

def logs_path() -> Path:
    ensure_workspace()
    return LOGS_DIR / f"{ts_for_filename()}.ndjson"

def errors_path() -> Path:
    ensure_workspace()
    return ERRORS_DIR / f"{ts_for_filename()}.json"
