"""
Tests for CameraStream, CameraManager, and Frame.

cv2 is not installed in CI.  These tests exercise all code paths that
do NOT require a real camera device.  The path that calls cv2 (CameraStream.start)
is tested by asserting that a clear RuntimeError is raised when cv2 is absent.
"""

import sys
from unittest.mock import patch

import numpy as np
import pytest

from config.settings import CameraConfig
from src.camera.camera_manager import CameraManager, CameraStream, Frame


# ---------------------------------------------------------------------------
# Frame dataclass
# ---------------------------------------------------------------------------

class TestFrame:
    def test_defaults(self):
        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        frame = Frame(camera_id="cam-01", zone="entrance", data=arr)
        assert frame.camera_id == "cam-01"
        assert frame.zone == "entrance"
        assert frame.frame_number == 0
        assert frame.timestamp > 0

    def test_frame_number_set(self):
        arr = np.zeros((10, 10, 3), dtype=np.uint8)
        frame = Frame(camera_id="c", zone="z", data=arr, frame_number=42)
        assert frame.frame_number == 42

    def test_data_preserved(self):
        arr = np.ones((5, 5, 3), dtype=np.uint8) * 128
        frame = Frame(camera_id="c", zone="z", data=arr)
        assert (frame.data == arr).all()


# ---------------------------------------------------------------------------
# CameraStream (without a real camera device)
# ---------------------------------------------------------------------------

class TestCameraStream:
    def _make_config(self, source: str = "0") -> CameraConfig:
        return CameraConfig(camera_id="cam-test", source=source, zone="test-zone")

    def test_init_not_running(self):
        stream = CameraStream(self._make_config())
        assert not stream.is_running
        assert stream._cap is None

    def test_read_frame_empty_queue_returns_none(self):
        stream = CameraStream(self._make_config())
        result = stream.read_frame(timeout=0.01)
        assert result is None

    def test_start_raises_runtime_error_without_cv2(self):
        """start() must raise RuntimeError when cv2 is not installed."""
        stream = CameraStream(self._make_config())
        with patch.dict(sys.modules, {"cv2": None}):
            with pytest.raises(RuntimeError, match="opencv-python"):
                stream.start()

    def test_stop_when_not_started_is_safe(self):
        """stop() must not raise even if start() was never called."""
        stream = CameraStream(self._make_config())
        stream.stop()  # should not raise
        assert not stream.is_running


# ---------------------------------------------------------------------------
# CameraManager
# ---------------------------------------------------------------------------

class TestCameraManager:
    def test_empty_config_no_streams(self):
        mgr = CameraManager([])
        assert mgr.active_camera_ids == []

    def test_disabled_camera_excluded(self):
        cfg = CameraConfig(camera_id="cam-off", source="0", zone="z", enabled=False)
        mgr = CameraManager([cfg])
        assert "cam-off" not in mgr.active_camera_ids
        assert mgr.get_stream("cam-off") is None

    def test_enabled_camera_creates_stream(self):
        cfg = CameraConfig(camera_id="cam-on", source="0", zone="z", enabled=True)
        mgr = CameraManager([cfg])
        stream = mgr.get_stream("cam-on")
        assert stream is not None
        assert not stream.is_running  # not yet started

    def test_get_stream_unknown_returns_none(self):
        mgr = CameraManager([])
        assert mgr.get_stream("nonexistent") is None

    def test_read_all_frames_empty(self):
        mgr = CameraManager([])
        frames = mgr.read_all_frames()
        assert frames == []

    def test_stop_all_empty_is_safe(self):
        mgr = CameraManager([])
        mgr.stop_all()  # must not raise

    def test_active_camera_ids_none_running(self):
        cfg = CameraConfig(camera_id="cam-01", source="0", zone="z", enabled=True)
        mgr = CameraManager([cfg])
        # Stream exists but is not started → not active
        assert "cam-01" not in mgr.active_camera_ids

    def test_draw_info_overlay_without_cv2_returns_copy(self):
        """draw_info_overlay must return a copy of the frame when cv2 is absent."""
        mgr = CameraManager([])
        frame = np.zeros((50, 50, 3), dtype=np.uint8)
        with patch.dict(sys.modules, {"cv2": None}):
            result = mgr.draw_info_overlay(frame, "cam-01", "entrance")
        assert result is not frame
        assert result.shape == frame.shape
