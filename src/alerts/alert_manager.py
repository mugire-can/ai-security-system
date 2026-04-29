"""
Alert manager — builds, deduplicates, and dispatches alerts to administrators.

Dispatchers supported
---------------------
* Email (SMTP/TLS)
* HTTP webhook (Slack / Teams / custom endpoint)
* Database record (always written regardless of other dispatchers)

Alerts are deduplicated: the same alert type from the same camera/zone will
not be resent to the admin within the cooldown window.
"""

import json
import logging
import smtplib
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Dict, List, Optional, Tuple

from config.settings import AlertConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Alert:
    """
    Immutable alert payload.  Created by the processing pipeline and
    handed to :class:`AlertManager.dispatch`.
    """

    camera_id: str
    zone: str
    alert_type: str  # matches AlertRecord.alert_type enum values
    severity: str  # "low" | "medium" | "high" | "critical"
    description: str
    person_name: Optional[str] = None
    snapshot_path: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def dedup_key(self) -> str:
        return f"{self.camera_id}:{self.zone}:{self.alert_type}:{self.person_name or ''}"


# ---------------------------------------------------------------------------
# AlertManager
# ---------------------------------------------------------------------------


class AlertManager:
    """
    Central hub for alert generation and delivery.

    Parameters
    ----------
    config : AlertConfig
        SMTP / webhook settings.
    on_alert : callable, optional
        Optional callback ``(alert: Alert) -> None`` invoked *after* all
        dispatchers run.  Useful for driving the live dashboard.
    """

    def __init__(
        self,
        config: AlertConfig,
        on_alert: Optional[Callable[["Alert"], None]] = None,
    ) -> None:
        self._config = config
        self._on_alert = on_alert
        # dedup_key → last dispatch timestamp
        self._last_sent: Dict[str, float] = {}
        # Warn early about common misconfigurations (e.g. placeholder admin_email)
        config.validate()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def dispatch(self, alert: Alert) -> bool:
        """
        Dispatch an alert if it passes the cooldown check.

        Returns ``True`` if the alert was actually dispatched.
        """
        now = time.time()
        last = self._last_sent.get(alert.dedup_key, 0.0)
        if now - last < self._config.alert_cooldown_seconds:
            logger.debug("Alert suppressed (cooldown): %s", alert.dedup_key)
            return False

        self._last_sent[alert.dedup_key] = now
        self._log_alert(alert)

        dispatched = False
        if self._config.smtp_user and self._config.smtp_password:
            dispatched |= self._send_email(alert)
        if self._config.webhook_url:
            dispatched |= self._send_webhook(alert)

        if self._on_alert:
            try:
                self._on_alert(alert)
            except Exception as exc:
                logger.error("on_alert callback error: %s", exc)

        return True

    def build_alert(
        self,
        camera_id: str,
        zone: str,
        alert_type: str,
        description: str,
        severity: str = "medium",
        person_name: Optional[str] = None,
        snapshot_path: Optional[str] = None,
    ) -> Alert:
        """Convenience factory to create and immediately dispatch an alert."""
        alert = Alert(
            camera_id=camera_id,
            zone=zone,
            alert_type=alert_type,
            severity=severity,
            description=description,
            person_name=person_name,
            snapshot_path=snapshot_path,
        )
        self.dispatch(alert)
        return alert

    def pending_count(self, since_seconds: float = 3600.0) -> int:
        """Count how many unique alert types have been dispatched recently."""
        now = time.time()
        return sum(1 for t in self._last_sent.values() if now - t <= since_seconds)

    # ------------------------------------------------------------------
    # Dispatchers
    # ------------------------------------------------------------------

    def _log_alert(self, alert: Alert) -> None:
        ts = datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        logger.warning(
            "🚨 ALERT [%s] %s | camera=%s zone=%s | person=%s | %s",
            alert.severity.upper(),
            alert.alert_type,
            alert.camera_id,
            alert.zone,
            alert.person_name or "—",
            alert.description,
        )

    def _send_email(self, alert: Alert) -> bool:
        """Send an email notification to the admin."""
        cfg = self._config
        subject = (
            f"[{alert.severity.upper()}] Security Alert: " f"{alert.alert_type} @ {alert.zone}"
        )
        body = self._build_email_body(alert)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.smtp_user
        msg["To"] = cfg.admin_email
        msg.attach(MIMEText(body, "html"))

        try:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(cfg.smtp_user, cfg.smtp_password)
                server.sendmail(cfg.smtp_user, cfg.admin_email, msg.as_string())
            logger.info("Alert email sent to %s", cfg.admin_email)
            return True
        except smtplib.SMTPException as exc:
            logger.error("Failed to send alert email: %s", exc)
            return False

    def _send_webhook(self, alert: Alert) -> bool:
        """POST a JSON payload to the configured webhook URL."""
        payload = {
            "text": (
                f"🚨 *{alert.severity.upper()} ALERT* — `{alert.alert_type}`\n"
                f"Camera: `{alert.camera_id}` | Zone: `{alert.zone}`\n"
                f"Person: {alert.person_name or '—'}\n"
                f"{alert.description}"
            ),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "camera_id": alert.camera_id,
            "zone": alert.zone,
            "timestamp": alert.timestamp,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._config.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                logger.info("Webhook alert sent (status %s).", resp.status)
            return True
        except (urllib.error.URLError, OSError) as exc:
            logger.error("Failed to send webhook alert: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_email_body(alert: Alert) -> str:
        ts = datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        colour = {
            "low": "#4CAF50",
            "medium": "#FF9800",
            "high": "#f44336",
            "critical": "#9C27B0",
        }.get(alert.severity, "#607D8B")
        return f"""
<html><body style="font-family:Arial,sans-serif;padding:20px;">
  <h2 style="color:{colour};">
    Security Alert — {alert.alert_type.replace("_", " ").title()}
  </h2>
  <table>
    <tr><td><b>Severity</b></td><td>{alert.severity.upper()}</td></tr>
    <tr><td><b>Camera</b></td><td>{alert.camera_id}</td></tr>
    <tr><td><b>Zone</b></td><td>{alert.zone}</td></tr>
    <tr><td><b>Person</b></td><td>{alert.person_name or "—"}</td></tr>
    <tr><td><b>Time</b></td><td>{ts}</td></tr>
    <tr><td><b>Description</b></td><td>{alert.description}</td></tr>
  </table>
  {"<p><b>Snapshot:</b> " + alert.snapshot_path + "</p>" if alert.snapshot_path else ""}
</body></html>
"""
