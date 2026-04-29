"""
Tests for the DatabaseManager and ORM models.
"""

from datetime import datetime

import pytest
from sqlalchemy import text

from src.database.db_manager import (
    AlertRecord,
    AnomalyEvent,
    AttendanceRecord,
    BehaviourEvent,
    DatabaseManager,
    DetectionEvent,
)


@pytest.fixture
def db():
    """In-memory SQLite database for testing."""
    manager = DatabaseManager("sqlite:///:memory:")
    return manager


class TestDetectionEvent:
    def test_insert_and_retrieve(self, db):
        with db.session() as s:
            rec = DetectionEvent(
                camera_id="cam-01",
                zone="entrance",
                object_type="person",
                confidence=0.9,
            )
            s.add(rec)
            s.commit()
            result = s.query(DetectionEvent).first()
        assert result.camera_id == "cam-01"
        assert result.object_type == "person"


class TestAlertRecord:
    def test_insert_and_count(self, db):
        with db.session() as s:
            for sev in ("low", "medium", "high"):
                s.add(
                    AlertRecord(
                        camera_id="cam-01",
                        zone="hall",
                        alert_type="loitering",
                        severity=sev,
                        acknowledged=False,
                    )
                )
            s.commit()

        count = db.get_alert_count(acknowledged=False)
        assert count == 3

    def test_acknowledged_filter(self, db):
        with db.session() as s:
            s.add(
                AlertRecord(
                    camera_id="cam-01",
                    zone="z",
                    alert_type="intrusion",
                    severity="high",
                    acknowledged=True,
                )
            )
            s.add(
                AlertRecord(
                    camera_id="cam-02",
                    zone="z",
                    alert_type="loitering",
                    severity="low",
                    acknowledged=False,
                )
            )
            s.commit()

        assert db.get_alert_count(acknowledged=True) == 1
        assert db.get_alert_count(acknowledged=False) == 1


class TestAttendanceRecord:
    def test_today_attendance(self, db):
        today = datetime.now().strftime("%Y-%m-%d")
        with db.session() as s:
            s.add(
                AttendanceRecord(
                    date=today,
                    person_name="Alice",
                    camera_id="cam-01",
                    zone="classroom",
                    check_in=datetime.now(),
                    status="present",
                )
            )
            s.commit()

        records = db.get_today_attendance(today)
        assert len(records) == 1
        assert records[0].person_name == "Alice"

    def test_different_date_not_returned(self, db):
        with db.session() as s:
            s.add(
                AttendanceRecord(
                    date="2020-01-01",
                    person_name="Bob",
                    camera_id="cam-01",
                    zone="office",
                    status="present",
                )
            )
            s.commit()

        records = db.get_today_attendance("2020-01-02")
        assert records == []


class TestAnomalyEvent:
    def test_insert_anomaly(self, db):
        with db.session() as s:
            s.add(
                AnomalyEvent(
                    camera_id="cam-01",
                    zone="entrance",
                    anomaly_type="animal_detected",
                    object_class="dog",
                    confidence=0.85,
                    description="Dog in lobby",
                )
            )
            s.commit()
            result = s.query(AnomalyEvent).first()
        assert result.anomaly_type == "animal_detected"
        assert result.resolved is False


class TestBehaviourEvent:
    def test_suspicious_flag(self, db):
        with db.session() as s:
            s.add(
                BehaviourEvent(
                    detection_id=1,
                    camera_id="cam-01",
                    zone="corridor",
                    activity="loitering",
                    suspicion_score=0.7,
                    is_suspicious=True,
                )
            )
            s.commit()
            result = s.query(BehaviourEvent).first()
        assert result.is_suspicious is True
        assert result.suspicion_score == pytest.approx(0.7)
