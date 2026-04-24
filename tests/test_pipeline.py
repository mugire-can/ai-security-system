"""
Tests for the central ProcessingPipeline.

After fixing camera_manager.py to lazy-import cv2, the pipeline module can
be imported and the pure-Python code paths tested without a GPU, camera, or
any heavy ML dependency.
"""

import logging
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from config.settings import AppConfig, DatabaseConfig


def _make_config(db_url: str = "sqlite:///:memory:") -> AppConfig:
    """Return a minimal AppConfig that works without real cameras or GPU."""
    return AppConfig(
        venue_name="Test Venue",
        cameras=[],  # No cameras → CameraManager stays idle
        database=DatabaseConfig(db_url=db_url),
    )


# ---------------------------------------------------------------------------
# _score_to_severity — pure static method, no external deps
# ---------------------------------------------------------------------------

class TestScoreToSeverity:
    def test_critical_threshold(self):
        from src.pipeline import ProcessingPipeline
        assert ProcessingPipeline._score_to_severity(0.90) == "critical"
        assert ProcessingPipeline._score_to_severity(0.99) == "critical"
        assert ProcessingPipeline._score_to_severity(1.0) == "critical"

    def test_high_threshold(self):
        from src.pipeline import ProcessingPipeline
        assert ProcessingPipeline._score_to_severity(0.65) == "high"
        assert ProcessingPipeline._score_to_severity(0.80) == "high"
        assert ProcessingPipeline._score_to_severity(0.899) == "high"

    def test_medium_threshold(self):
        from src.pipeline import ProcessingPipeline
        assert ProcessingPipeline._score_to_severity(0.40) == "medium"
        assert ProcessingPipeline._score_to_severity(0.55) == "medium"
        assert ProcessingPipeline._score_to_severity(0.649) == "medium"

    def test_low_threshold(self):
        from src.pipeline import ProcessingPipeline
        assert ProcessingPipeline._score_to_severity(0.39) == "low"
        assert ProcessingPipeline._score_to_severity(0.0) == "low"

    def test_boundary_values(self):
        from src.pipeline import ProcessingPipeline
        assert ProcessingPipeline._score_to_severity(0.9) == "critical"
        assert ProcessingPipeline._score_to_severity(0.65) == "high"
        assert ProcessingPipeline._score_to_severity(0.4) == "medium"

    def test_behaviour_alert_type_mapping(self):
        from src.pipeline import ProcessingPipeline
        assert ProcessingPipeline._resolve_behaviour_alert_type("fighting") == "fight"
        assert (
            ProcessingPipeline._resolve_behaviour_alert_type("fallen_person")
            == "suspicious_behaviour"
        )

    def test_anomaly_severity_mapping(self):
        from src.pipeline import ProcessingPipeline
        assert ProcessingPipeline._severity_for_anomaly("fire_detected") == "critical"
        assert ProcessingPipeline._severity_for_anomaly("water_leak_detected") == "high"
        assert ProcessingPipeline._severity_for_anomaly("animal_detected") == "medium"


# ---------------------------------------------------------------------------
# ProcessingPipeline construction
# ---------------------------------------------------------------------------

class TestProcessingPipelineInit:
    def test_init_with_no_cameras(self):
        from src.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(config=_make_config())
        assert pipeline._config.venue_name == "Test Venue"

    def test_save_snapshots_default_true(self):
        from src.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(config=_make_config())
        assert pipeline._save_snapshots is True

    def test_save_snapshots_can_be_disabled(self):
        from src.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(config=_make_config(), save_snapshots=False)
        assert pipeline._save_snapshots is False

    def test_snapshot_dir_created_on_init(self):
        from src.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(config=_make_config())
        assert pipeline._snapshot_dir.exists()

    def test_frame_counter_starts_empty(self):
        from src.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(config=_make_config())
        assert pipeline._frame_counter == {}


# ---------------------------------------------------------------------------
# Callback methods
# ---------------------------------------------------------------------------

class TestProcessingPipelineCallbacks:
    def test_on_checkin_logs_person_name(self, caplog):
        from src.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(config=_make_config())
        with caplog.at_level(logging.INFO, logger="src.pipeline"):
            pipeline._on_checkin("Alice", "cam-01", "entrance", datetime.now())
        assert "Alice" in caplog.text

    def test_on_checkout_logs_person_name(self, caplog):
        from src.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(config=_make_config())
        with caplog.at_level(logging.INFO, logger="src.pipeline"):
            pipeline._on_checkout("Bob", "cam-01", "entrance", datetime.now(), 30.0)
        assert "Bob" in caplog.text

    def test_on_alert_dispatched_adds_to_dashboard(self):
        from src.pipeline import ProcessingPipeline
        from src.alerts.alert_manager import Alert
        pipeline = ProcessingPipeline(config=_make_config())
        alert = Alert(
            camera_id="cam-01", zone="entrance",
            alert_type="loitering", severity="medium",
            description="test alert",
        )
        pipeline._on_alert_dispatched(alert)
        assert len(pipeline._dashboard._recent_alerts) == 1
        assert pipeline._dashboard._recent_alerts[0].alert_type == "loitering"

    def test_on_alert_dispatched_persists_to_db(self):
        """_on_alert_dispatched writes the alert to the database."""
        from src.pipeline import ProcessingPipeline
        from src.alerts.alert_manager import Alert
        pipeline = ProcessingPipeline(config=_make_config())
        alert = Alert(
            camera_id="cam-01", zone="parking",
            alert_type="anomaly", severity="high",
            description="vehicle in pedestrian zone",
        )
        pipeline._on_alert_dispatched(alert)
        count = pipeline._db.get_alert_count(acknowledged=False)
        assert count == 1

    def test_check_camera_health_queues_alert_for_offline_camera(self):
        from src.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(config=_make_config())
        pipeline._last_health_check = 0.0
        pipeline._camera_mgr.get_health_snapshots = MagicMock(return_value=[
            type(
                "Health",
                (),
                {
                    "camera_id": "cam-01",
                    "zone": "entrance",
                    "source": "rtsp://example.local/stream",
                    "status": "offline",
                    "reason": "last frame received 30.0s ago",
                },
            )()
        ])
        with patch.object(pipeline._alerts, "build_alert") as build_alert:
            with patch("src.pipeline.time.time", return_value=2.0):
                pipeline._check_camera_health()
        build_alert.assert_called_once()
        kwargs = build_alert.call_args.kwargs
        assert kwargs["alert_type"] == "other"
        assert kwargs["severity"] == "high"


# ---------------------------------------------------------------------------
# _save_snapshot
# ---------------------------------------------------------------------------

class TestSaveSnapshot:
    def test_save_snapshot_without_cv2_returns_none(self):
        """_save_snapshot must return None gracefully when cv2 is absent."""
        import sys
        from src.pipeline import ProcessingPipeline
        from src.camera.camera_manager import Frame
        import numpy as np
        pipeline = ProcessingPipeline(config=_make_config(), save_snapshots=True)
        frame = Frame(
            camera_id="cam-01", zone="entrance",
            data=np.zeros((100, 100, 3), dtype=np.uint8),
        )
        with patch.dict(sys.modules, {"cv2": None}):
            result = pipeline._save_snapshot(frame)
        assert result is None
