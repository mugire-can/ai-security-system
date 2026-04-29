"""
Central configuration for the AI Security Camera System.
All settings can be overridden via environment variables or a .env file.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class VenueType(str, Enum):
    SCHOOL = "school"
    COMMERCIAL = "commercial"
    WORKPLACE = "workplace"


@dataclass
class CameraConfig:
    """Configuration for a single camera feed."""

    camera_id: str
    source: str  # URL, RTSP stream, or integer device index
    zone: str  # e.g. "entrance", "classroom-A", "shop-floor"
    fps: int = 15
    width: int = 1280
    height: int = 720
    enabled: bool = True


@dataclass
class AlertConfig:
    """Admin notification settings."""

    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@example.com")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    # Cooldown in seconds before the same alert is resent for the same person/zone
    alert_cooldown_seconds: int = 60
    # Webhook URL for instant push notifications (Slack, Teams, etc.)
    webhook_url: str = os.getenv("ALERT_WEBHOOK_URL", "")

    def __repr__(self) -> str:
        # Never expose the SMTP password in logs or repr output.
        masked = "***" if self.smtp_password else ""
        return (
            f"AlertConfig(admin_email={self.admin_email!r}, "
            f"smtp_host={self.smtp_host!r}, smtp_port={self.smtp_port}, "
            f"smtp_user={self.smtp_user!r}, smtp_password={masked!r}, "
            f"alert_cooldown_seconds={self.alert_cooldown_seconds}, "
            f"webhook_url={self.webhook_url!r})"
        )

    def validate(self) -> None:
        """Log warnings for common misconfigurations."""
        import logging

        _log = logging.getLogger(__name__)
        if self.smtp_user and self.admin_email == "admin@example.com":
            _log.warning(
                "AlertConfig: SMTP credentials are set but ADMIN_EMAIL is still "
                "the default placeholder 'admin@example.com'. "
                "Set ADMIN_EMAIL env var to receive alert emails."
            )


@dataclass
class DetectionConfig:
    """Thresholds and model settings for the detection pipeline."""

    # Minimum confidence to report a detected person (0–1)
    person_confidence_threshold: float = 0.55
    # Minimum confidence for suspicious behaviour classification
    behaviour_confidence_threshold: float = 0.65
    # Frame sampling rate for heavy analysis (every N frames)
    analysis_frame_interval: int = 5
    # How long (seconds) a "loitering" dwell triggers an alert
    loitering_threshold_seconds: int = 120
    # Frames of unusual activity before alerting
    anomaly_consecutive_frames: int = 10
    # YOLO model weights (path or HuggingFace model name)
    yolo_model: str = os.getenv("YOLO_MODEL", "yolov8n.pt")
    # Face-recognition tolerance (lower = stricter)
    face_recognition_tolerance: float = 0.5


@dataclass
class SystemHealthConfig:
    """Runtime health thresholds for camera and service monitoring."""

    camera_stall_seconds: int = int(os.getenv("CAMERA_STALL_SECONDS", "10"))
    max_consecutive_read_failures: int = int(os.getenv("MAX_CONSECUTIVE_READ_FAILURES", "5"))


@dataclass
class AttendanceConfig:
    """Roll-call and time-tracking settings."""

    # Directory that holds registered face images, one sub-folder per person
    known_faces_dir: str = os.getenv("KNOWN_FACES_DIR", "data/known_faces")
    # Earliest time considered a valid check-in (HH:MM)
    work_start_time: str = os.getenv("WORK_START_TIME", "08:00")
    # Latest time considered a valid check-out (HH:MM)
    work_end_time: str = os.getenv("WORK_END_TIME", "18:00")
    # CSV / SQLite path for exported reports
    reports_dir: str = os.getenv("REPORTS_DIR", "data/reports")


@dataclass
class DatabaseConfig:
    """Persistent storage settings."""

    db_url: str = os.getenv("DATABASE_URL", "sqlite:///data/security_system.db")


@dataclass
class AppConfig:
    """Top-level application configuration."""

    venue_type: VenueType = VenueType(os.getenv("VENUE_TYPE", VenueType.SCHOOL.value))
    venue_name: str = os.getenv("VENUE_NAME", "My Venue")
    cameras: List[CameraConfig] = field(default_factory=list)
    alert: AlertConfig = field(default_factory=AlertConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    health: SystemHealthConfig = field(default_factory=SystemHealthConfig)
    attendance: AttendanceConfig = field(default_factory=AttendanceConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Default configuration used when no explicit config is provided at runtime.
# Replace / extend `cameras` with your actual camera sources.
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = AppConfig(
    venue_name="Demo Venue",
    cameras=[
        CameraConfig(
            camera_id="cam-01",
            source="0",  # webcam index 0
            zone="entrance",
        ),
    ],
)
