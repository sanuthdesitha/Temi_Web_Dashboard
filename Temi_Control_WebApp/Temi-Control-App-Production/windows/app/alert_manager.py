"""
Alert Manager for Temi Control Application
Handles in-app, email, and SMS notifications (email/SMS are stubbed for now).
"""

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
import requests

logger = logging.getLogger(__name__)


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class AlertManager:
    """Centralized alert handler for violation and system notifications."""

    def __init__(self, db_module):
        self.db = db_module

    def _get_settings(self):
        try:
            return self.db.get_all_settings()
        except Exception as exc:
            logger.error("AlertManager: failed to load settings: %s", exc)
            return {}

    def notify_violation(self, violation_data: dict) -> None:
        """Decide whether to notify, then dispatch via configured channels."""
        settings = self._get_settings()
        if not settings:
            return
        if not _to_bool(settings.get("notifications_enabled"), True):
            return

        only_high = _to_bool(settings.get("notify_only_high"), False)
        severity = str(violation_data.get("severity", "medium")).lower()
        if only_high and severity != "high":
            return

        notify_email = _to_bool(settings.get("notify_email"), False)
        notify_sms = _to_bool(settings.get("notify_sms"), False)
        notify_webpush = _to_bool(settings.get("notify_webpush"), False)
        notify_telegram = _to_bool(settings.get("notify_telegram"), False)
        notify_whatsapp = _to_bool(settings.get("notify_whatsapp"), False)

        if notify_email:
            self._send_email(violation_data, settings)
        if notify_sms:
            self._send_sms(violation_data, settings)
        if notify_telegram:
            self._send_telegram(violation_data, settings)
        if notify_whatsapp:
            self._send_whatsapp(violation_data, settings)
        if notify_webpush:
            self._send_webpush_stub(violation_data)

    def send_test_email(self) -> dict:
        """Send a test email using current SMTP settings."""
        settings = self._get_settings()
        if not settings:
            return {"success": False, "error": "SMTP settings not available"}

        host = settings.get("smtp_host")
        port = int(settings.get("smtp_port") or 587)
        user = settings.get("smtp_user")
        password = settings.get("smtp_password")
        from_addr = settings.get("smtp_from")
        to_addr = settings.get("smtp_to")
        use_tls = _to_bool(settings.get("smtp_use_tls"), True)

        if not host or not from_addr or not to_addr:
            return {"success": False, "error": "SMTP settings incomplete"}

        msg = EmailMessage()
        msg["Subject"] = "Temi WebApp SMTP Test"
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content("This is a test email from Temi Control WebApp.")

        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
            return {"success": True}
        except Exception as exc:
            logger.error("AlertManager: SMTP test failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def send_test_telegram(self) -> dict:
        """Send a test Telegram message using current settings."""
        settings = self._get_settings()
        if not settings:
            return {"success": False, "error": "Telegram settings not available"}

        token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
        if not token or not chat_id:
            return {"success": False, "error": "Telegram settings incomplete"}

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": "Temi WebApp Telegram test message."}
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code >= 300:
                return {"success": False, "error": resp.text}
            return {"success": True}
        except Exception as exc:
            logger.error("AlertManager: Telegram test failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def send_test_whatsapp(self) -> dict:
        """Send a test WhatsApp message using current Twilio settings."""
        settings = self._get_settings()
        if not settings:
            return {"success": False, "error": "WhatsApp settings not available"}

        sid = settings.get("twilio_account_sid")
        token = settings.get("twilio_auth_token")
        from_num = settings.get("twilio_whatsapp_from")
        to_num = settings.get("twilio_whatsapp_to")
        if not sid or not token or not from_num or not to_num:
            return {"success": False, "error": "WhatsApp settings incomplete"}

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        payload = {
            "From": from_num,
            "To": to_num,
            "Body": "Temi WebApp WhatsApp test message."
        }
        try:
            resp = requests.post(url, data=payload, auth=(sid, token), timeout=10)
            if resp.status_code >= 300:
                return {"success": False, "error": resp.text}
            return {"success": True}
        except Exception as exc:
            logger.error("AlertManager: WhatsApp test failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def _send_email(self, violation_data: dict, settings: dict) -> None:
        host = settings.get("smtp_host")
        port = int(settings.get("smtp_port") or 587)
        user = settings.get("smtp_user")
        password = settings.get("smtp_password")
        from_addr = settings.get("smtp_from")
        to_addr = settings.get("smtp_to")
        use_tls = _to_bool(settings.get("smtp_use_tls"), True)

        if not host or not from_addr or not to_addr:
            logger.warning("AlertManager: SMTP settings incomplete; skipping email")
            return

        subject = f"Temi Alert: {violation_data.get('violation_type', 'Violation')}"
        body = self._format_message(violation_data)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(body)

        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
            self._log_alert("email", violation_data)
        except Exception as exc:
            logger.error("AlertManager: SMTP send failed: %s", exc)

    def _send_sms(self, violation_data: dict, settings: dict) -> None:
        sid = settings.get("twilio_account_sid")
        token = settings.get("twilio_auth_token")
        from_num = settings.get("twilio_from")
        to_num = settings.get("twilio_to")

        if not sid or not token or not from_num or not to_num:
            logger.warning("AlertManager: Twilio settings incomplete; skipping SMS")
            return

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        payload = {
            "From": from_num,
            "To": to_num,
            "Body": self._format_message(violation_data)
        }
        try:
            resp = requests.post(url, data=payload, auth=(sid, token), timeout=10)
            if resp.status_code >= 300:
                logger.error("AlertManager: Twilio error %s: %s", resp.status_code, resp.text)
                return
            self._log_alert("sms", violation_data)
        except Exception as exc:
            logger.error("AlertManager: Twilio send failed: %s", exc)

    def _send_whatsapp(self, violation_data: dict, settings: dict) -> None:
        sid = settings.get("twilio_account_sid")
        token = settings.get("twilio_auth_token")
        from_num = settings.get("twilio_whatsapp_from")
        to_num = settings.get("twilio_whatsapp_to")

        if not sid or not token or not from_num or not to_num:
            logger.warning("AlertManager: WhatsApp settings incomplete; skipping WhatsApp")
            return

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        payload = {
            "From": from_num,
            "To": to_num,
            "Body": self._format_message(violation_data)
        }
        try:
            resp = requests.post(url, data=payload, auth=(sid, token), timeout=10)
            if resp.status_code >= 300:
                logger.error("AlertManager: Twilio WhatsApp error %s: %s", resp.status_code, resp.text)
                return
            self._log_alert("whatsapp", violation_data)
        except Exception as exc:
            logger.error("AlertManager: WhatsApp send failed: %s", exc)

    def _send_telegram(self, violation_data: dict, settings: dict) -> None:
        token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
        if not token or not chat_id:
            logger.warning("AlertManager: Telegram settings incomplete; skipping Telegram")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": self._format_message(violation_data)
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code >= 300:
                logger.error("AlertManager: Telegram error %s: %s", resp.status_code, resp.text)
                return
            self._log_alert("telegram", violation_data)
        except Exception as exc:
            logger.error("AlertManager: Telegram send failed: %s", exc)

    def _send_webpush_stub(self, violation_data: dict) -> None:
        logger.info("AlertManager: webpush notify (stub) -> %s", violation_data)
        self._log_alert("webpush", violation_data)

    def _log_alert(self, channel: str, violation_data: dict) -> None:
        try:
            robot_id = violation_data.get("robot_id")
            msg = f"Alert ({channel}) - {violation_data.get('violation_type', 'violation')} at {violation_data.get('location', 'unknown')}"
            details = {
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
                "data": violation_data
            }
            self.db.add_activity_log(robot_id, "warning", msg, str(details))
        except Exception as exc:
            logger.error("AlertManager: failed to log alert: %s", exc)

    def _format_message(self, violation_data: dict) -> str:
        robot_id = violation_data.get("robot_id", "unknown")
        location = violation_data.get("location", "unknown")
        vtype = violation_data.get("violation_type", "violation")
        severity = violation_data.get("severity", "medium")
        timestamp = violation_data.get("timestamp") or datetime.now().isoformat()
        return (
            f"Robot: {robot_id}\n"
            f"Location: {location}\n"
            f"Violation: {vtype}\n"
            f"Severity: {severity}\n"
            f"Time: {timestamp}\n"
        )

    def send_patrol_summary(self, summary_data: dict) -> None:
        """Send patrol completion summary via configured channels."""
        settings = self._get_settings()
        if not settings or not summary_data:
            return
        if not _to_bool(settings.get("notifications_enabled"), True):
            return

        notify_email = _to_bool(settings.get("notify_email"), False)
        notify_sms = _to_bool(settings.get("notify_sms"), False)
        notify_telegram = _to_bool(settings.get("notify_telegram"), False)
        notify_whatsapp = _to_bool(settings.get("notify_whatsapp"), False)

        message = self._format_patrol_summary(summary_data)

        if notify_email:
            self._send_custom_email("Patrol Summary", message, settings)
        if notify_sms:
            self._send_custom_sms(message, settings)
        if notify_telegram:
            self._send_custom_telegram(message, settings)
        if notify_whatsapp:
            self._send_custom_whatsapp(message, settings)

    def _format_patrol_summary(self, summary_data: dict) -> str:
        route_name = summary_data.get("route_name", "Unknown route")
        robot_id = summary_data.get("robot_id", "unknown")
        started_at = summary_data.get("started_at", "")
        ended_at = summary_data.get("ended_at", "")
        waypoint_summaries = summary_data.get("waypoints", []) or []
        total_violations = summary_data.get("total_violations", 0)
        total_people = summary_data.get("total_people", 0)

        lines = [
            f"Patrol Summary - {route_name}",
            f"Robot: {robot_id}",
            f"Start: {started_at}",
            f"End: {ended_at}",
            f"Total Violations: {total_violations}",
            f"Total People: {total_people}",
            "Waypoint Details:"
        ]
        for wp in waypoint_summaries:
            name = wp.get("waypoint_name") or wp.get("name") or "unknown"
            v = wp.get("total_violations", 0)
            p = wp.get("total_people", 0)
            lines.append(f"- {name}: {v} violations ({p} people)")
        return "\n".join(lines)

    def _send_custom_email(self, subject: str, body: str, settings: dict) -> None:
        host = settings.get("smtp_host")
        port = int(settings.get("smtp_port") or 587)
        user = settings.get("smtp_user")
        password = settings.get("smtp_password")
        from_addr = settings.get("smtp_from")
        to_addr = settings.get("smtp_to")
        use_tls = _to_bool(settings.get("smtp_use_tls"), True)

        if not host or not from_addr or not to_addr:
            logger.warning("AlertManager: SMTP settings incomplete; skipping email")
            return

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(body)

        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
        except Exception as exc:
            logger.error("AlertManager: SMTP send failed: %s", exc)

    def _send_custom_sms(self, message: str, settings: dict) -> None:
        sid = settings.get("twilio_account_sid")
        token = settings.get("twilio_auth_token")
        from_num = settings.get("twilio_from")
        to_num = settings.get("twilio_to")

        if not sid or not token or not from_num or not to_num:
            logger.warning("AlertManager: Twilio settings incomplete; skipping SMS")
            return

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        payload = {"From": from_num, "To": to_num, "Body": message}
        try:
            resp = requests.post(url, data=payload, auth=(sid, token), timeout=10)
            if resp.status_code >= 300:
                logger.error("AlertManager: Twilio error %s: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("AlertManager: Twilio send failed: %s", exc)

    def _send_custom_whatsapp(self, message: str, settings: dict) -> None:
        sid = settings.get("twilio_account_sid")
        token = settings.get("twilio_auth_token")
        from_num = settings.get("twilio_whatsapp_from")
        to_num = settings.get("twilio_whatsapp_to")

        if not sid or not token or not from_num or not to_num:
            logger.warning("AlertManager: WhatsApp settings incomplete; skipping WhatsApp")
            return

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        payload = {"From": from_num, "To": to_num, "Body": message}
        try:
            resp = requests.post(url, data=payload, auth=(sid, token), timeout=10)
            if resp.status_code >= 300:
                logger.error("AlertManager: Twilio WhatsApp error %s: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("AlertManager: WhatsApp send failed: %s", exc)

    def _send_custom_telegram(self, message: str, settings: dict) -> None:
        token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
        if not token or not chat_id:
            logger.warning("AlertManager: Telegram settings incomplete; skipping Telegram")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code >= 300:
                logger.error("AlertManager: Telegram error %s: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("AlertManager: Telegram send failed: %s", exc)
