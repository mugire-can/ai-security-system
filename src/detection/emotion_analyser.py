"""
Emotion analyser — estimates the emotional state of each detected face.

Uses DeepFace for emotion classification.  Falls back gracefully when
DeepFace is not installed (returns "unknown").

Emotions returned: angry, disgust, fear, happy, sad, surprise, neutral.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from src.detection.person_detector import Detection

logger = logging.getLogger(__name__)

_NEGATIVE_EMOTIONS = {"angry", "disgust", "fear", "sad"}
_HIGH_ALERT_EMOTIONS = {"angry", "fear"}


@dataclass
class EmotionResult:
    """Emotion classification result for a single person/face."""

    camera_id: str
    zone: str
    person_name: Optional[str]
    emotion: str
    confidence: float
    is_negative: bool
    timestamp: float = field(default_factory=time.time)
    bbox: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)


class EmotionAnalyser:
    """
    Analyses the emotional state of faces detected in frames.

    :param frame_interval: Only run heavy analysis every N calls to :meth:`analyse`
                           to reduce CPU/GPU load.
    """

    def __init__(self, frame_interval: int = 5) -> None:
        self._interval = frame_interval
        self._call_count = 0
        self._deepface = None  # lazy import

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def analyse(
        self,
        frame: np.ndarray,
        detections: List[Detection],
    ) -> List[EmotionResult]:
        """
        Return one :class:`EmotionResult` per person detection.

        Analysis is performed only every :attr:`_interval` calls to avoid
        overloading the CPU.
        """
        self._call_count += 1
        if self._call_count % self._interval != 0:
            return []

        people = [d for d in detections if d.object_type == "person"]
        results: List[EmotionResult] = []

        for det in people:
            emotion, conf = self._analyse_face(frame, det)
            results.append(
                EmotionResult(
                    camera_id=det.camera_id,
                    zone=det.zone,
                    person_name=det.person_name,
                    emotion=emotion,
                    confidence=conf,
                    is_negative=emotion in _NEGATIVE_EMOTIONS,
                    bbox=det.bbox.as_tuple() if det.bbox else None,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _analyse_face(self, frame: np.ndarray, det: Detection) -> Tuple[str, float]:
        """
        Crop the face region from *frame* and classify the emotion.

        Falls back to ("unknown", 0.0) on any error.
        """
        df = self._get_deepface()
        if df is None or det.bbox is None:
            return "unknown", 0.0

        bx, by, bw, bh = det.bbox.as_tuple()
        # Add padding around face for better recognition
        pad = int(min(bw, bh) * 0.15)
        h_img, w_img = frame.shape[:2]
        x1 = max(0, bx - pad)
        y1 = max(0, by - pad)
        x2 = min(w_img, bx + bw + pad)
        y2 = min(h_img, by + bh + pad)
        face_crop = frame[y1:y2, x1:x2]

        if face_crop.size == 0:
            return "unknown", 0.0

        try:
            analysis = df.analyze(
                face_crop,
                actions=["emotion"],
                enforce_detection=False,
                silent=True,
            )
            if isinstance(analysis, list):
                analysis = analysis[0]
            dominant = analysis.get("dominant_emotion", "unknown")
            conf = analysis.get("emotion", {}).get(dominant, 0.0) / 100.0
            return dominant, conf
        except Exception as exc:
            logger.debug("Emotion analysis failed for %s: %s", det.person_name, exc)
            return "unknown", 0.0

    def _get_deepface(self):
        if self._deepface is None:
            try:
                from deepface import DeepFace

                self._deepface = DeepFace
            except ImportError:
                logger.warning(
                    "DeepFace not installed — emotion analysis disabled. "
                    "Run: pip install deepface"
                )
        return self._deepface
