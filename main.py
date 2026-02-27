#!/usr/bin/env python3
"""
AI Security Camera System — entry point.

Usage
-----
    python main.py                        # use DEFAULT_CONFIG
    VENUE_TYPE=school python main.py      # override via env vars
    python main.py --demo                 # run a 10-second demo with mock data

Run ``python main.py --help`` for all options.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure the project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import AppConfig, CameraConfig, DEFAULT_CONFIG, VenueType


def _configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy third-party loggers
    for noisy in ("urllib3", "PIL", "ultralytics", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Security Camera System"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a 10-second demo with synthetic data (no real cameras needed)",
    )
    parser.add_argument(
        "--venue-type",
        choices=[v.value for v in VenueType],
        default=None,
        help="Override the venue type",
    )
    parser.add_argument(
        "--venue-name",
        default=None,
        help="Override the venue name",
    )
    parser.add_argument(
        "--camera-source",
        default=None,
        help=(
            "Camera source: integer index (0, 1, …), "
            "RTSP URL, or path to a video file"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args()


def _build_config(args: argparse.Namespace) -> AppConfig:
    config = DEFAULT_CONFIG

    if args.venue_type:
        config.venue_type = VenueType(args.venue_type)
    if args.venue_name:
        config.venue_name = args.venue_name
    if args.camera_source:
        if config.cameras:
            config.cameras[0].source = args.camera_source
        else:
            config.cameras.append(
                CameraConfig(
                    camera_id="cam-01",
                    source=args.camera_source,
                    zone="main",
                )
            )
    if args.debug:
        config.debug = True

    return config


def _run_demo(config: AppConfig) -> None:
    """
    Run a synthetic demo without real cameras.

    Injects mock frames, detections, and alerts to show the dashboard.
    """
    import numpy as np
    from src.alerts.alert_manager import Alert, AlertManager
    from src.attendance.time_tracker import AttendanceTracker
    from src.dashboard.admin_dashboard import AdminDashboard

    logger = logging.getLogger("demo")
    logger.info("Starting DEMO mode (10 seconds)…")

    dashboard = AdminDashboard(
        venue_name=config.venue_name + "  [DEMO]",
        refresh_seconds=2,
    )
    alert_mgr = AlertManager(config=config.alert)
    tracker = AttendanceTracker(
        work_start=config.attendance.work_start_time,
        work_end=config.attendance.work_end_time,
    )

    # Simulate camera IDs
    dashboard.update_cameras(["cam-01", "cam-02"])

    # Simulate some attendance
    from datetime import datetime
    for name in ["Alice Smith", "Bob Jones", "Carol White"]:
        tracker.record_sighting(name, "cam-01", "classroom-A")
    dashboard.update_attendance(tracker.get_today_summary())

    # Simulate a couple of alerts
    alerts = [
        Alert(
            camera_id="cam-01",
            zone="corridor",
            alert_type="loitering",
            severity="medium",
            description="Person loitering near exit for >2 minutes.",
        ),
        Alert(
            camera_id="cam-02",
            zone="entrance",
            alert_type="anomaly",
            severity="high",
            description="Dog detected near main entrance.",
        ),
    ]
    for a in alerts:
        dashboard.add_alert(a)

    dashboard.update_counts(persons=7, anomalies=2)

    # Run the dashboard for a few refreshes
    import threading

    def _stop_after(n: int) -> None:
        time.sleep(n)
        dashboard.stop()

    t = threading.Thread(target=_stop_after, args=(10,), daemon=True)
    t.start()
    dashboard.run()
    logger.info("Demo completed.")


def main() -> None:
    args = _parse_args()
    _configure_logging(args.debug)
    logger = logging.getLogger("main")

    config = _build_config(args)
    logger.info(
        "AI Security Camera System starting — venue='%s' type=%s",
        config.venue_name,
        config.venue_type.value,
    )

    Path("data").mkdir(exist_ok=True)
    Path(config.attendance.reports_dir).mkdir(parents=True, exist_ok=True)
    Path(config.attendance.known_faces_dir).mkdir(parents=True, exist_ok=True)

    if args.demo:
        _run_demo(config)
        return

    # Real pipeline
    from src.pipeline import ProcessingPipeline

    pipeline = ProcessingPipeline(config=config, save_snapshots=True)
    try:
        pipeline.start()
    except KeyboardInterrupt:
        logger.info("Shutting down…")


if __name__ == "__main__":
    main()
