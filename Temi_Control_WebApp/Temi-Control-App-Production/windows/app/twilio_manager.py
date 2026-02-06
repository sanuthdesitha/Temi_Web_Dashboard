"""
Twilio WhatsApp Integration for Temi Robot Control
Sends WhatsApp alerts for violations, patrol status, and robot events
"""

import os
import logging
from typing import Optional, Dict, List
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


class TwilioWhatsAppManager:
    """
    Manages WhatsApp messaging via Twilio for alert notifications.

    Configuration via environment variables:
        TWILIO_ACCOUNT_SID: Your Twilio Account SID
        TWILIO_AUTH_TOKEN: Your Twilio Auth Token
        TWILIO_WHATSAPP_FROM: WhatsApp Sandbox number (whatsapp:+1415XXXXX)
        TWILIO_ALERT_RECIPIENTS: Comma-separated WhatsApp numbers to receive alerts
    """

    def __init__(self):
        """Initialize Twilio client with credentials from environment."""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID', '')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN', '')
        self.from_number = os.getenv('TWILIO_WHATSAPP_FROM', '')
        self.recipients = self._parse_recipients(
            os.getenv('TWILIO_ALERT_RECIPIENTS', '')
        )

        self.enabled = bool(self.account_sid and self.auth_token and self.from_number)

        if self.enabled:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("✅ Twilio WhatsApp integration enabled")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Twilio: {e}")
                self.enabled = False
        else:
            logger.warning("⚠️ Twilio WhatsApp not configured (missing credentials)")
            self.client = None

    @staticmethod
    def _parse_recipients(recipients_str: str) -> List[str]:
        """Parse comma-separated WhatsApp numbers."""
        if not recipients_str:
            return []
        return [f"whatsapp:{num.strip()}" for num in recipients_str.split(',')]

    def send_alert(self, message: str, robot_name: str = None,
                   custom_recipients: List[str] = None) -> Dict:
        """
        Send a WhatsApp alert message.

        Args:
            message: Alert message text
            robot_name: Name of the robot (for logging)
            custom_recipients: Override default recipients for this message

        Returns:
            Dict with status and message SID(s)
        """
        if not self.enabled:
            logger.warning("⚠️ Twilio not enabled, alert not sent")
            return {"status": "disabled", "message": "Twilio not configured"}

        recipients = custom_recipients or self.recipients
        if not recipients:
            logger.warning("⚠️ No WhatsApp recipients configured")
            return {"status": "no_recipients", "message": "No recipients configured"}

        results = []
        for recipient in recipients:
            try:
                msg = self.client.messages.create(
                    from_=self.from_number,
                    to=recipient,
                    body=message
                )
                results.append({
                    "recipient": recipient,
                    "status": "sent",
                    "sid": msg.sid
                })
                logger.info(
                    f"✅ WhatsApp alert sent to {recipient} "
                    f"(Robot: {robot_name or 'Unknown'}): {message[:50]}..."
                )
            except TwilioRestException as e:
                results.append({
                    "recipient": recipient,
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"❌ Failed to send WhatsApp to {recipient}: {e}")
            except Exception as e:
                results.append({
                    "recipient": recipient,
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"❌ Unexpected error sending WhatsApp: {e}")

        return {
            "status": "sent",
            "total": len(recipients),
            "results": results
        }

    def send_violation_alert(self, robot_name: str, location: str,
                             confidence: float) -> Dict:
        """Send alert when violation is detected."""
        message = (
            f"🚨 VIOLATION DETECTED\n\n"
            f"Robot: {robot_name}\n"
            f"Location: {location}\n"
            f"Confidence: {confidence:.1%}\n"
            f"Time: {self._get_timestamp()}\n\n"
            f"Check dashboard for details."
        )
        return self.send_alert(message, robot_name)

    def send_patrol_status(self, robot_name: str, status: str,
                           waypoint: str = None) -> Dict:
        """Send patrol status update."""
        status_emoji = {
            "started": "🚀",
            "navigating": "🧭",
            "arrived": "✅",
            "inspecting": "🔍",
            "returning": "🔄",
            "completed": "🎉",
            "stopped": "⏹️"
        }.get(status.lower(), "📍")

        message = (
            f"{status_emoji} PATROL STATUS UPDATE\n\n"
            f"Robot: {robot_name}\n"
            f"Status: {status.upper()}\n"
        )

        if waypoint:
            message += f"Waypoint: {waypoint}\n"

        message += f"Time: {self._get_timestamp()}"

        return self.send_alert(message, robot_name)

    def send_robot_alert(self, robot_name: str, alert_type: str,
                        description: str) -> Dict:
        """Send robot-specific alert."""
        alert_emoji = {
            "low_battery": "🔋",
            "disconnected": "📡",
            "error": "⚠️",
            "warning": "⚡",
            "info": "ℹ️"
        }.get(alert_type, "🔔")

        message = (
            f"{alert_emoji} ROBOT ALERT\n\n"
            f"Robot: {robot_name}\n"
            f"Type: {alert_type.upper()}\n"
            f"Details: {description}\n"
            f"Time: {self._get_timestamp()}"
        )

        return self.send_alert(message, robot_name)

    def test_message(self, test_number: str = None) -> Dict:
        """Send a test message to verify configuration."""
        if not self.enabled:
            return {"status": "error", "message": "Twilio not enabled"}

        recipient = f"whatsapp:{test_number}" if test_number else self.recipients[0]
        message = (
            f"✅ Test Message\n\n"
            f"Temi Robot Control WebApp\n"
            f"WhatsApp Integration Active\n"
            f"Time: {self._get_timestamp()}"
        )

        return self.send_alert(message, custom_recipients=[recipient])

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp for messages."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_status(self) -> Dict:
        """Get current Twilio configuration status."""
        return {
            "enabled": self.enabled,
            "account_configured": bool(self.account_sid),
            "from_number": self.from_number if self.enabled else "Not configured",
            "recipients_count": len(self.recipients),
            "recipients": self.recipients if self.enabled else []
        }


# Global instance
whatsapp_manager = TwilioWhatsAppManager()
