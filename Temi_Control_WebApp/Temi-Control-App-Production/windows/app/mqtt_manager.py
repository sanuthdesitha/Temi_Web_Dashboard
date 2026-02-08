"""
MQTT Manager module for Temi Control Application
Handles MQTT connections and message routing for multiple robots
"""

import json
import ssl
import logging
import threading
import time
import os
from typing import Dict, Callable, Optional, Any
import paho.mqtt.client as mqtt
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _normalize_webview_url(url: str) -> str:
    """Normalize webview URL to file:///storage/emulated/0/... when using local paths."""
    if not url:
        return url
    trimmed = str(url).strip()
    if trimmed.startswith(('http://', 'https://', 'file://', 'data:', 'content://')):
        return trimmed
    if trimmed.startswith('/'):
        return f"file://{trimmed}"
    return f"file:///storage/emulated/0/{trimmed}"


class MQTTRobotClient:
    """MQTT client for a single robot"""
    
    def __init__(self, robot_id: int, serial_number: str, broker_url: str, 
                 port: int, username: str = None, password: str = None, 
                 use_tls: bool = True):
        self.robot_id = robot_id
        self.serial_number = serial_number
        self.broker_url = broker_url
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        
        # Create unique client ID per process to avoid broker kicks
        self.client_id = f"temi_control_{serial_number}_{os.getpid()}_{int(time.time())}"
        
        # MQTT client
        self.client = None
        self.connected = False
        self.connecting = False
        self.last_connect_attempt = 0.0
        self.loop_started = False
        self.connect_lock = threading.Lock()
        
        # Callbacks
        self.on_message_callback: Optional[Callable] = None
        self.on_connect_callback: Optional[Callable] = None
        self.on_disconnect_callback: Optional[Callable] = None
        
        # Topic structure
        self.base_topic = f"temi/{serial_number}"
        self.command_topic = f"{self.base_topic}/command/#"
        
    def set_callbacks(self, on_message: Callable = None, on_connect: Callable = None, 
                     on_disconnect: Callable = None):
        """Set callback functions"""
        if on_message:
            self.on_message_callback = on_message
        if on_connect:
            self.on_connect_callback = on_connect
        if on_disconnect:
            self.on_disconnect_callback = on_disconnect
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            with self.connect_lock:
                now = time.time()
                if self.connecting or (now - self.last_connect_attempt) < 2.0:
                    return False
                self.connecting = True
                self.last_connect_attempt = now

            self.connected = False
            # Create MQTT client
            self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Set username and password if provided
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)
            
            # Configure TLS if needed
            if self.use_tls:
                self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)
                self.client.tls_insecure_set(False)

            # Enable auto-reconnect with backoff
            self.client.reconnect_delay_set(min_delay=1, max_delay=30)
            
            # Set Last Will and Testament
            lwt_topic = f"{self.base_topic}/lwt"
            lwt_payload = json.dumps({"status": "offline", "timestamp": datetime.now().isoformat()})
            self.client.will_set(lwt_topic, lwt_payload, qos=1, retain=False)
            
            # Connect to broker
            logger.info(f"Connecting to MQTT broker {self.broker_url}:{self.port} for robot {self.serial_number}")
            self.client.connect(self.broker_url, self.port, keepalive=120)
            
            # Start network loop in background thread
            if not self.loop_started:
                self.client.loop_start()
                self.loop_started = True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker for robot {self.serial_number}: {e}")
            return False
        finally:
            self.connecting = False

    def _wait_for_connect(self, timeout_seconds: float = 3.0) -> bool:
        """Wait briefly for on_connect to set connected flag"""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.connected:
                return True
            time.sleep(0.1)
        return self.connected

    def ensure_connected(self) -> bool:
        """Ensure client is connected, reconnecting if needed"""
        if self.connected and self.client:
            return True

        # Try reconnect if client exists
        if self.client:
            try:
                with self.connect_lock:
                    now = time.time()
                    if self.connecting or (now - self.last_connect_attempt) < 2.0:
                        return False
                    self.connecting = True
                    self.last_connect_attempt = now
                if not self.loop_started:
                    self.client.loop_start()
                    self.loop_started = True
                self.client.reconnect()
                return self._wait_for_connect(5.0)
            except Exception as e:
                logger.warning(f"Reconnect failed for robot {self.serial_number}: {e}")
            finally:
                self.connecting = False

        # Fall back to fresh connect
        if self.connect():
            return self._wait_for_connect(5.0)
        return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            if self.client:
                if self.loop_started:
                    self.client.loop_stop()
                    self.loop_started = False
                self.client.disconnect()
                self.connected = False
                logger.info(f"Disconnected from MQTT broker for robot {self.serial_number}")
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT broker: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            self.connecting = False
            logger.info(f"Connected to MQTT broker for robot {self.serial_number}")
            
            # Subscribe to all status and event topics from robot
            topics = [
                (f"{self.base_topic}/status/#", 0),
                (f"{self.base_topic}/event/#", 0),
                # YOLO topics
                ("nokia/safety/violations/summary", 0),
                ("nokia/safety/violations/counts", 0),
                ("nokia/safety/violations/new", 0),
            ]
            
            for topic, qos in topics:
                self.client.subscribe(topic, qos)
                logger.info(f"Subscribed to {topic}")
            
            # Call user callback
            if self.on_connect_callback:
                self.on_connect_callback(self.robot_id, self.serial_number)
        else:
            logger.error(f"Failed to connect to MQTT broker for robot {self.serial_number}. Return code: {rc} ({mqtt.error_string(rc)})")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        self.connecting = False
        logger.info(f"Disconnected from MQTT broker for robot {self.serial_number}. Return code: {rc} ({mqtt.error_string(rc)})")
        
        # Call user callback
        if self.on_disconnect_callback:
            self.on_disconnect_callback(self.robot_id, self.serial_number, rc)
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
            except json.JSONDecodeError:
                # If not JSON, treat as string
                payload = msg.payload.decode('utf-8')
            
            # Log all messages for debugging
            logger.info(f"[MQTT] Robot {self.serial_number} | Topic: {topic}")
            logger.info(f"[MQTT] Payload: {payload}")
            
            # Call user callback
            if self.on_message_callback:
                self.on_message_callback(self.robot_id, self.serial_number, topic, payload)
                
        except Exception as e:
            logger.error(f"Error processing message on {topic}: {e}")
            logger.error(f"Raw payload: {msg.payload}")
    
    def publish_command(self, category: str, command: str, payload: Dict) -> bool:
        """Publish command to robot"""
        if not self.ensure_connected():
            logger.warning(f"Cannot publish command - not connected to broker")
            return False
        
        try:
            topic = f"{self.base_topic}/command/{category}/{command}"
            payload_str = json.dumps(payload)
            
            result = self.client.publish(topic, payload_str, qos=0)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published command to {topic}: {payload}")
                return True
            else:
                logger.error(f"Failed to publish command. Return code: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing command: {e}")
            return False

    def publish_raw(self, topic: str, payload: Dict) -> bool:
        """Publish a raw MQTT message"""
        if not self.ensure_connected():
            logger.warning("Cannot publish raw message - not connected to broker")
            return False
        try:
            payload_str = json.dumps(payload)
            result = self.client.publish(topic, payload_str, qos=0)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published raw MQTT to {topic}: {payload}")
                return True
            logger.error(f"Failed to publish raw MQTT. Return code: {result.rc}")
            return False
        except Exception as e:
            logger.error(f"Error publishing raw MQTT: {e}")
            return False
    
    def goto_waypoint(self, location: str) -> bool:
        """Send goto waypoint command"""
        return self.publish_command("waypoint", "goto", {"location": location})
    
    def speak_tts(self, utterance: str) -> bool:
        """Send text-to-speech command"""
        return self.publish_command("tts", "speak", {"utterance": utterance})
    
    def play_video(self, url: str) -> bool:
        """Send play video command"""
        return self.publish_command("media", "video", {"url": url})
    
    def show_webview(self, url: str) -> bool:
        """Send show webview command"""
        return self.publish_command("media", "webview", {"url": _normalize_webview_url(url)})

    def close_webview(self) -> bool:
        """Send close webview command"""
        return self.publish_command("media", "webviewclose", {})
    
    def show_image(self, url: str) -> bool:
        """Send show image command (using webview)"""
        return self.publish_command("media", "webview", {"url": _normalize_webview_url(url)})
    
    def stop_movement(self) -> bool:
        """Send stop movement command"""
        return self.publish_command("move", "stop", {})
    
    def request_reposition(self) -> bool:
        """Request current location from robot"""
        return self.publish_command("location", "reposition", {})

    def request_waypoints(self) -> bool:
        """Request waypoint list from robot"""
        return self.publish_command("waypoint", "fetch", {})

    def request_locations(self) -> bool:
        """Request saved locations via SDK info/getLocations"""
        return self.publish_command("info", "getLocations", {})

    def request_position(self) -> bool:
        """Request current position (X, Y, theta) from robot"""
        return self.publish_command("position", "get", {})

    def request_map_image(self, chunk_size: int = 120000, fmt: str = "png") -> bool:
        """Request map image from robot via SDK getMapImage()"""
        payload = {"chunk_size": chunk_size, "format": fmt}
        return self.publish_command("map", "getImage", payload)

    def joystick_move(self, x: float, y: float, theta: float) -> bool:
        """Send joystick movement command"""
        return self.publish_command("move", "joystick", {
            "x": x,
            "y": y,
            "theta": theta
        })

    def tilt_camera(self, degrees: int) -> bool:
        """Tilt camera up/down (degrees: -25 to +60)"""
        return self.publish_command("utils", "tilt", {"degrees": degrees})

    def turn_by_angle(self, angle: int) -> bool:
        """Turn by angle in degrees"""
        return self.publish_command("move", "turn", {"angle": angle})

    def skid_joy(self, velocity: float, radius: float) -> bool:
        """Skid joystick command"""
        return self.publish_command("move", "skid_joy", {
            "velocity": velocity,
            "radius": radius
        })

    def publish_volume(self, volume: int) -> bool:
        """Publish volume control command (0-100)"""
        return self.publish_command("audio", "setVolume", {"level": volume, "level_percent": volume})

    def publish_system_command(self, command: str) -> bool:
        """Publish system command (restart, shutdown)"""
        return self.publish_command("system", command.lower(), {"timestamp": time.time()})


