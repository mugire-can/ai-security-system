"""
Tests for AnomalyDetector.
"""

import time

import pytest

from src.detection.anomaly_detector import AnomalyDetector
from src.detection.person_detector import BoundingBox, Detection


def _make_detection(
    object_type: str,
    class_label: str,
    zone: str = "classroom",
    camera_id: str = "cam-01",
    confidence: float = 0.8,
) -> Detection:
    return Detection(
        camera_id=camera_id,
        zone=zone,
        object_type=object_type,
        class_label=class_label,
        confidence=confidence,
        bbox=BoundingBox(x=100, y=100, w=50, h=80),
    )


class TestAnomalyDetector:
    def setup_method(self):
        self.detector = AnomalyDetector()

    def test_person_in_default_zone_no_anomaly(self):
        det = _make_detection("person", "person", zone="classroom")
        anomalies = self.detector.detect([det])
        assert anomalies == []

    def test_animal_in_classroom_is_anomaly(self):
        det = _make_detection("animal", "dog", zone="classroom")
        anomalies = self.detector.detect([det])
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "animal_detected"
        assert anomalies[0].object_class == "dog"

    def test_vehicle_in_classroom_is_anomaly(self):
        det = _make_detection("vehicle", "car", zone="classroom")
        anomalies = self.detector.detect([det])
        assert any(
            a.object_type if hasattr(a, "object_type") else a.anomaly_type for a in anomalies
        )

    def test_vehicle_in_entrance_allowed(self):
        det = _make_detection("vehicle", "car", zone="entrance")
        anomalies = self.detector.detect([det])
        # 'entrance' allowlist includes vehicles
        vehicle_anomalies = [a for a in anomalies if "vehicle" in a.anomaly_type]
        assert vehicle_anomalies == []

    def test_animal_in_parking_is_anomaly(self):
        det = _make_detection("animal", "cat", zone="parking")
        anomalies = self.detector.detect([det])
        assert any(a.anomaly_type == "animal_detected" for a in anomalies)

    def test_no_anomaly_for_object_in_cafeteria(self):
        det = _make_detection("object", "backpack", zone="cafeteria")
        anomalies = self.detector.detect([det])
        # 'object' is allowed in cafeteria
        obj_anomalies = [a for a in anomalies if "unattended" not in a.anomaly_type]
        assert obj_anomalies == []

    def test_multiple_anomalies_in_one_frame(self):
        dets = [
            _make_detection("animal", "dog", zone="library"),
            _make_detection("vehicle", "car", zone="library"),
        ]
        anomalies = self.detector.detect(dets)
        assert len(anomalies) >= 2

    def test_confidence_preserved_in_anomaly(self):
        det = _make_detection("animal", "bird", zone="office", confidence=0.72)
        anomalies = self.detector.detect([det])
        assert anomalies[0].confidence == pytest.approx(0.72)

    def test_description_contains_zone(self):
        det = _make_detection("animal", "horse", zone="server-room")
        anomalies = self.detector.detect([det])
        assert "server-room" in anomalies[0].description

    def test_empty_detections_returns_empty(self):
        anomalies = self.detector.detect([])
        assert anomalies == []

    def test_fire_label_creates_facility_anomaly(self):
        det = _make_detection("facility_hazard", "fire", zone="server-room")
        anomalies = self.detector.detect([det])
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "fire_detected"

    def test_water_leak_label_creates_facility_anomaly(self):
        det = _make_detection("facility_hazard", "water_leak", zone="basement")
        anomalies = self.detector.detect([det])
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "water_leak_detected"

    def test_electrical_label_creates_hazard_anomaly(self):
        det = _make_detection("facility_hazard", "electrical_spark", zone="lab")
        anomalies = self.detector.detect([det])
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "electrical_hazard_detected"

    def test_weapon_label_creates_threat_anomaly(self):
        det = _make_detection("threat", "knife", zone="entrance")
        anomalies = self.detector.detect([det])
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "weapon_detected"

    def test_fallen_person_label_creates_accident_anomaly(self):
        det = _make_detection("person_incident", "fallen_person", zone="corridor")
        anomalies = self.detector.detect([det])
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "person_down_detected"
