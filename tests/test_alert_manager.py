"""
Tests for AlertManager.
"""

import time

import pytest

from config.settings import AlertConfig
from src.alerts.alert_manager import Alert, AlertManager


def _make_manager(cooldown: int = 60) -> AlertManager:
    cfg = AlertConfig(
        admin_email="admin@test.com",
        smtp_host="localhost",
        smtp_port=587,
        smtp_user="",  # empty → email dispatch skipped
        smtp_password="",
        alert_cooldown_seconds=cooldown,
        webhook_url="",  # empty → webhook dispatch skipped
    )
    return AlertManager(config=cfg)


class TestAlert:
    def test_dedup_key_unique_per_camera_zone_type(self):
        a1 = Alert(
            camera_id="cam-01",
            zone="entrance",
            alert_type="loitering",
            severity="medium",
            description="test",
        )
        a2 = Alert(
            camera_id="cam-02",
            zone="entrance",
            alert_type="loitering",
            severity="medium",
            description="test",
        )
        assert a1.dedup_key != a2.dedup_key

    def test_dedup_key_same_for_same_params(self):
        a1 = Alert(
            camera_id="cam-01",
            zone="hall",
            alert_type="fight",
            severity="high",
            description="test1",
        )
        a2 = Alert(
            camera_id="cam-01",
            zone="hall",
            alert_type="fight",
            severity="high",
            description="test2",
        )
        assert a1.dedup_key == a2.dedup_key


class TestAlertManager:
    def test_dispatch_returns_true_first_time(self):
        mgr = _make_manager(cooldown=60)
        alert = Alert(
            camera_id="cam-01",
            zone="entrance",
            alert_type="loitering",
            severity="medium",
            description="test alert",
        )
        assert mgr.dispatch(alert) is True

    def test_dispatch_returns_false_within_cooldown(self):
        mgr = _make_manager(cooldown=60)
        alert = Alert(
            camera_id="cam-01",
            zone="entrance",
            alert_type="loitering",
            severity="medium",
            description="test",
        )
        mgr.dispatch(alert)
        assert mgr.dispatch(alert) is False

    def test_dispatch_allowed_after_cooldown(self):
        mgr = _make_manager(cooldown=0)  # zero cooldown
        alert = Alert(
            camera_id="cam-01",
            zone="entrance",
            alert_type="intrusion",
            severity="high",
            description="test",
        )
        assert mgr.dispatch(alert) is True
        time.sleep(0.05)
        assert mgr.dispatch(alert) is True

    def test_different_zones_not_deduplicated(self):
        mgr = _make_manager(cooldown=60)
        a1 = Alert(
            camera_id="cam-01",
            zone="entrance",
            alert_type="loitering",
            severity="medium",
            description="t",
        )
        a2 = Alert(
            camera_id="cam-01",
            zone="cafeteria",
            alert_type="loitering",
            severity="medium",
            description="t",
        )
        assert mgr.dispatch(a1) is True
        assert mgr.dispatch(a2) is True

    def test_on_alert_callback_called(self):
        received = []
        mgr = AlertManager(
            config=AlertConfig(
                admin_email="x@x.com",
                smtp_user="",
                smtp_password="",
                webhook_url="",
                alert_cooldown_seconds=0,
            ),
            on_alert=lambda a: received.append(a),
        )
        alert = Alert(
            camera_id="cam-01",
            zone="hall",
            alert_type="fight",
            severity="critical",
            description="fight detected",
        )
        mgr.dispatch(alert)
        assert len(received) == 1
        assert received[0].alert_type == "fight"

    def test_build_alert_dispatches_immediately(self):
        fired = []
        mgr = AlertManager(
            config=AlertConfig(
                admin_email="a@b.com",
                smtp_user="",
                smtp_password="",
                webhook_url="",
                alert_cooldown_seconds=0,
            ),
            on_alert=lambda a: fired.append(a),
        )
        mgr.build_alert(
            camera_id="cam-02",
            zone="parking",
            alert_type="anomaly",
            description="Car in pedestrian zone",
            severity="high",
        )
        assert len(fired) == 1

    def test_pending_count_increases_with_alerts(self):
        mgr = _make_manager(cooldown=0)
        for i in range(3):
            mgr.dispatch(
                Alert(
                    camera_id=f"cam-{i}",
                    zone="zone",
                    alert_type="loitering",
                    severity="low",
                    description="x",
                )
            )
            time.sleep(0.01)
        assert mgr.pending_count(since_seconds=60) == 3

    def test_severity_levels_accepted(self):
        mgr = _make_manager(cooldown=0)
        for sev in ("low", "medium", "high", "critical"):
            a = Alert(
                camera_id="c",
                zone="z",
                alert_type="other",
                severity=sev,
                description="test",
            )
            assert mgr.dispatch(a) is True
