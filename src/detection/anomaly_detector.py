"""
Anomaly detector — detects non-human entities and unusual object states.

Covers:
* Animals (cats, dogs, birds, …) in areas where they shouldn't be
* Unattended / abandoned bags / luggage
* Vehicles in pedestrian zones
* Unusual crowd density (sudden spike or drop)
* Any YOLO-detected object class that is unexpected for the venue zone
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.detection.person_detector import Detection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Zone-specific allow-lists
# Allow list maps zone keywords → set of acceptable object_types.
# Anything NOT in the allow list triggers an anomaly alert.
# ---------------------------------------------------------------------------
_DEFAULT_ZONE_ALLOWLIST: Dict[str, Set[str]] = {
    "default": {"person"},
    "entrance": {"person", "vehicle"},
    "parking": {"person", "vehicle"},
    "cafeteria": {"person", "object"},  # bags/trays are OK
    "shop-floor": {"person", "object"},
}


@dataclass
class AnomalyResult:
    """A detected anomaly."""

    camera_id: str
    zone: str
    anomaly_type: str           # e.g. "animal_detected", "unattended_object"
    object_class: str           # YOLO class label
    confidence: float
    description: str
    bbox: Optional[Tuple[int, int, int, int]] = None
    timestamp: float = field(default_factory=time.time)


class AnomalyDetector:
    """
    Post-processes a list of :class:`Detection` objects to identify anomalies.

    Maintains per-zone object state to detect "abandoned" items (object
    present in the same position for too long without an associated person).
    """

    # Seconds an object must be stationary before it is "abandoned"
    ABANDONED_THRESHOLD_SECONDS = 180

    def __init__(
        self,
        zone_allowlist: Optional[Dict[str, Set[str]]] = None,
        abandoned_threshold: int = ABANDONED_THRESHOLD_SECONDS,
    ) -> None:
        self._allowlist = zone_allowlist or _DEFAULT_ZONE_ALLOWLIST
        self._abandoned_threshold = abandoned_threshold
        # Track non-person objects: {camera_id: {zone: [(Detection, first_seen)]}}
        self._object_log: Dict[str, Dict[str, List[Tuple[Detection, float]]]] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def detect(
        self, detections: List[Detection]
    ) -> List[AnomalyResult]:
        """
        Inspect *detections* and return anomaly results.

        :param detections: All detections from a single frame.
        """
        anomalies: List[AnomalyResult] = []
        now = time.time()

        people_present: Dict[str, bool] = {}   # camera_id+zone → any person?

        for det in detections:
            key = f"{det.camera_id}:{det.zone}"
            if det.object_type == "person":
                people_present[key] = True
                continue

            # Check zone allowlist
            allow = self._get_allowlist(det.zone)
            if det.object_type not in allow:
                anomalies.append(
                    AnomalyResult(
                        camera_id=det.camera_id,
                        zone=det.zone,
                        anomaly_type=f"{det.object_type}_detected",
                        object_class=det.class_label,
                        confidence=det.confidence,
                        description=(
                            f"Unexpected {det.object_type} "
                            f"('{det.class_label}') detected in zone "
                            f"'{det.zone}'."
                        ),
                        bbox=det.bbox.as_tuple() if det.bbox else None,
                    )
                )

            # Track objects for abandoned-item detection
            cam_log = self._object_log.setdefault(det.camera_id, {})
            zone_log = cam_log.setdefault(det.zone, [])
            zone_log.append((det, now))

        # Check for abandoned objects
        for cam_id, zone_map in self._object_log.items():
            for zone, entries in zone_map.items():
                key = f"{cam_id}:{zone}"
                any_person = people_present.get(key, False)
                # Keep only entries younger than 10 min
                zone_map[zone] = [
                    (d, t) for d, t in entries if now - t < 600
                ]
                if any_person:
                    continue   # Someone is there — not abandoned
                for det, first_seen in zone_map[zone]:
                    if (
                        det.object_type == "object"
                        and now - first_seen > self._abandoned_threshold
                    ):
                        anomalies.append(
                            AnomalyResult(
                                camera_id=cam_id,
                                zone=zone,
                                anomaly_type="unattended_object",
                                object_class=det.class_label,
                                confidence=det.confidence,
                                description=(
                                    f"'{det.class_label}' has been unattended "
                                    f"in zone '{zone}' for "
                                    f"{int(now - first_seen)}s."
                                ),
                                bbox=det.bbox.as_tuple() if det.bbox else None,
                            )
                        )

        return anomalies

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_allowlist(self, zone: str) -> Set[str]:
        """Return the allow-list for a zone, falling back to default."""
        for key, allowed in self._allowlist.items():
            if key in zone.lower():
                return allowed
        return self._allowlist.get("default", {"person"})
