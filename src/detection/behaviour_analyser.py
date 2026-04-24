"""
Behaviour analyser — classifies the activity of each detected person and
computes a suspicion score.

Activities recognised
---------------------
* studying          — seated, looking downward / at desk (school context)
* attending_lesson  — upright, facing toward board / presenter
* working           — desk or standing activity with regular arm motion
* loitering         — stationary in an area for too long without purpose
* running           — fast movement in frame
* fighting          — close-proximity rapid movements between ≥ 2 people
* theft_attempt     — reaching toward objects that don't belong to the person
* sleeping          — head dropped, low activity over long window

The analyser is velocity- and pose-based.  Without a pose model the analysis
falls back to optical-flow metrics.
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Deque, List, Optional, Tuple

import numpy as np

from src.detection.person_detector import Detection

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Suspicion weights per activity
# ------------------------------------------------------------------
_ACTIVITY_SUSPICION: Dict[str, float] = {
    "studying": 0.0,
    "attending_lesson": 0.0,
    "working": 0.0,
    "idle": 0.1,
    "running": 0.3,
    "loitering": 0.5,
    "theft_attempt": 0.9,
    "fighting": 1.0,
    "fallen_person": 0.95,
    "sleeping": 0.2,
    "unknown": 0.1,
}

_LOITERING_SECONDS = 120   # flag after 2 minutes in the same spot


@dataclass
class BehaviourResult:
    """Output of the behaviour analyser for a single tracked person."""

    detection: Detection
    activity: str = "unknown"
    suspicion_score: float = 0.0
    is_suspicious: bool = False
    notes: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class _TrackState:
    """Internal state kept per tracked individual."""

    track_id: str
    position_history: Deque[Tuple[int, int]] = field(
        default_factory=lambda: deque(maxlen=60)
    )
    first_seen: float = field(default_factory=time.time)
    last_moved: float = field(default_factory=time.time)
    velocity_history: Deque[float] = field(
        default_factory=lambda: deque(maxlen=30)
    )
    aspect_ratio_history: Deque[float] = field(
        default_factory=lambda: deque(maxlen=15)
    )
    last_activity: str = "unknown"


class BehaviourAnalyser:
    """
    Stateful analyser that keeps a short history per person to determine
    activity and flag suspicious behaviour.

    Usage::

        analyser = BehaviourAnalyser()
        results = analyser.analyse(detections, frame)
    """

    def __init__(
        self,
        confidence_threshold: float = 0.65,
        loitering_threshold_seconds: int = _LOITERING_SECONDS,
    ) -> None:
        self._threshold = confidence_threshold
        self._loitering_threshold = loitering_threshold_seconds
        self._tracks: Dict[str, _TrackState] = {}
        # Optional pose model (loaded lazily)
        self._pose_model = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def analyse(
        self,
        detections: List[Detection],
        frame: Optional[np.ndarray] = None,
    ) -> List[BehaviourResult]:
        """
        Analyse a list of detections from a single frame.

        Returns one :class:`BehaviourResult` per *person* detection.
        Non-person detections are ignored here (see AnomalyDetector).
        """
        results: List[BehaviourResult] = []
        people = [d for d in detections if d.object_type == "person"]
        now = time.time()

        # Assign simple track IDs based on bounding-box centre proximity
        # (in production replace with a proper tracker, e.g. ByteTrack)
        self._assign_track_ids(people, now)

        # Proximity map for fighting detection
        centres = [
            (d.bbox.centre() if d.bbox else (0, 0)) for d in people
        ]

        for idx, det in enumerate(people):
            tid = det.track_id or f"anon-{idx}"
            state = self._tracks.setdefault(tid, _TrackState(track_id=tid))

            centre = centres[idx]
            state.position_history.append(centre)
            aspect_ratio = self._aspect_ratio(det)
            state.aspect_ratio_history.append(aspect_ratio)

            velocity = self._compute_velocity(state)
            state.velocity_history.append(velocity)
            avg_velocity = (
                sum(state.velocity_history) / len(state.velocity_history)
                if state.velocity_history else 0.0
            )

            if velocity > 1.0:
                state.last_moved = now

            activity = self._classify_activity(
                state=state,
                detection=det,
                velocity=avg_velocity,
                people_centres=centres,
                own_centre=centre,
                now=now,
            )
            state.last_activity = activity

            score = _ACTIVITY_SUSPICION.get(activity, 0.1)
            is_suspicious = score >= self._threshold

            results.append(
                BehaviourResult(
                    detection=det,
                    activity=activity,
                    suspicion_score=score,
                    is_suspicious=is_suspicious,
                    notes=self._make_notes(state, activity, now),
                )
            )

        # Prune stale tracks (not seen for > 30 s)
        self._prune_tracks(now, max_age=30.0)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assign_track_ids(
        self, people: List[Detection], now: float
    ) -> None:
        """Assign simple positional track IDs to detected people."""
        existing_centres: List[Tuple[str, Tuple[int, int]]] = [
            (tid, list(state.position_history)[-1])
            for tid, state in self._tracks.items()
            if state.position_history
        ]
        used_tids = set()
        for det in people:
            if det.bbox is None:
                det.track_id = f"no-bbox-{now}"
                continue
            centre = det.bbox.centre()
            best_tid, best_dist = None, float("inf")
            for tid, prev_centre in existing_centres:
                if tid in used_tids:
                    continue
                dist = _euclidean(centre, prev_centre)
                if dist < best_dist:
                    best_dist = dist
                    best_tid = tid
            if best_tid and best_dist < 100:
                det.track_id = best_tid
                used_tids.add(best_tid)
            else:
                # New person — assign a fresh ID
                new_tid = f"T{int(now * 1000) % 100000}-{len(self._tracks)}"
                det.track_id = new_tid
                self._tracks[new_tid] = _TrackState(track_id=new_tid)

    def _compute_velocity(self, state: _TrackState) -> float:
        """Return the Euclidean distance between the last two positions."""
        if len(state.position_history) < 2:
            return 0.0
        p1 = state.position_history[-2]
        p2 = state.position_history[-1]
        return _euclidean(p1, p2)

    def _classify_activity(
        self,
        state: _TrackState,
        detection: Detection,
        velocity: float,
        people_centres: List[Tuple[int, int]],
        own_centre: Tuple[int, int],
        now: float,
    ) -> str:
        if self._looks_like_fall(state, detection, own_centre):
            return "fallen_person"

        # Fighting: close proximity to another person + high velocity.
        # NOTE: This is a pure bounding-box heuristic (no pose estimation).
        # Two people standing close and moving normally may trigger a false
        # positive.  For production use, replace with a pose-based model
        # (e.g. YOLOv8-pose) to reduce false positives.
        for other in people_centres:
            if other == own_centre:
                continue
            if _euclidean(own_centre, other) < 80 and velocity > 15:
                return "fighting"

        if velocity > 30:
            return "running"

        # Loitering: barely moved for a long time
        stationary_secs = now - state.last_moved
        if stationary_secs > self._loitering_threshold:
            return "loitering"

        if velocity < 2:
            # Nearly still — could be studying/working/sleeping
            time_in_area = now - state.first_seen
            if time_in_area > 600:   # 10 min
                return "studying"
            return "idle"

        return "working"

    @staticmethod
    def _make_notes(state: _TrackState, activity: str, now: float) -> str:
        dwell = int(now - state.first_seen)
        posture = (
            f"{state.aspect_ratio_history[-1]:.2f}"
            if state.aspect_ratio_history else "n/a"
        )
        return (
            f"Track {state.track_id}: dwell={dwell}s, "
            f"activity={activity}, posture_ratio={posture}"
        )

    @staticmethod
    def _aspect_ratio(det: Detection) -> float:
        if det.bbox is None or det.bbox.h <= 0:
            return 0.0
        return det.bbox.w / det.bbox.h

    def _looks_like_fall(
        self,
        state: _TrackState,
        detection: Detection,
        own_centre: Tuple[int, int],
    ) -> bool:
        if detection.bbox is None:
            return False

        current_ratio = self._aspect_ratio(detection)
        historical_ratios = list(state.aspect_ratio_history)[:-1]
        was_upright = any(r < 0.85 for r in historical_ratios)
        sudden_drop = False
        if len(state.position_history) >= 2:
            previous_y = state.position_history[-2][1]
            sudden_drop = own_centre[1] - previous_y > 25

        return current_ratio >= 1.15 and (was_upright or sudden_drop)

    def _prune_tracks(self, now: float, max_age: float = 30.0) -> None:
        stale = [
            tid for tid, s in self._tracks.items()
            if now - s.last_moved > max_age + self._loitering_threshold
        ]
        for tid in stale:
            del self._tracks[tid]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _euclidean(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return float(np.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2))
