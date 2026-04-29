"""
Person & object detector using YOLOv8.

Detects:
* People (with optional face-recognition for identity)
* Animals
* Vehicles
* Common objects (bags, packages, …)

Returns structured :class:`Detection` objects that downstream analysers consume.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# COCO class indices we care about
_PERSON_CLASS_ID = 0
_ANIMAL_CLASS_IDS = {
    14,  # bird
    15,  # cat
    16,  # dog
    17,  # horse
    18,  # sheep
    19,  # cow
    20,  # elephant
    21,  # bear
    22,  # zebra
    23,  # giraffe
}
_VEHICLE_CLASS_IDS = {
    1,  # bicycle
    2,  # car
    3,  # motorcycle
    5,  # bus
    7,  # truck
}
_OBJECT_CLASS_IDS = {
    24,  # backpack
    26,  # handbag
    28,  # suitcase
}
_FACILITY_HAZARD_KEYWORDS = {
    "fire",
    "flame",
    "smoke",
    "water_leak",
    "water leak",
    "leak",
    "flood",
    "spill",
    "electrical",
    "spark",
    "short_circuit",
    "arc_flash",
}
_THREAT_KEYWORDS = {
    "weapon",
    "gun",
    "knife",
    "rifle",
    "pistol",
    "blade",
}
_PERSON_INCIDENT_KEYWORDS = {
    "fallen_person",
    "person_down",
    "fall",
    "slip",
    "accident",
    "injury",
}


@dataclass
class BoundingBox:
    x: int
    y: int
    w: int
    h: int

    @property
    def area(self) -> int:
        return self.w * self.h

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return self.x, self.y, self.w, self.h

    def centre(self) -> Tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


@dataclass
class Detection:
    """A single detected object in a frame."""

    camera_id: str
    zone: str
    timestamp: float = field(default_factory=time.time)
    object_type: str = "unknown"  # "person", "animal", "vehicle", "object", ...
    class_label: str = "unknown"  # YOLO class name
    confidence: float = 0.0
    bbox: Optional[BoundingBox] = None
    track_id: Optional[str] = None
    person_name: Optional[str] = None  # filled by face recogniser


class PersonDetector:
    """
    Wraps a YOLOv8 model to detect people and objects in frames.

    The heavy model is loaded lazily on first call to :meth:`detect` so that
    the process starts quickly even when a GPU is unavailable.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.55,
    ) -> None:
        self._model_path = model_path
        self._threshold = confidence_threshold
        self._model = None  # lazy load

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray, camera_id: str, zone: str) -> List[Detection]:
        """
        Run object detection on *frame*.

        Returns a list of :class:`Detection` objects for every detected entity
        that exceeds :attr:`_threshold`.
        """
        model = self._get_model()
        if model is None:
            return []

        try:
            results = model(frame, verbose=False)[0]
        except Exception as exc:
            logger.error("YOLO inference error: %s", exc)
            return []

        detections: List[Detection] = []
        for box in results.boxes:
            conf = float(box.conf[0])
            if conf < self._threshold:
                continue

            cls_id = int(box.cls[0])
            cls_label = results.names.get(cls_id, str(cls_id))
            xywh = box.xywhn[0].tolist()  # normalised cx,cy,w,h

            h_img, w_img = frame.shape[:2]
            bw = int(xywh[2] * w_img)
            bh = int(xywh[3] * h_img)
            bbox = BoundingBox(
                x=int(xywh[0] * w_img) - bw // 2,
                y=int(xywh[1] * h_img) - bh // 2,
                w=bw,
                h=bh,
            )

            obj_type = self._classify_type(cls_id, cls_label)

            det = Detection(
                camera_id=camera_id,
                zone=zone,
                object_type=obj_type,
                class_label=cls_label,
                confidence=conf,
                bbox=bbox,
            )
            detections.append(det)

        return detections

    def draw_detections(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """Draw bounding boxes and labels onto *frame* (returns a copy)."""
        out = frame.copy()
        colour_map = {
            "person": (0, 255, 0),
            "animal": (255, 128, 0),
            "vehicle": (0, 128, 255),
            "object": (200, 200, 0),
            "unknown": (128, 128, 128),
        }
        for det in detections:
            if det.bbox is None:
                continue
            colour = colour_map.get(det.object_type, (128, 128, 128))
            bx, by, bw, bh = det.bbox.as_tuple()
            cv2 = _lazy_cv2()
            if cv2:
                label = f"{det.person_name or det.class_label} " f"({det.confidence:.0%})"
                cv2.rectangle(out, (bx, by), (bx + bw, by + bh), colour, 2)
                cv2.putText(
                    out,
                    label,
                    (bx, by - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    colour,
                    2,
                )
        return out

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model(self):
        if self._model is None:
            try:
                from ultralytics import YOLO

                self._model = YOLO(self._model_path)
                logger.info("YOLO model loaded: %s", self._model_path)
            except Exception as exc:
                logger.error(
                    "Cannot load YOLO model '%s': %s. " "Detections will be skipped.",
                    self._model_path,
                    exc,
                )
        return self._model

    @staticmethod
    def _classify_type(cls_id: int, cls_label: str) -> str:
        label = cls_label.lower().replace("-", "_")
        if cls_id == _PERSON_CLASS_ID:
            return "person"
        if cls_id in _ANIMAL_CLASS_IDS:
            return "animal"
        if cls_id in _VEHICLE_CLASS_IDS:
            return "vehicle"
        if cls_id in _OBJECT_CLASS_IDS:
            return "object"
        if any(keyword in label for keyword in _FACILITY_HAZARD_KEYWORDS):
            return "facility_hazard"
        if any(keyword in label for keyword in _THREAT_KEYWORDS):
            return "threat"
        if any(keyword in label for keyword in _PERSON_INCIDENT_KEYWORDS):
            return "person_incident"
        return "unknown"


def _lazy_cv2():
    """Import cv2 only when needed (so tests can run without it)."""
    try:
        import cv2

        return cv2
    except ImportError:
        return None
