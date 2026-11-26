"""M3.4 Task 7 — health snapshot collector tests.

Pins that health_snapshot builds an alerts-compatible signals dict from
mockable inputs (HTTP probes, backup dir, disk, docker stats) and that the
alert engine fires on the resulting signals.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.scripts import health_snapshot
from backend.app.scripts.alerts import evaluate
from backend.app.scripts.health_snapshot import build_signals


class FakeResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _mock_urlopen(responses: dict[str, tuple[int, bytes]]):
    def fake(url, timeout):
        for path, (status, body) in responses.items():
            if url.endswith(path):
                return FakeResponse(status, body)
        raise AssertionError(f"unexpected url {url}")

    return fake


def test_signals_from_healthy_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(
        health_snapshot.urllib.request,
        "urlopen",
        _mock_urlopen(
            {
                "/api/ready": (200, json.dumps({"status": "ready"}).encode()),
                "/api/health": (200, b'{"status":"healthy"}'),
                "/api/release": (
                    200,
                    json.dumps({"version": "M3.3", "git_sha": "5c2c7d9"}).encode(),
                ),
                "/api/metrics": (
                    200,
                    json.dumps(
                        {"total_requests": 100, "status_classes": {"2xx": 98, "5xx": 2}}
                    ).encode(),
                ),
            }
        ),
    )
    # Fresh backup + plenty of disk.
    (tmp_path / "spectra_backup_20261126T000000Z.db").write_bytes(b"x" * 64)
    from collections import namedtuple
    _usage = namedtuple("usage", ["total", "used", "free"])
    monkeypatch.setattr(
        health_snapshot.shutil, "disk_usage",
        lambda _: _usage(100 << 30, 50 << 30, 50 << 30),
    )
    monkeypatch.setattr(
        health_snapshot, "_docker_restart_count", lambda container: 0
    )

    snapshot = build_signals(
        base_url="http://127.0.0.1:8080",
        backup_dir=tmp_path,
        container="spectra-backend",
    )

    signals = snapshot["signals"]
    assert signals["backend_ready_ok"] is True
    assert signals["frontend_ok"] is True
    assert signals["backup_age_hours"] < 48
    assert signals["free_bytes"] == 50 << 30
    assert signals["restart_count"] == 0
    assert signals["http_5xx_rate"] == 0.02
    assert snapshot["release"] == {"version": "M3.3", "git_sha": "5c2c7d9"}
    assert evaluate(signals) == []  # healthy: no alerts


def test_alerts_fire_on_degraded_signals(tmp_path, monkeypatch):
    monkeypatch.setattr(
        health_snapshot.urllib.request,
        "urlopen",
        _mock_urlopen(
            {
                "/api/ready": (503, b'{"detail":"not ready"}'),
                "/api/health": (200, b'{"status":"healthy"}'),
                "/api/release": (200, b"{}"),
                "/api/metrics": (
                    200,
                    json.dumps(
                        {"total_requests": 100, "status_classes": {"2xx": 90, "5xx": 10}}
                    ).encode(),
                ),
            }
        ),
    )
    # No backup files at all -> backup_missing.
    from collections import namedtuple

    _usage = namedtuple("usage", ["total", "used", "free"])
    monkeypatch.setattr(
        health_snapshot.shutil, "disk_usage",
        lambda _: _usage(100 << 30, 100 << 30 - 1, 1 << 20),
    )
    monkeypatch.setattr(
        health_snapshot, "_docker_restart_count", lambda container: 5
    )

    snapshot = build_signals(
        base_url="http://127.0.0.1:8080",
        backup_dir=tmp_path,
        container="spectra-backend",
    )

    signals = snapshot["signals"]
    alert_ids = {alert.id for alert in evaluate(signals)}
    assert "backend_down" in alert_ids
    assert "backup_missing" in alert_ids
    assert "low_disk" in alert_ids
    assert "container_restart_storm" in alert_ids


def test_snapshot_is_json_serializable_and_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(
        health_snapshot.urllib.request,
        "urlopen",
        _mock_urlopen({"/api/ready": (200, b"{}")}),
    )
    (tmp_path / "spectra_backup_20261126T000000Z.db").write_bytes(b"x")
    from collections import namedtuple

    _usage = namedtuple("usage", ["total", "used", "free"])
    monkeypatch.setattr(
        health_snapshot.shutil, "disk_usage", lambda _: _usage(1, 0, 1)
    )
    monkeypatch.setattr(
        health_snapshot, "_docker_restart_count", lambda container: 0
    )

    snapshot = build_signals(
        base_url="http://127.0.0.1:8080",
        backup_dir=tmp_path,
        container="spectra-backend",
    )
    encoded = json.dumps(snapshot)  # must not raise
    assert "signals" in json.loads(encoded)
