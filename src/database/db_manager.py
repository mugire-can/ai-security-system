"""
Database layer — SQLAlchemy ORM models and session management.

All persistent data (detections, alerts, attendance records, anomalies) is
stored in a single SQLite database by default.  Switching to PostgreSQL/MySQL
requires only a change to ``DATABASE_URL`` in the environment.
"""

import logging
from datetime import datetime, timezone
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class DetectionEvent(Base):
    """A single detection captured by a camera frame."""

    __tablename__ = "detection_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), nullable=False, index=True)
    zone = Column(String(128), nullable=False)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    object_type = Column(String(64), nullable=False)  # "person", "animal", "vehicle", …
    track_id = Column(String(64), nullable=True)  # optional tracker identity
    person_name = Column(String(128), nullable=True)  # set after face recognition
    confidence = Column(Float, nullable=False)
    bbox_x = Column(Integer, nullable=True)
    bbox_y = Column(Integer, nullable=True)
    bbox_w = Column(Integer, nullable=True)
    bbox_h = Column(Integer, nullable=True)
    snapshot_path = Column(String(256), nullable=True)  # saved frame crop

    def __repr__(self) -> str:
        return (
            f"<DetectionEvent id={self.id} camera={self.camera_id} "
            f"type={self.object_type} ts={self.timestamp}>"
        )


class BehaviourEvent(Base):
    """
    A behaviour classification tied to a DetectionEvent.
    Includes emotion analysis, activity, and suspicion score.
    """

    __tablename__ = "behaviour_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detection_id = Column(Integer, nullable=False, index=True)
    camera_id = Column(String(64), nullable=False, index=True)
    zone = Column(String(128), nullable=False)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    person_name = Column(String(128), nullable=True)
    activity = Column(String(128), nullable=True)  # "studying", "working", "loitering", …
    emotion = Column(String(64), nullable=True)  # "happy", "angry", "fear", …
    suspicion_score = Column(Float, default=0.0)  # 0.0 – 1.0
    is_suspicious = Column(Boolean, default=False, index=True)
    notes = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<BehaviourEvent id={self.id} activity={self.activity} "
            f"suspicious={self.is_suspicious} score={self.suspicion_score:.2f}>"
        )


class AlertRecord(Base):
    """An alert sent (or queued to be sent) to the administrator."""

    __tablename__ = "alert_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    camera_id = Column(String(64), nullable=False)
    zone = Column(String(128), nullable=False)
    person_name = Column(String(128), nullable=True)
    alert_type = Column(
        Enum(
            "suspicious_behaviour",
            "loitering",
            "intrusion",
            "anomaly",
            "fight",
            "unattended_object",
            "animal_detected",
            "other",
            name="alert_type_enum",
        ),
        nullable=False,
    )
    severity = Column(
        Enum("low", "medium", "high", "critical", name="severity_enum"),
        nullable=False,
        default="medium",
    )
    description = Column(Text, nullable=True)
    snapshot_path = Column(String(256), nullable=True)
    sent = Column(Boolean, default=False)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(128), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AlertRecord id={self.id} type={self.alert_type} "
            f"severity={self.severity} sent={self.sent}>"
        )


class AttendanceRecord(Base):
    """Tracks check-in / check-out times for known individuals."""

    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    person_name = Column(String(128), nullable=False, index=True)
    camera_id = Column(String(64), nullable=False)
    zone = Column(String(128), nullable=False)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, nullable=True)
    status = Column(
        Enum("present", "absent", "late", "early_leave", name="attendance_status_enum"),
        nullable=False,
        default="present",
    )
    notes = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AttendanceRecord {self.person_name} {self.date} "
            f"in={self.check_in} out={self.check_out} status={self.status}>"
        )


class AnomalyEvent(Base):
    """Non-human anomaly detection (animals, abandoned objects, vehicles, etc.)."""

    __tablename__ = "anomaly_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), nullable=False, index=True)
    zone = Column(String(128), nullable=False)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    anomaly_type = Column(String(128), nullable=False)  # "animal", "unattended_bag", …
    object_class = Column(String(64), nullable=True)  # YOLO class label
    confidence = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    snapshot_path = Column(String(256), nullable=True)
    resolved = Column(Boolean, default=False)

    def __repr__(self) -> str:
        return (
            f"<AnomalyEvent id={self.id} type={self.anomaly_type} "
            f"camera={self.camera_id} ts={self.timestamp}>"
        )


# ---------------------------------------------------------------------------
# Database manager
# ---------------------------------------------------------------------------


class DatabaseManager:
    """
    Thin wrapper around SQLAlchemy engine + session factory.

    Usage::

        db = DatabaseManager("sqlite:///data/security_system.db")
        with db.session() as s:
            s.add(some_record)
    """

    def __init__(self, db_url: str) -> None:
        self._engine = create_engine(db_url, echo=False, future=True)
        # Enable WAL mode for SQLite to allow concurrent readers
        if db_url.startswith("sqlite"):

            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(conn, _record):
                conn.execute("PRAGMA journal_mode=WAL")

        self._SessionLocal = sessionmaker(
            bind=self._engine, autoflush=False, autocommit=False, future=True
        )
        Base.metadata.create_all(bind=self._engine)
        logger.info("Database initialised at %s", db_url)

    def session(self) -> Session:
        """Return a new SQLAlchemy session (use as a context manager)."""
        return self._SessionLocal()

    def get_alert_count(self, acknowledged: Optional[bool] = None) -> int:
        with self.session() as s:
            q = s.query(AlertRecord)
            if acknowledged is not None:
                q = q.filter(AlertRecord.acknowledged == acknowledged)
            return q.count()

    def get_today_attendance(self, date_str: str) -> list:
        with self.session() as s:
            return s.query(AttendanceRecord).filter(AttendanceRecord.date == date_str).all()
