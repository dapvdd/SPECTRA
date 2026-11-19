"""Manufacturer alias map test shim — the canonical map lives in
canonical.py; this module re-exports it so callers can import either path."""
from backend.app.identity.canonical import ALIASES

__all__ = ["ALIASES"]