class MQTTManager:
    """Manager for multiple robot MQTT connections"""
    
    def __init__(self):
        self.robot_clients: Dict[int, MQTTRobotClient] = {}
        self.lock = threading.Lock()
        
        # Callbacks
        self.on_message_callback: Optional[Callable] = None
        self.on_connect_callback: Optional[Callable] = None
        self.on_disconnect_callback: Optional[Callable] = None
    
    def set_callbacks(self, on_message: Callable = None, on_connect: Callable = None, 
                     on_disconnect: Callable = None):
        """Set callback functions for all robots"""
        if on_message:
            self.on_message_callback = on_message
        if on_connect:
            self.on_connect_callback = on_connect
        if on_disconnect:
            self.on_disconnect_callback = on_disconnect
    
    def add_robot(self, robot_id: int, serial_number: str, broker_url: str, 
                  port: int, username: str = None, password: str = None, 
                  use_tls: bool = True) -> bool:
        """Add a robot and connect to its MQTT broker"""
        with self.lock:
            # Check if robot already exists
            if robot_id in self.robot_clients:
                existing = self.robot_clients[robot_id]
                if existing.connected:
                    logger.info(f"Robot {robot_id} already connected")
                    return True
                # Reconnect existing client
                logger.info(f"Robot {robot_id} exists but disconnected, reconnecting")
                return existing.ensure_connected()
            
            # Create robot client
            client = MQTTRobotClient(
                robot_id, serial_number, broker_url, port, 
                username, password, use_tls
            )
            
            # Set callbacks
            client.set_callbacks(
                on_message=self._on_message,
                on_connect=self._on_connect,
                on_disconnect=self._on_disconnect
            )
            
            # Connect
            success = client.connect()
            
            if success:
                if client._wait_for_connect(5.0):
                    self.robot_clients[robot_id] = client
                    logger.info(f"Added robot {robot_id} ({serial_number})")
                    return True
                logger.error(f"Timeout waiting for MQTT connect for robot {serial_number}")
                client.disconnect()
            else:
                logger.error(f"Failed to add robot {robot_id}")
                return False
    
    def remove_robot(self, robot_id: int) -> bool:
        """Remove a robot and disconnect from MQTT"""
        with self.lock:
            if robot_id not in self.robot_clients:
                logger.warning(f"Robot {robot_id} not found")
                return False
            
            client = self.robot_clients[robot_id]
            client.disconnect()
            del self.robot_clients[robot_id]
            
            logger.info(f"Removed robot {robot_id}")
            return True
    
    def get_robot_client(self, robot_id: int) -> Optional[MQTTRobotClient]:
        """Get robot client by ID"""
        return self.robot_clients.get(robot_id)
    
    def is_robot_connected(self, robot_id: int) -> bool:
        """Check if robot is connected"""
        client = self.get_robot_client(robot_id)
        return client.connected if client else False
    
    def disconnect_all(self):
        """Disconnect all robots"""
        with self.lock:
            for robot_id, client in list(self.robot_clients.items()):
                client.disconnect()
            self.robot_clients.clear()
            logger.info("Disconnected all robots")
    
    def _on_message(self, robot_id: int, serial_number: str, topic: str, payload: Dict):
        """Internal message callback"""
        if self.on_message_callback:
            self.on_message_callback(robot_id, serial_number, topic, payload)
    
    def _on_connect(self, robot_id: int, serial_number: str):
        """Internal connect callback"""
        if self.on_connect_callback:
            self.on_connect_callback(robot_id, serial_number)
    
    def _on_disconnect(self, robot_id: int, serial_number: str, rc: int):
        """Internal disconnect callback"""
        if self.on_disconnect_callback:
            self.on_disconnect_callback(robot_id, serial_number, rc)
    
    # Convenience methods for sending commands
    def goto_waypoint(self, robot_id: int, location: str) -> bool:
        """Send goto waypoint command to robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.goto_waypoint(location)
        return False
    
    def speak_tts(self, robot_id: int, utterance: str) -> bool:
        """Send TTS command to robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.speak_tts(utterance)
        return False
    
    def play_video(self, robot_id: int, url: str) -> bool:
        """Send play video command to robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.play_video(url)
        return False
    
    def show_webview(self, robot_id: int, url: str) -> bool:
        """Send show webview command to robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.show_webview(url)
        return False

    def close_webview(self, robot_id: int) -> bool:
        """Send close webview command to robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.close_webview()
        return False
    
    def show_image(self, robot_id: int, url: str) -> bool:
        """Send show image command to robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.show_image(url)
        return False
    
    def stop_movement(self, robot_id: int) -> bool:
        """Send stop movement command to robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.stop_movement()
        return False
    
    def request_reposition(self, robot_id: int) -> bool:
        """Request current location from robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.request_reposition()
        return False

    def request_waypoints(self, robot_id: int) -> bool:
        """Request waypoint list from robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.request_waypoints()
        return False

    def request_locations(self, robot_id: int) -> bool:
        """Request saved locations from robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.request_locations()
        return False

    def request_map_image(self, robot_id: int, chunk_size: int = 120000, fmt: str = "png") -> bool:
        """Request map image from robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.request_map_image(chunk_size, fmt)
        return False

    def publish_raw(self, robot_id: int, topic: str, payload: Dict) -> bool:
        """Publish a raw MQTT message for a robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.publish_raw(topic, payload)
        return False

    def joystick_move(self, robot_id: int, x: float, y: float, theta: float) -> bool:
        """Send joystick movement command to robot"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.joystick_move(x, y, theta)
        return False

    def tilt_camera(self, robot_id: int, degrees: int) -> bool:
        """Tilt camera up/down"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.tilt_camera(degrees)
        return False

    def turn_by_angle(self, robot_id: int, angle: int) -> bool:
        """Turn robot by angle"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.turn_by_angle(angle)
        return False

    def skid_joy(self, robot_id: int, velocity: float, radius: float) -> bool:
        """Send skid joystick command"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.skid_joy(velocity, radius)
        return False

    def publish_volume(self, robot_id: int, volume: int) -> bool:
        """Publish volume control command"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.publish_volume(volume)
        return False

    def publish_system_command(self, robot_id: int, command: str) -> bool:
        """Publish system command (restart, shutdown)"""
        client = self.get_robot_client(robot_id)
        if client:
            return client.publish_system_command(command)
        return False


# Global MQTT manager instance
mqtt_manager = MQTTManager()


if __name__ == '__main__':
    # Test MQTT manager
    print("MQTT Manager module loaded successfully")
