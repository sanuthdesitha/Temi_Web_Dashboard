"""
Cloud MQTT Monitor - Connects to HiveMQ cloud broker
Monitors nokia/safety/* topics for violation data
"""

import paho.mqtt.client as mqtt
import json
import ssl
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CloudMQTTMonitor:
    """MQTT client that monitors the cloud broker for safety violations"""

    def __init__(self, broker_url, port, username, password, use_tls=True):
        self.broker_url = broker_url
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

        self.client = None
        self.connected = False
        self.on_message_callback = None
        self.on_violation_callback = None

        # Topics to monitor
        self.topics = [
            ("nokia/safety/violations/summary", 0),
            ("nokia/safety/violations/counts", 0),
            ("nokia/safety/violations/new", 0),
        ]

    def set_callbacks(self, on_message=None, on_violation=None):
        """Set callback functions"""
        if on_message:
            self.on_message_callback = on_message
        if on_violation:
            self.on_violation_callback = on_violation

    def connect(self):
        """Connect to cloud MQTT broker"""
        try:
            # Create MQTT client
            client_id = f"temi_control_monitor_{datetime.now().timestamp()}"
            self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)

            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            # Set username and password
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            # Configure TLS if needed
            if self.use_tls:
                self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)
                self.client.tls_insecure_set(False)

            # Connect to broker
            logger.info(f"Connecting to cloud MQTT broker {self.broker_url}:{self.port}")
            self.client.connect(self.broker_url, self.port, keepalive=60)

            # Start network loop in background thread
            self.client.loop_start()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to cloud MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.connected = False
                logger.info("Disconnected from cloud MQTT broker")
        except Exception as e:
            logger.error(f"Error disconnecting from cloud MQTT broker: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to cloud MQTT broker")

            # Subscribe to all topics
            for topic, qos in self.topics:
                self.client.subscribe(topic, qos)
                logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect to cloud MQTT broker. Return code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        logger.info(f"Disconnected from cloud MQTT broker. Return code: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
            except json.JSONDecodeError:
                # If not JSON, treat as string
                payload = msg.payload.decode('utf-8')

            # Log message
            logger.info(f"[CLOUD MQTT] Topic: {topic}")
            logger.debug(f"[CLOUD MQTT] Payload: {payload}")

            # Call message callback
            if self.on_message_callback:
                self.on_message_callback(topic, payload)

            # Process violation messages
            if 'nokia/safety/violations' in topic:
                self._process_violation(topic, payload)

        except Exception as e:
            logger.error(f"Error processing cloud MQTT message: {e}")

    def publish(self, topic, payload, qos=0):
        """Publish a message to the cloud MQTT broker"""
        if not self.client or not self.connected:
            logger.error("Cannot publish - not connected to cloud MQTT broker")
            return False
        try:
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            result = self.client.publish(topic, payload, qos=qos)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"[CLOUD MQTT] Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"[CLOUD MQTT] Failed to publish to {topic}: rc={result.rc}")
                return False
        except Exception as e:
            logger.error(f"[CLOUD MQTT] Publish error: {e}")
            return False

    def _process_violation(self, topic, payload):
        """Process violation messages"""
        try:
            # Extract violation data
            violation_data = {
                'topic': topic,
                'timestamp': datetime.now().isoformat(),
                'payload': payload
            }

            # Parse based on topic type
            if topic == 'nokia/safety/violations/summary':
                violation_data['type'] = 'summary'
                violation_data['total_violations'] = payload.get('total_violations', 0)
                violation_data['viewports'] = payload.get('viewports', {})

            elif topic == 'nokia/safety/violations/counts':
                violation_data['type'] = 'counts'
                violation_data['total_people'] = payload.get('total_people', 0)
                violation_data['total_violations'] = payload.get('total_violations', 0)
                violation_data['viewports'] = payload.get('viewports', {})

            elif topic == 'nokia/safety/violations/new':
                violation_data['type'] = 'new_violation'
                violation_data['event_id'] = payload.get('event_id')
                violation_data['track_id'] = payload.get('track_id')
                violation_data['violation_type'] = payload.get('violation_type')
                violation_data['viewport'] = payload.get('viewport')
                violation_data['confidence'] = payload.get('confidence')
                violation_data['bbox'] = payload.get('bbox')
                violation_data['location_info'] = payload.get('location')
                # Extract Temi location from payload if available
                if isinstance(payload.get('location'), dict):
                    violation_data['azimuth'] = payload['location'].get('azimuth')
                    violation_data['elevation'] = payload['location'].get('elevation')

            # Call violation callback
            if self.on_violation_callback:
                self.on_violation_callback(violation_data)

        except Exception as e:
            logger.error(f"Error processing violation: {e}")


# Global cloud monitor instance (will be initialized in app.py)
cloud_monitor = None


def initialize_cloud_monitor(broker_url, port, username, password, use_tls=True):
    """Initialize the global cloud monitor instance"""
    global cloud_monitor
    cloud_monitor = CloudMQTTMonitor(broker_url, port, username, password, use_tls)
    return cloud_monitor


if __name__ == '__main__':
    print("Cloud MQTT Monitor module loaded successfully")
