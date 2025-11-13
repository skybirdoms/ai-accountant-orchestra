"""Stub router. Not used yet."""

from __future__ import annotations

def route(action: str, payload: dict | None = None) -> dict:
    return {
        "status": "NOT_IMPLEMENTED",
        "message": "router.route is a stub; no routing performed.",
        "action": action,
    }
