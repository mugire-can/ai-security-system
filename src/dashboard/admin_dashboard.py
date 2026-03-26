"""
Admin dashboard — real-time terminal UI.

Displays a continuously updating summary of:
* Active cameras and their status
* Recent alerts (unacknowledged, last 1 h)
* Today's attendance summary
* Detected anomalies (last 30 min)

The dashboard prints to stdout and refreshes every ``refresh_seconds``.
It is intentionally dependency-free so it works without any extra packages.
ANSI colour codes are automatically disabled when stdout is not a real
terminal (e.g. CI pipelines, Docker log capture, file redirection).
"""

import logging
import os
import sys
import time
from datetime import datetime
from typing import List, Optional

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from src.alerts.alert_manager import Alert

logger = logging.getLogger(__name__)

_RESET = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_GREEN = "\033[92m"
_CYAN = "\033[96m"
_MAGENTA = "\033[95m"
_WHITE = "\033[97m"


def _severity_colour(severity: str) -> str:
    return {
        "low": _GREEN,
        "medium": _YELLOW,
        "high": _RED,
        "critical": _MAGENTA,
    }.get(severity, _WHITE)


def _tty_supports_colour() -> bool:
    """Return True when stdout is a real terminal that supports ANSI codes."""
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class AdminDashboard:
    """
    Terminal dashboard that renders live stats for the security system.

    Parameters
    ----------
    venue_name : str
        Displayed in the header.
    refresh_seconds : int
        How often the screen is redrawn.
    max_alerts : int
        Maximum number of recent alerts to display.
    """

    def __init__(
        self,
        venue_name: str = "Venue",
        refresh_seconds: int = 5,
        max_alerts: int = 20,
    ) -> None:
        self.venue_name = venue_name
        self.refresh_seconds = refresh_seconds
        self.max_alerts = max_alerts

        self._active_cameras: List[str] = []
        self._recent_alerts: List[Alert] = []
        self._attendance: List[dict] = []
        self._anomaly_count: int = 0
        self._person_count: int = 0
        self._running = False
        # Only emit ANSI escape codes when writing to a real terminal.
        self._use_colour: bool = _tty_supports_colour()

    # ------------------------------------------------------------------
    # Colour helper
    # ------------------------------------------------------------------

    def _c(self, code: str) -> str:
        """Return *code* only when ANSI colour is enabled; otherwise ''."""
        return code if self._use_colour else ""

    # ------------------------------------------------------------------
    # Feed methods — called by the processing pipeline
    # ------------------------------------------------------------------

    def update_cameras(self, active_ids: List[str]) -> None:
        self._active_cameras = list(active_ids)

    def add_alert(self, alert: Alert) -> None:
        self._recent_alerts.insert(0, alert)
        if len(self._recent_alerts) > self.max_alerts:
            self._recent_alerts = self._recent_alerts[: self.max_alerts]

    def update_attendance(self, records: List[dict]) -> None:
        self._attendance = records

    def update_counts(self, persons: int, anomalies: int) -> None:
        self._person_count = persons
        self._anomaly_count = anomalies

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Clear the terminal and print the current dashboard state."""
        os.system("cls" if sys.platform == "win32" else "clear")
        self._print_header()
        self._print_camera_status()
        self._print_live_counts()
        self._print_alerts()
        self._print_attendance()
        self._print_footer()

    def run(self) -> None:
        """
        Blocking loop: render every ``refresh_seconds``.

        Interrupted by Ctrl-C.
        """
        self._running = True
        try:
            while self._running:
                self.render()
                time.sleep(self.refresh_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Private print helpers
    # ------------------------------------------------------------------

    def _print_header(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        w = 72
        print(self._c(_BOLD) + self._c(_CYAN) + "=" * w + self._c(_RESET))
        title = f"  AI SECURITY CAMERA SYSTEM  —  {self.venue_name}"
        print(self._c(_BOLD) + self._c(_CYAN) + title.center(w) + self._c(_RESET))
        print(self._c(_BOLD) + self._c(_CYAN) + f"  {now}".center(w) + self._c(_RESET))
        print(self._c(_BOLD) + self._c(_CYAN) + "=" * w + self._c(_RESET))

    def _print_camera_status(self) -> None:
        print(self._c(_BOLD) + "\n[CAMERAS]" + self._c(_RESET))
        if not self._active_cameras:
            print("  (no active cameras)")
        else:
            for cid in self._active_cameras:
                print(f"  {self._c(_GREEN)}● {cid}{self._c(_RESET)}  LIVE")

    def _print_live_counts(self) -> None:
        print(self._c(_BOLD) + "\n[LIVE COUNTS]" + self._c(_RESET))
        print(
            f"  People in frame : {self._c(_BOLD)}{self._person_count}{self._c(_RESET)}"
            f"   Anomalies : {self._c(_BOLD)}{self._anomaly_count}{self._c(_RESET)}"
        )

    def _print_alerts(self) -> None:
        print(self._c(_BOLD) + "\n[RECENT ALERTS]" + self._c(_RESET))
        if not self._recent_alerts:
            print(f"  {self._c(_GREEN)}No alerts.{self._c(_RESET)}")
            return
        print(
            f"  {'TIME':<10}  {'SEVERITY':<10}  {'TYPE':<25}  "
            f"{'CAMERA':<10}  {'ZONE':<15}  PERSON"
        )
        print("  " + "-" * 90)
        for alert in self._recent_alerts:
            ts = datetime.fromtimestamp(alert.timestamp).strftime("%H:%M:%S")
            colour = _severity_colour(alert.severity) if self._use_colour else ""
            print(
                f"  {ts:<10}  "
                f"{colour}{alert.severity.upper():<10}{self._c(_RESET)}  "
                f"{alert.alert_type:<25}  "
                f"{alert.camera_id:<10}  "
                f"{alert.zone:<15}  "
                f"{alert.person_name or '—'}"
            )

    def _print_attendance(self) -> None:
        print(self._c(_BOLD) + "\n[TODAY'S ATTENDANCE]" + self._c(_RESET))
        if not self._attendance:
            print("  (no records yet)")
            return
        print(
            f"  {'NAME':<22}  {'IN':<10}  {'OUT':<10}  "
            f"{'DURATION':>10}  STATUS"
        )
        print("  " + "-" * 70)
        status_colour = {
            "present": _GREEN,
            "late": _YELLOW,
            "early_leave": _YELLOW,
            "absent": _RED,
        }
        for rec in self._attendance:
            col = (status_colour.get(rec.get("status", "present"), _WHITE)
                   if self._use_colour else "")
            print(
                f"  {rec['name']:<22}  "
                f"{rec.get('check_in') or '—':<10}  "
                f"{rec.get('check_out') or '—':<10}  "
                f"{str(rec.get('duration_min', '')) + ' min':>10}  "
                f"{col}{rec.get('status', '').upper()}{self._c(_RESET)}"
            )

    def _print_footer(self) -> None:
        print("\n" + self._c(_BOLD) + self._c(_CYAN) + "  Press Ctrl+C to exit" + self._c(_RESET))
