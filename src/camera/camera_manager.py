"""
Camera manager — opens, reads, and releases camera feeds.

Supports:
* Local webcams (integer index)
* IP / RTSP streams (URL string)
* Video files (path string) — useful for testing

Each camera runs in its own background thread and puts decoded frames into a
thread-safe queue so that the processing pipeline never blocks on I/O.

Note: ``opencv-python`` (cv2) is imported lazily inside methods that actually
open a capture device so that the module can be imported and tested without
a full OpenCV installation.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config.settings import CameraConfig

logger = logging.getLogger(__name__)

# Maximum frames held in memory per camera before the oldest is dropped
_FRAME_QUEUE_SIZE = 8


@dataclass
class Frame:
    """A decoded video frame together with its metadata."""

    camera_id: str
    zone: str
    data: np.ndarray          # BGR image array
    timestamp: float = field(default_factory=time.time)
    frame_number: int = 0


class CameraStream:
    """
    Background thread that continuously reads from a single camera.

    Call :meth:`start` before reading frames, and :meth:`stop` when done.
    """

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._queue: queue.Queue[Frame] = queue.Queue(maxsize=_FRAME_QUEUE_SIZE)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._frame_count = 0
        self._cap: Any = None  # cv2.VideoCapture, set lazily in start()
        self.is_running = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> "CameraStream":
        """Open the capture device and start the reader thread."""
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "opencv-python is required to open a camera. "
                "Install it with: pip install opencv-python"
            ) from exc

        source: int | str
        try:
            source = int(self.config.source)
        except ValueError:
            source = self.config.source

        self._cap = cv2.VideoCapture(source)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera '{self.config.camera_id}' "
                f"with source '{self.config.source}'"
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._reader_loop,
            name=f"camera-{self.config.camera_id}",
            daemon=True,
        )
        self._thread.start()
        self.is_running = True
        logger.info(
            "Camera '%s' started (source=%s, zone=%s)",
            self.config.camera_id,
            self.config.source,
            self.config.zone,
        )
        return self

    def stop(self) -> None:
        """Signal the reader thread to exit and release the device."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()
        self.is_running = False
        logger.info("Camera '%s' stopped.", self.config.camera_id)

    def read_frame(self, timeout: float = 1.0) -> Optional[Frame]:
        """
        Return the latest available frame or *None* if none is available
        within *timeout* seconds.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._cap is None or not self._cap.isOpened():
                time.sleep(0.5)
                continue

            ret, raw = self._cap.read()
            if not ret:
                logger.warning(
                    "Camera '%s': failed to read frame. Retrying in 1 s…",
                    self.config.camera_id,
                )
                time.sleep(1.0)
                continue

            self._frame_count += 1
            frame = Frame(
                camera_id=self.config.camera_id,
                zone=self.config.zone,
                data=raw,
                frame_number=self._frame_count,
            )
            # Drop the oldest frame if the queue is full (non-blocking put)
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            self._queue.put_nowait(frame)


class CameraManager:
    """
    Manages the full set of camera streams defined in the application config.

    Usage::

        manager = CameraManager(config.cameras)
        manager.start_all()

        while True:
            for frame in manager.read_all_frames():
                process(frame)

        manager.stop_all()
    """

    def __init__(self, camera_configs: List[CameraConfig]) -> None:
        self._streams: Dict[str, CameraStream] = {}
        for cfg in camera_configs:
            if cfg.enabled:
                self._streams[cfg.camera_id] = CameraStream(cfg)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_all(self) -> None:
        for cam_id, stream in self._streams.items():
            try:
                stream.start()
            except RuntimeError as exc:
                logger.error("Failed to start camera '%s': %s", cam_id, exc)

    def stop_all(self) -> None:
        for stream in self._streams.values():
            stream.stop()

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def read_all_frames(self, timeout: float = 0.1) -> List[Frame]:
        """Collect one frame from every active camera."""
        frames = []
        for stream in self._streams.values():
            if not stream.is_running:
                continue
            frame = stream.read_frame(timeout=timeout)
            if frame is not None:
                frames.append(frame)
        return frames

    def get_stream(self, camera_id: str) -> Optional[CameraStream]:
        return self._streams.get(camera_id)

    @property
    def active_camera_ids(self) -> List[str]:
        return [cid for cid, s in self._streams.items() if s.is_running]

    def draw_info_overlay(
        self, frame: np.ndarray, camera_id: str, zone: str, extra: str = ""
    ) -> np.ndarray:
        """
        Burn camera ID, zone, and timestamp into the top-left corner of a frame.
        Returns a new array (does not modify the original in-place).
        """
        try:
            import cv2
        except ImportError:
            logger.warning("cv2 not available — draw_info_overlay skipped.")
            return frame.copy()

        out = frame.copy()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"Camera: {camera_id}  Zone: {zone}",
            ts,
        ]
        if extra:
            lines.append(extra)
        y = 28
        for line in lines:
            cv2.putText(
                out, line, (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
            )
            y += 26
        return out
