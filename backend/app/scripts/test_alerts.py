"""Alert evaluation tests — one per alert condition plus the quiet case."""

from backend.app.scripts import alerts as al


HEALTHY = {
    "backend_ready_ok": True,
    "frontend_ok": True,
    "total_requests": 100,
    "server_errors": 0,
    "db_integrity": "ok",
    "backup_age_hours": 4,
    "free_bytes": 100 << 30,
    "restart_count": 0,
    "ai_configured": False,
}


class TestQuietSystem:
    def test_healthy_signals_fire_nothing(self):
        assert al.evaluate(HEALTHY) == []

    def test_empty_signals_fire_backup_missing(self):
        # No backup signal at all means we cannot prove backups exist —
        # that is precisely the backup_missing condition, not a quiet system.
        alerts = al.evaluate({})
        assert [a.id for a in alerts] == ["backup_missing"]


class TestAvailabilityAlerts:
    def test_backend_down_fires(self):
        alerts = al.evaluate({**HEALTHY, "backend_ready_ok": False})
        ids = [a.id for a in alerts]
        assert "backend_down" in ids
        assert ids[0] == "backend_down"
        assert alerts[0].severity == "critical"

    def test_frontend_down_fires(self):
        alerts = al.evaluate({**HEALTHY, "frontend_ok": False})
        assert any(a.id == "frontend_down" for a in alerts)


class TestErrorRate:
    def test_high_5xx_fires(self):
        alerts = al.evaluate({**HEALTHY, "server_errors": 10})  # 10/100 > 5%
        assert any(a.id == "high_5xx_rate" for a in alerts)

    def test_low_5xx_does_not_fire(self):
        alerts = al.evaluate({**HEALTHY, "server_errors": 3})  # 3/100 < 5%
        assert not any(a.id == "high_5xx_rate" for a in alerts)

    def test_small_sample_does_not_fire(self):
        # 1 error out of 10 (10%) must not fire: sample too small.
        alerts = al.evaluate({**HEALTHY, "total_requests": 10, "server_errors": 1})
        assert not any(a.id == "high_5xx_rate" for a in alerts)


class TestDatabaseAlerts:
    def test_integrity_failure_fires(self):
        alerts = al.evaluate({**HEALTHY, "db_integrity": "corrupt"})
        found = next(a for a in alerts if a.id == "db_integrity_failure")
        assert found.severity == "critical"
        assert "integrity_check" in found.message

    def test_ok_integrity_quiet(self):
        assert al.evaluate({**HEALTHY, "db_integrity": "ok"}) == []


class TestBackupAlerts:
    def test_missing_backup_fires(self):
        alerts = al.evaluate({**HEALTHY, "backup_age_hours": None})
        assert any(a.id == "backup_missing" for a in alerts)

    def test_stale_backup_fires_warning(self):
        alerts = al.evaluate({**HEALTHY, "backup_age_hours": 72})
        found = next(a for a in alerts if a.id == "backup_stale")
        assert found.severity == "warning"

    def test_fresh_backup_quiet(self):
        assert al.evaluate({**HEALTHY, "backup_age_hours": 6}) == []


class TestDiskAlerts:
    def test_low_disk_fires(self):
        alerts = al.evaluate({**HEALTHY, "free_bytes": 512 << 20})  # 0.5 GiB
        found = next(a for a in alerts if a.id == "low_disk")
        assert found.severity == "warning"

    def test_ample_disk_quiet(self):
        assert al.evaluate({**HEALTHY, "free_bytes": 50 << 30}) == []


class TestRestartStorm:
    def test_restart_storm_fires(self):
        alerts = al.evaluate({**HEALTHY, "restart_count": 5})
        assert any(a.id == "container_restart_storm" for a in alerts)

    def test_few_restarts_quiet(self):
        assert al.evaluate({**HEALTHY, "restart_count": 1}) == []


class TestAIAlerts:
    def test_ai_failures_fire_when_configured(self):
        signals = {
            **HEALTHY,
            "ai_configured": True,
            "ai_calls": 10,
            "ai_failures": 8,
        }
        alerts = al.evaluate(signals)
        found = next(a for a in alerts if a.id == "ai_provider_failure")
        assert found.severity == "warning"

    def test_ai_failures_ignored_when_unconfigured(self):
        signals = {
            **HEALTHY,
            "ai_configured": False,
            "ai_calls": 10,
            "ai_failures": 10,
        }
        assert not any(a.id == "ai_provider_failure" for a in al.evaluate(signals))

    def test_small_ai_sample_ignored(self):
        signals = {
            **HEALTHY,
            "ai_configured": True,
            "ai_calls": 2,
            "ai_failures": 2,
        }
        assert not any(a.id == "ai_provider_failure" for a in al.evaluate(signals))


class TestFormatting:
    def test_format_alerts_empty(self):
        assert al.format_alerts([]) == "no alerts"

    def test_format_alerts_lists_all(self):
        alerts = al.evaluate({**HEALTHY, "backend_ready_ok": False, "frontend_ok": False})
        text = al.format_alerts(alerts)
        assert "backend_down" in text
        assert "frontend_down" in text
        assert "CRITICAL" in text
