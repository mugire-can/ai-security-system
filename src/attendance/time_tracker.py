"""
Time tracker — records check-in and check-out times for every known person
seen by the cameras, and computes attendance status.

The tracker is intentionally lightweight: it works entirely in memory and
persists records by calling back into the database layer.
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class AttendanceTracker:
    """
    Tracks daily check-in / check-out for each identified individual.

    Parameters
    ----------
    work_start : str
        Expected start time in ``HH:MM`` format.
    work_end : str
        Expected end time in ``HH:MM`` format.
    on_checkin : callable, optional
        Callback invoked with ``(name, camera_id, zone, timestamp)``
        when a new check-in is recorded.
    on_checkout : callable, optional
        Callback invoked with ``(name, camera_id, zone, timestamp,
        duration_minutes)`` when a check-out is recorded.
    """

    def __init__(
        self,
        work_start: str = "08:00",
        work_end: str = "18:00",
        on_checkin: Optional[Callable] = None,
        on_checkout: Optional[Callable] = None,
    ) -> None:
        self._work_start = self._parse_hhmm(work_start)
        self._work_end = self._parse_hhmm(work_end)
        self._on_checkin = on_checkin
        self._on_checkout = on_checkout
        # {date_str: {person_name: {"check_in": dt, "check_out": dt, ...}}}
        self._records: Dict[str, Dict[str, dict]] = {}
        # Track the last time each person was seen (for auto check-out)
        self._last_seen: Dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def record_sighting(
        self,
        person_name: str,
        camera_id: str,
        zone: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record that *person_name* was sighted at *timestamp*.

        * First sighting of the day → check-in.
        * Every subsequent sighting → update "last seen" (used for check-out).
        """
        now = timestamp or datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        self._last_seen[person_name] = now

        day = self._records.setdefault(date_str, {})
        if person_name not in day:
            # First sighting today — check in
            status = self._compute_checkin_status(now)
            day[person_name] = {
                "check_in": now,
                "check_out": None,
                "camera_id": camera_id,
                "zone": zone,
                "status": status,
            }
            logger.info(
                "CHECK-IN  | %-20s | %s | camera=%-8s zone=%s",
                person_name, now.strftime("%H:%M:%S"), camera_id, zone,
            )
            if self._on_checkin:
                self._on_checkin(person_name, camera_id, zone, now)

    def record_departure(
        self,
        person_name: str,
        camera_id: str,
        zone: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record that *person_name* has left and update check-out time.

        Can be called explicitly (e.g. when a person is no longer tracked)
        or via :meth:`auto_checkout`.
        """
        now = timestamp or datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        resolved = self._find_open_record(person_name, preferred_date=date_str)
        if resolved is None:
            return
        _, record = resolved

        if record.get("check_out") is not None:
            return  # already checked out

        record["check_out"] = now
        duration = (now - record["check_in"]).total_seconds() / 60.0
        record["duration_minutes"] = duration

        # Refine status if early leave
        check_in_dt: datetime = record["check_in"]
        leave_status = self._compute_checkout_status(check_in_dt, now)
        record["status"] = leave_status

        logger.info(
            "CHECK-OUT | %-20s | %s | camera=%-8s zone=%-10s duration=%.0f min",
            person_name, now.strftime("%H:%M:%S"), camera_id, zone, duration,
        )
        if self._on_checkout:
            self._on_checkout(person_name, camera_id, zone, now, duration)

    def auto_checkout(self, inactivity_seconds: int = 300) -> None:
        """
        Auto-check-out everyone who hasn't been seen in *inactivity_seconds*.

        Suitable for calling on a schedule (e.g. every minute).
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=inactivity_seconds)
        for name, last in list(self._last_seen.items()):
            if last < cutoff:
                self.record_departure(
                    person_name=name,
                    camera_id="auto",
                    zone="auto",
                    timestamp=now,
                )
                del self._last_seen[name]

    def get_today_summary(self) -> list:
        """Return today's attendance records as a list of dicts."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        day = self._records.get(date_str, {})
        return [
            {
                "name": name,
                "check_in": rec["check_in"].strftime("%H:%M:%S") if rec["check_in"] else None,
                "check_out": rec["check_out"].strftime("%H:%M:%S") if rec["check_out"] else "—",
                "duration_min": round(rec.get("duration_minutes", 0)),
                "status": rec.get("status", "present"),
            }
            for name, rec in day.items()
        ]

    def get_absent_from_registered(self, registered: list) -> list:
        """Return names in *registered* that have no check-in today."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        day = self._records.get(date_str, {})
        return [name for name in registered if name not in day]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_checkin_status(self, dt: datetime) -> str:
        expected = dt.replace(
            hour=self._work_start.hour,
            minute=self._work_start.minute,
            second=0, microsecond=0,
        )
        if dt > expected + timedelta(minutes=15):
            return "late"
        return "present"

    def _compute_checkout_status(
        self, check_in: datetime, check_out: datetime
    ) -> str:
        expected_end = check_out.replace(
            hour=self._work_end.hour,
            minute=self._work_end.minute,
            second=0, microsecond=0,
        )
        check_in_status = self._compute_checkin_status(check_in)
        if check_out < expected_end - timedelta(minutes=15):
            return "early_leave"
        return check_in_status if check_in_status == "late" else "present"

    @staticmethod
    def _parse_hhmm(hhmm: str) -> datetime:
        return datetime.strptime(hhmm, "%H:%M")

    def _find_open_record(
        self, person_name: str, preferred_date: str
    ) -> Optional[tuple[str, dict]]:
        """
        Find the most relevant open attendance record for *person_name*.

        Prefer today's record, then fall back to the most recent earlier record
        that still has no check-out time. This avoids losing auto-checkouts when
        inactivity crosses midnight.
        """
        preferred_day = self._records.get(preferred_date, {})
        preferred_record = preferred_day.get(person_name)
        if preferred_record is not None:
            return preferred_date, preferred_record

        for date_key in sorted(self._records.keys(), reverse=True):
            record = self._records[date_key].get(person_name)
            if record is not None and record.get("check_out") is None:
                return date_key, record

        return None
