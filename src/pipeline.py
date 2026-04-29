"""
Central processing pipeline.

Ties all subsystems together:
  CameraManager → PersonDetector → BehaviourAnalyser
                                 → EmotionAnalyser
                                 → AnomalyDetector
                                 → RollCall / AttendanceTracker
                                 → AlertManager
                                 → DatabaseManager
                                 → AdminDashboard

One :class:`ProcessingPipeline` instance is shared across all camera streams.
"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np

from config.settings import AppConfig
from src.alerts.alert_manager import Alert, AlertManager
from src.attendance.roll_call import RollCall
from src.attendance.time_tracker import AttendanceTracker
from src.camera.camera_manager import CameraManager, Frame
from src.dashboard.admin_dashboard import AdminDashboard
from src.database.db_manager import (
    AlertRecord,
    AnomalyEvent,
    AttendanceRecord,
    BehaviourEvent,
    DatabaseManager,
    DetectionEvent,
)
from src.detection.anomaly_detector import AnomalyDetector, AnomalyResult
from src.detection.behaviour_analyser import BehaviourAnalyser, BehaviourResult
from src.detection.emotion_analyser import EmotionAnalyser
from src.detection.person_detector import Detection, PersonDetector

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """
    Wires all subsystems together and drives the main processing loop.

    Parameters
    ----------
    config : AppConfig
        Full application configuration.
    save_snapshots : bool
        When True, suspicious-behaviour frames are saved as JPEG snapshots.
    """

    def __init__(
        self,
        config: AppConfig,
        save_snapshots: bool = True,
    ) -> None:
        self._config = config
        self._save_snapshots = save_snapshots

        # Subsystems
        self._camera_mgr = CameraManager(config.cameras)
        self._detector = PersonDetector(
            model_path=config.detection.yolo_model,
            confidence_threshold=config.detection.person_confidence_threshold,
        )
        self._behaviour = BehaviourAnalyser(
            confidence_threshold=config.detection.behaviour_confidence_threshold,
            loitering_threshold_seconds=config.detection.loitering_threshold_seconds,
        )
        self._emotion = EmotionAnalyser(
            frame_interval=config.detection.analysis_frame_interval,
        )
        self._anomaly = AnomalyDetector()
        self._roll_call = RollCall(
            known_faces_dir=config.attendance.known_faces_dir,
            tolerance=config.detection.face_recognition_tolerance,
        )
        self._tracker = AttendanceTracker(
            work_start=config.attendance.work_start_time,
            work_end=config.attendance.work_end_time,
            on_checkin=self._on_checkin,
            on_checkout=self._on_checkout,
        )
        self._alerts = AlertManager(
            config=config.alert,
            on_alert=self._on_alert_dispatched,
        )
        self._db = DatabaseManager(config.database.db_url)
        self._dashboard = AdminDashboard(venue_name=config.venue_name)

        # Snapshot directory
        self._snapshot_dir = Path("data/snapshots")
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Frame counter for sub-sampling heavy analysis
        self._frame_counter: dict = {}
        self._last_health_check = 0.0
        self._camera_health_state: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start all cameras and run the processing loop (blocking)."""
        self._camera_mgr.start_all()
        logger.info(
            "Pipeline started for venue '%s' (%s)",
            self._config.venue_name,
            self._config.venue_type.value,
        )
        try:
            self._loop()
        finally:
            self._camera_mgr.stop_all()
            logger.info("Pipeline stopped.")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while True:
            frames = self._camera_mgr.read_all_frames(timeout=0.05)
            self._check_camera_health()
            if not frames:
                time.sleep(0.01)
                continue

            person_count_total = 0
            anomaly_count_total = 0

            for frame in frames:
                p, a = self._process_frame(frame)
                person_count_total += p
                anomaly_count_total += a

            # Update dashboard
            self._dashboard.update_cameras(self._camera_mgr.active_camera_ids)
            self._dashboard.update_counts(person_count_total, anomaly_count_total)
            self._dashboard.update_attendance(self._tracker.get_today_summary())

    def _process_frame(self, frame: Frame) -> tuple[int, int]:
        """
        Full processing of a single video frame.

        Returns ``(person_count, anomaly_count)``.
        """
        cnt = self._frame_counter.get(frame.camera_id, 0) + 1
        self._frame_counter[frame.camera_id] = cnt

        # 1. Object detection
        detections: List[Detection] = self._detector.detect(frame.data, frame.camera_id, frame.zone)

        # 2. Face recognition — only every N frames (expensive)
        if cnt % self._config.detection.analysis_frame_interval == 0:
            self._identify_people(frame, detections)

        # 3. Attendance tracking
        for det in detections:
            if det.object_type == "person" and det.person_name:
                self._tracker.record_sighting(det.person_name, frame.camera_id, frame.zone)

        # 4. Behaviour analysis
        behaviours: List[BehaviourResult] = self._behaviour.analyse(detections, frame.data)
        for beh in behaviours:
            if beh.is_suspicious:
                self._handle_suspicious_behaviour(beh, frame)
            self._persist_behaviour(beh)

        # 5. Emotion analysis
        emotions = self._emotion.analyse(frame.data, detections)

        # 6. Anomaly detection
        anomalies = self._anomaly.detect(detections)
        for anm in anomalies:
            self._handle_anomaly(anm, frame)
            self._persist_anomaly(anm)

        # 7. Persist detections
        for det in detections:
            self._persist_detection(det)

        person_count = sum(1 for d in detections if d.object_type == "person")
        return person_count, len(anomalies)

    # ------------------------------------------------------------------
    # Face recognition
    # ------------------------------------------------------------------

    def _identify_people(self, frame: Frame, detections: List[Detection]) -> None:
        for det in detections:
            if det.object_type != "person" or det.bbox is None:
                continue
            bx, by, bw, bh = det.bbox.as_tuple()
            crop = frame.data[by : by + bh, bx : bx + bw]
            if crop.size == 0:
                continue
            result = self._roll_call.identify(crop)
            if result.is_known:
                det.person_name = result.name

    # ------------------------------------------------------------------
    # Alerting
    # ------------------------------------------------------------------

    def _handle_suspicious_behaviour(self, beh: BehaviourResult, frame: Frame) -> None:
        snapshot = self._save_snapshot(frame) if self._save_snapshots else None
        self._alerts.build_alert(
            camera_id=frame.camera_id,
            zone=frame.zone,
            alert_type=self._resolve_behaviour_alert_type(beh.activity),
            description=(
                f"{beh.activity.replace('_', ' ').title()} detected. "
                f"Suspicion score: {beh.suspicion_score:.0%}. "
                f"{beh.notes}"
            ),
            severity=self._score_to_severity(beh.suspicion_score),
            person_name=beh.detection.person_name,
            snapshot_path=str(snapshot) if snapshot else None,
        )

    def _handle_anomaly(self, anm: AnomalyResult, frame: Frame) -> None:
        snapshot = self._save_snapshot(frame) if self._save_snapshots else None
        self._alerts.build_alert(
            camera_id=anm.camera_id,
            zone=anm.zone,
            alert_type=self._resolve_anomaly_alert_type(anm.anomaly_type),
            description=anm.description,
            severity=self._severity_for_anomaly(anm.anomaly_type),
            snapshot_path=str(snapshot) if snapshot else None,
        )

    # ------------------------------------------------------------------
    # Dashboard callbacks
    # ------------------------------------------------------------------

    def _on_alert_dispatched(self, alert: Alert) -> None:
        self._dashboard.add_alert(alert)
        self._persist_alert(alert)

    def _on_checkin(self, name: str, camera_id: str, zone: str, ts: datetime) -> None:
        logger.info("Check-in: %s at %s", name, ts.strftime("%H:%M:%S"))

    def _on_checkout(self, name: str, camera_id: str, zone: str, ts: datetime, dur: float) -> None:
        logger.info("Check-out: %s at %s (%.0f min)", name, ts.strftime("%H:%M:%S"), dur)

    # ------------------------------------------------------------------
    # Snapshot saving
    # ------------------------------------------------------------------

    def _save_snapshot(self, frame: Frame) -> Optional[Path]:
        try:
            import cv2

            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = self._snapshot_dir / f"{frame.camera_id}_{ts}.jpg"
            cv2.imwrite(str(path), frame.data)
            return path
        except Exception as exc:
            logger.warning("Could not save snapshot: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _persist_detection(self, det: Detection) -> None:
        with self._db.session() as s:
            rec = DetectionEvent(
                camera_id=det.camera_id,
                zone=det.zone,
                object_type=det.object_type,
                track_id=det.track_id,
                person_name=det.person_name,
                confidence=det.confidence,
                bbox_x=det.bbox.x if det.bbox else None,
                bbox_y=det.bbox.y if det.bbox else None,
                bbox_w=det.bbox.w if det.bbox else None,
                bbox_h=det.bbox.h if det.bbox else None,
            )
            s.add(rec)
            s.commit()

    def _persist_behaviour(self, beh: BehaviourResult) -> None:
        with self._db.session() as s:
            rec = BehaviourEvent(
                detection_id=0,
                camera_id=beh.detection.camera_id,
                zone=beh.detection.zone,
                person_name=beh.detection.person_name,
                activity=beh.activity,
                suspicion_score=beh.suspicion_score,
                is_suspicious=beh.is_suspicious,
                notes=beh.notes,
            )
            s.add(rec)
            s.commit()

    def _persist_anomaly(self, anm: AnomalyResult) -> None:
        with self._db.session() as s:
            rec = AnomalyEvent(
                camera_id=anm.camera_id,
                zone=anm.zone,
                anomaly_type=anm.anomaly_type,
                object_class=anm.object_class,
                confidence=anm.confidence,
                description=anm.description,
                snapshot_path=None,
            )
            s.add(rec)
            s.commit()

    def _persist_alert(self, alert: Alert) -> None:
        with self._db.session() as s:
            rec = AlertRecord(
                camera_id=alert.camera_id,
                zone=alert.zone,
                person_name=alert.person_name,
                alert_type=alert.alert_type,
                severity=alert.severity,
                description=alert.description,
                snapshot_path=alert.snapshot_path,
                sent=True,
            )
            s.add(rec)
            s.commit()

    # ------------------------------------------------------------------
    # Camera health
    # ------------------------------------------------------------------

    def _check_camera_health(self) -> None:
        now = time.time()
        if now - self._last_health_check < 1.0:
            return
        self._last_health_check = now

        for snapshot in self._camera_mgr.get_health_snapshots(
            stall_seconds=self._config.health.camera_stall_seconds,
            max_consecutive_failures=(self._config.health.max_consecutive_read_failures),
        ):
            previous = self._camera_health_state.get(snapshot.camera_id)
            self._camera_health_state[snapshot.camera_id] = snapshot.status

            if snapshot.status in {"healthy", "starting"}:
                continue
            if previous == snapshot.status:
                continue

            severity = "high" if snapshot.status == "offline" else "medium"
            self._alerts.build_alert(
                camera_id=snapshot.camera_id,
                zone=snapshot.zone,
                alert_type="other",
                severity=severity,
                description=(
                    f"Camera health issue: {snapshot.reason}. " f"Source={snapshot.source}"
                ),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_to_severity(score: float) -> str:
        if score >= 0.9:
            return "critical"
        if score >= 0.65:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _resolve_behaviour_alert_type(activity: str) -> str:
        if activity == "fighting":
            return "fight"
        if activity == "loitering":
            return "loitering"
        return "suspicious_behaviour"

    @staticmethod
    def _resolve_anomaly_alert_type(anomaly_type: str) -> str:
        if anomaly_type == "weapon_detected":
            return "intrusion"
        return "anomaly"

    @staticmethod
    def _severity_for_anomaly(anomaly_type: str) -> str:
        critical = {
            "fire_detected",
            "electrical_hazard_detected",
            "weapon_detected",
            "person_down_detected",
        }
        high = {
            "smoke_detected",
            "water_leak_detected",
            "facility_hazard_detected",
            "security_threat_detected",
            "unattended_object",
        }

        if anomaly_type in critical:
            return "critical"
        if anomaly_type in high:
            return "high"
        return "medium"
