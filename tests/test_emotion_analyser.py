"""
Tests for EmotionAnalyser and EmotionResult.

DeepFace is not installed in CI, so all tests verify the graceful-fallback
path where ``emotion = "unknown"`` is returned.
"""

import numpy as np
import pytest

from src.detection.emotion_analyser import EmotionAnalyser, EmotionResult
from src.detection.person_detector import BoundingBox, Detection


def _make_detection(
    object_type: str = "person",
    with_bbox: bool = False,
) -> Detection:
    det = Detection(camera_id="cam-01", zone="entrance", object_type=object_type)
    if with_bbox:
        det.bbox = BoundingBox(x=10, y=10, w=40, h=60)
    return det


# ---------------------------------------------------------------------------
# EmotionResult dataclass
# ---------------------------------------------------------------------------

class TestEmotionResult:
    def test_negative_emotion_flag(self):
        r = EmotionResult(
            camera_id="c", zone="z", person_name=None,
            emotion="angry", confidence=0.9, is_negative=True,
        )
        assert r.is_negative is True

    def test_positive_emotion_flag(self):
        r = EmotionResult(
            camera_id="c", zone="z", person_name=None,
            emotion="happy", confidence=0.8, is_negative=False,
        )
        assert r.is_negative is False

    def test_timestamp_set_automatically(self):
        r = EmotionResult(
            camera_id="c", zone="z", person_name=None,
            emotion="neutral", confidence=0.5, is_negative=False,
        )
        assert r.timestamp > 0

    def test_bbox_optional(self):
        r = EmotionResult(
            camera_id="c", zone="z", person_name="Alice",
            emotion="sad", confidence=0.6, is_negative=True,
        )
        assert r.bbox is None


# ---------------------------------------------------------------------------
# EmotionAnalyser
# ---------------------------------------------------------------------------

class TestEmotionAnalyser:
    def test_analyse_empty_detections_returns_empty(self):
        analyser = EmotionAnalyser(frame_interval=1)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert analyser.analyse(frame, []) == []

    def test_analyse_skips_non_person_detections(self):
        analyser = EmotionAnalyser(frame_interval=1)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        dets = [_make_detection("vehicle"), _make_detection("animal")]
        assert analyser.analyse(frame, dets) == []

    def test_analyse_respects_frame_interval_skip(self):
        """Calls that don't land on a multiple of frame_interval return []."""
        analyser = EmotionAnalyser(frame_interval=5)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        dets = [_make_detection("person")]
        # First 4 calls (call counts 1-4) should all be skipped
        for _ in range(4):
            assert analyser.analyse(frame, dets) == []

    def test_analyse_runs_on_interval(self):
        """5th call (count == 5) should trigger analysis and return a result."""
        analyser = EmotionAnalyser(frame_interval=5)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        dets = [_make_detection("person")]
        for _ in range(4):
            analyser.analyse(frame, dets)
        # 5th call — DeepFace not installed so fallback to "unknown"
        result = analyser.analyse(frame, dets)
        assert len(result) == 1
        assert result[0].emotion == "unknown"
        assert result[0].camera_id == "cam-01"

    def test_analyse_returns_unknown_without_deepface(self):
        """When DeepFace is absent, every result must carry emotion='unknown'."""
        import sys
        from unittest.mock import patch
        analyser = EmotionAnalyser(frame_interval=1)
        frame = np.zeros((60, 60, 3), dtype=np.uint8)
        dets = [_make_detection("person")]
        # Simulate deepface being unavailable by blocking the import
        with patch.dict(sys.modules, {"deepface": None}):
            result = analyser.analyse(frame, dets)
        assert len(result) == 1
        assert result[0].emotion == "unknown"
        assert result[0].confidence == 0.0
        assert not result[0].is_negative

    def test_analyse_multiple_people(self):
        analyser = EmotionAnalyser(frame_interval=1)
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        dets = [_make_detection("person"), _make_detection("person")]
        # Two people → two results regardless of DeepFace availability
        result = analyser.analyse(frame, dets)
        assert len(result) == 2

    def test_analyse_uses_person_name_from_detection(self):
        analyser = EmotionAnalyser(frame_interval=1)
        frame = np.zeros((60, 60, 3), dtype=np.uint8)
        det = _make_detection("person")
        det.person_name = "Alice"
        result = analyser.analyse(frame, [det])
        assert result[0].person_name == "Alice"

    def test_call_count_increments(self):
        analyser = EmotionAnalyser(frame_interval=3)
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        assert analyser._call_count == 0
        analyser.analyse(frame, [])
        assert analyser._call_count == 1
        analyser.analyse(frame, [])
        assert analyser._call_count == 2
