"""
Tests for AttendanceTracker.
"""

from datetime import datetime, timedelta

import pytest

from src.attendance.time_tracker import AttendanceTracker


class TestAttendanceTracker:
    def _make_tracker(self, work_start="08:00", work_end="17:00"):
        return AttendanceTracker(
            work_start=work_start,
            work_end=work_end,
        )

    def test_checkin_on_first_sighting(self):
        tracker = self._make_tracker()
        ts = datetime.now().replace(hour=8, minute=0, second=0)
        tracker.record_sighting("Alice", "cam-01", "entrance", timestamp=ts)
        summary = tracker.get_today_summary()
        assert len(summary) == 1
        assert summary[0]["name"] == "Alice"
        assert summary[0]["check_in"] is not None

    def test_second_sighting_does_not_duplicate_checkin(self):
        tracker = self._make_tracker()
        ts = datetime.now().replace(hour=8, minute=5, second=0)
        tracker.record_sighting("Bob", "cam-01", "entrance", timestamp=ts)
        tracker.record_sighting("Bob", "cam-01", "corridor", timestamp=ts + timedelta(minutes=10))
        summary = tracker.get_today_summary()
        assert len(summary) == 1

    def test_checkout_records_duration(self):
        tracker = self._make_tracker()
        checkin_ts = datetime.now().replace(hour=9, minute=0, second=0)
        checkout_ts = checkin_ts + timedelta(hours=4)

        tracker.record_sighting("Carol", "cam-01", "office", timestamp=checkin_ts)
        tracker.record_departure("Carol", "cam-01", "office", timestamp=checkout_ts)

        summary = tracker.get_today_summary()
        assert len(summary) == 1
        assert summary[0]["check_out"] is not None
        assert summary[0]["duration_min"] == pytest.approx(240, abs=1)

    def test_late_status(self):
        tracker = self._make_tracker(work_start="08:00")
        late_ts = datetime.now().replace(hour=8, minute=30, second=0)
        tracker.record_sighting("Dave", "cam-01", "lobby", timestamp=late_ts)
        summary = tracker.get_today_summary()
        assert summary[0]["status"] == "late"

    def test_present_status_on_time(self):
        tracker = self._make_tracker(work_start="08:00")
        on_time_ts = datetime.now().replace(hour=7, minute=58, second=0)
        tracker.record_sighting("Eve", "cam-01", "lobby", timestamp=on_time_ts)
        summary = tracker.get_today_summary()
        assert summary[0]["status"] == "present"

    def test_early_leave_status(self):
        tracker = self._make_tracker(work_end="17:00")
        checkin_ts = datetime.now().replace(hour=8, minute=0, second=0)
        early_out_ts = datetime.now().replace(hour=14, minute=0, second=0)

        tracker.record_sighting("Frank", "cam-01", "office", timestamp=checkin_ts)
        tracker.record_departure("Frank", "cam-01", "office", timestamp=early_out_ts)

        summary = tracker.get_today_summary()
        assert summary[0]["status"] == "early_leave"

    def test_absent_from_registered(self):
        tracker = self._make_tracker()
        tracker.record_sighting("Grace", "cam-01", "room", timestamp=datetime.now())
        absentees = tracker.get_absent_from_registered(["Grace", "Henry", "Iris"])
        assert "Grace" not in absentees
        assert "Henry" in absentees
        assert "Iris" in absentees

    def test_auto_checkout_inactive_person(self):
        tracker = self._make_tracker()
        old_ts = datetime.now() - timedelta(seconds=600)
        tracker.record_sighting("Jake", "cam-01", "room", timestamp=old_ts)
        tracker._last_seen["Jake"] = old_ts

        tracker.auto_checkout(inactivity_seconds=300)
        summary = tracker.get_today_summary()
        checked_out = [r for r in summary if r["name"] == "Jake" and r["check_out"] != "—"]
        assert len(checked_out) == 1

    def test_multiple_people(self):
        tracker = self._make_tracker()
        ts = datetime.now()
        for name in ["Kim", "Lee", "Mia"]:
            tracker.record_sighting(name, "cam-01", "classroom", timestamp=ts)
        summary = tracker.get_today_summary()
        assert len(summary) == 3
        names = {r["name"] for r in summary}
        assert names == {"Kim", "Lee", "Mia"}

    def test_checkin_callback_fired(self):
        fired = []

        def on_checkin(name, cam, zone, ts):
            fired.append(name)

        tracker = AttendanceTracker(
            work_start="08:00",
            work_end="17:00",
            on_checkin=on_checkin,
        )
        tracker.record_sighting("Nina", "cam-01", "hall", timestamp=datetime.now())
        assert "Nina" in fired

    def test_checkout_callback_fired(self):
        fired = []

        def on_checkout(name, cam, zone, ts, dur):
            fired.append((name, dur))

        tracker = AttendanceTracker(
            work_start="08:00",
            work_end="17:00",
            on_checkout=on_checkout,
        )
        checkin = datetime.now().replace(hour=8, minute=0)
        checkout = checkin + timedelta(hours=2)
        tracker.record_sighting("Oscar", "cam-01", "room", timestamp=checkin)
        tracker.record_departure("Oscar", "cam-01", "room", timestamp=checkout)

        assert any(name == "Oscar" for name, _ in fired)
