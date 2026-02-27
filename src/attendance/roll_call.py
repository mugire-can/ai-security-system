"""
Face-recognition based roll-call and attendance tracker.

How it works
------------
1. On startup, :class:`RollCall` loads face encodings from
   ``known_faces_dir``.  Each sub-directory is named after the person,
   and contains one or more reference images.
2. During processing, :meth:`RollCall.identify` compares an incoming
   detection crop against the database.
3. :class:`AttendanceTracker` records check-in / check-out times per
   individual per day.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class IdentityResult:
    """Face recognition result for a single detection crop."""

    name: str                   # "Unknown" when not recognised
    confidence: float           # 0–1, higher is better
    is_known: bool


class RollCall:
    """
    Loads known face encodings and identifies people in frame crops.

    Dependencies: ``face_recognition`` library (dlib-based).
    Falls back to "Unknown" if the library is not installed.
    """

    UNKNOWN = "Unknown"

    def __init__(
        self,
        known_faces_dir: str,
        tolerance: float = 0.5,
    ) -> None:
        self._tolerance = tolerance
        self._known_encodings: Dict[str, list] = {}  # name → [encoding]
        self._fr = None   # lazy import
        self._load_known_faces(known_faces_dir)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def identify(
        self,
        frame_crop: np.ndarray,
    ) -> IdentityResult:
        """
        Identify a face in *frame_crop*.

        *frame_crop* should be a BGR numpy array cropped to the face region.
        """
        fr = self._get_fr()
        if fr is None or not self._known_encodings:
            return IdentityResult(name=self.UNKNOWN, confidence=0.0, is_known=False)

        # face_recognition uses RGB
        try:
            rgb = frame_crop[:, :, ::-1]
            locs = fr.face_locations(rgb, model="hog")
            if not locs:
                return IdentityResult(
                    name=self.UNKNOWN, confidence=0.0, is_known=False
                )
            enc = fr.face_encodings(rgb, locs)[0]
        except Exception as exc:
            logger.debug("face_recognition error: %s", exc)
            return IdentityResult(name=self.UNKNOWN, confidence=0.0, is_known=False)

        best_name = self.UNKNOWN
        best_dist = float("inf")
        for name, encodings in self._known_encodings.items():
            distances = fr.face_distance(encodings, enc)
            min_dist = float(np.min(distances))
            if min_dist < best_dist:
                best_dist = min_dist
                best_name = name

        if best_dist > self._tolerance:
            return IdentityResult(name=self.UNKNOWN, confidence=0.0, is_known=False)

        confidence = max(0.0, 1.0 - best_dist / self._tolerance)
        return IdentityResult(name=best_name, confidence=confidence, is_known=True)

    @property
    def registered_names(self) -> List[str]:
        return list(self._known_encodings.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_known_faces(self, known_faces_dir: str) -> None:
        fr = self._get_fr()
        if fr is None:
            logger.warning(
                "face_recognition not installed — roll-call disabled. "
                "Run: pip install face-recognition"
            )
            return

        base = Path(known_faces_dir)
        if not base.is_dir():
            logger.warning("Known faces directory not found: %s", base)
            return

        loaded = 0
        for person_dir in sorted(base.iterdir()):
            if not person_dir.is_dir():
                continue
            name = person_dir.name
            encodings = []
            for img_file in person_dir.iterdir():
                if img_file.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                    continue
                try:
                    import cv2
                    img = cv2.imread(str(img_file))
                    if img is None:
                        continue
                    rgb = img[:, :, ::-1]
                    encs = fr.face_encodings(rgb)
                    if encs:
                        encodings.extend(encs)
                except Exception as exc:
                    logger.warning(
                        "Could not encode face from %s: %s", img_file, exc
                    )
            if encodings:
                self._known_encodings[name] = encodings
                loaded += 1

        logger.info(
            "Loaded face encodings for %d people from %s", loaded, base
        )

    def _get_fr(self):
        if self._fr is None:
            try:
                import face_recognition
                self._fr = face_recognition
            except ImportError:
                pass
        return self._fr
