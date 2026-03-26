"""
Tests for AdminDashboard.

The dashboard now uses a TTY check (_use_colour) so ANSI escape codes are
suppressed in non-terminal environments like CI.  These tests exercise all
public feed methods, rendering, and the stop mechanism.
"""

import time
from unittest.mock import patch

import pytest

from src.alerts.alert_manager import Alert
from src.dashboard.admin_dashboard import AdminDashboard, _tty_supports_colour


def _make_alert(severity: str = "medium", alert_type: str = "loitering") -> Alert:
    return Alert(
        camera_id="cam-01",
        zone="entrance",
        alert_type=alert_type,
        severity=severity,
        description="test alert",
    )


# ---------------------------------------------------------------------------
# TTY detection helper
# ---------------------------------------------------------------------------

class TestTtySupportsColour:
    def test_no_color_env_disables_colour(self):
        with patch.dict("os.environ", {"NO_COLOR": "1"}, clear=False):
            assert _tty_supports_colour() is False

    def test_force_color_env_enables_colour(self):
        with patch.dict("os.environ", {"FORCE_COLOR": "1"}, clear=False):
            assert _tty_supports_colour() is True

    def test_no_tty_returns_false(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            with patch.dict("os.environ", {}, clear=True):
                assert _tty_supports_colour() is False


# ---------------------------------------------------------------------------
# AdminDashboard
# ---------------------------------------------------------------------------

class TestAdminDashboard:
    def test_init_defaults(self):
        dash = AdminDashboard()
        assert not dash._running
        assert dash._recent_alerts == []
        assert dash._active_cameras == []
        assert dash._person_count == 0
        assert dash._anomaly_count == 0

    def test_colour_helper_when_disabled(self):
        dash = AdminDashboard()
        dash._use_colour = False
        assert dash._c("\033[1m") == ""

    def test_colour_helper_when_enabled(self):
        dash = AdminDashboard()
        dash._use_colour = True
        assert dash._c("\033[1m") == "\033[1m"

    def test_update_cameras(self):
        dash = AdminDashboard()
        dash.update_cameras(["cam-01", "cam-02"])
        assert dash._active_cameras == ["cam-01", "cam-02"]

    def test_update_cameras_replaces_previous(self):
        dash = AdminDashboard()
        dash.update_cameras(["cam-01"])
        dash.update_cameras(["cam-02", "cam-03"])
        assert dash._active_cameras == ["cam-02", "cam-03"]

    def test_add_alert_prepends(self):
        dash = AdminDashboard()
        a1 = _make_alert(severity="low")
        a2 = _make_alert(severity="high")
        dash.add_alert(a1)
        dash.add_alert(a2)
        assert dash._recent_alerts[0].severity == "high"
        assert dash._recent_alerts[1].severity == "low"

    def test_add_alert_respects_max(self):
        dash = AdminDashboard(max_alerts=3)
        for _ in range(5):
            dash.add_alert(_make_alert())
        assert len(dash._recent_alerts) == 3

    def test_update_attendance(self):
        dash = AdminDashboard()
        records = [{"name": "Alice", "status": "present"}]
        dash.update_attendance(records)
        assert dash._attendance == records

    def test_update_counts(self):
        dash = AdminDashboard()
        dash.update_counts(persons=7, anomalies=3)
        assert dash._person_count == 7
        assert dash._anomaly_count == 3

    def test_stop_sets_running_false(self):
        dash = AdminDashboard()
        dash._running = True
        dash.stop()
        assert not dash._running

    def test_render_no_cameras_no_alerts(self, capsys):
        dash = AdminDashboard(venue_name="CI Test")
        dash._use_colour = False
        with patch("os.system"):
            dash.render()
        out = capsys.readouterr().out
        assert "CI Test" in out
        assert "CAMERAS" in out
        assert "No alerts" in out

    def test_render_with_cameras(self, capsys):
        dash = AdminDashboard(venue_name="Venue")
        dash._use_colour = False
        dash.update_cameras(["cam-01", "cam-02"])
        with patch("os.system"):
            dash.render()
        out = capsys.readouterr().out
        assert "cam-01" in out
        assert "cam-02" in out

    def test_render_with_alert(self, capsys):
        dash = AdminDashboard()
        dash._use_colour = False
        dash.add_alert(_make_alert(severity="high", alert_type="fighting"))
        with patch("os.system"):
            dash.render()
        out = capsys.readouterr().out
        assert "fighting" in out
        assert "HIGH" in out

    def test_render_with_attendance(self, capsys):
        dash = AdminDashboard()
        dash._use_colour = False
        dash.update_attendance([
            {
                "name": "Alice Smith",
                "status": "present",
                "check_in": "09:00",
                "check_out": "17:00",
                "duration_min": 480,
            }
        ])
        with patch("os.system"):
            dash.render()
        out = capsys.readouterr().out
        assert "Alice Smith" in out
        assert "PRESENT" in out

    def test_render_with_all_severity_levels(self, capsys):
        dash = AdminDashboard()
        dash._use_colour = False
        for sev in ("low", "medium", "high", "critical"):
            dash.add_alert(_make_alert(severity=sev))
        with patch("os.system"):
            dash.render()
        out = capsys.readouterr().out
        for sev in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            assert sev in out
