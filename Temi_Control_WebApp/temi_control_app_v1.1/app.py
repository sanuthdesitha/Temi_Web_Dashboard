"""
Main Flask Application for Temi Control
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, stream_with_context
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
import logging
import json
import os
import subprocess
import base64
from collections import deque
from datetime import datetime, timedelta
import threading
from typing import Optional, Any
from functools import wraps
import requests
import time

# Import our modules
import database as db
from mqtt_manager import mqtt_manager
from patrol_manager import MultiRobotPatrolManager
from position_tracker import PositionTracker
from api_extensions import register_violation_routes, register_schedule_routes, register_detection_routes
from cloud_mqtt_monitor import initialize_cloud_monitor
from alert_manager import AlertManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Helper function for thread-safe Socket.IO emit (for MQTT callbacks)
def emit_socketio(event, data):
    """Emit Socket.IO event from any thread context (MQTT callbacks)"""
    try:
        with app.app_context():
            # Use socketio.server.emit() to broadcast from background threads
            # This sends to ALL connected clients on the default namespace
            socketio.server.emit(event, data, namespace='/')
            logger.info(f"[Socket.IO] Emitted {event} to all clients")
    except Exception as e:
        logger.error(f"[Socket.IO] Failed to emit {event}: {e}")

# Initialize database
db.init_database()

# Get settings
settings = db.get_all_settings()

# Initialize patrol manager
patrol_manager = MultiRobotPatrolManager(mqtt_manager, settings)

# Initialize position tracker
position_tracker = PositionTracker(max_history_per_robot=500)

# Initialize alert manager
alert_manager = AlertManager(db)

# YOLO state storage
yolo_state = {
    'enabled': True,  # Changed to True - YOLO enabled by default
    'last_message_time': None,
    'total_violations': 0,
    'total_people': 0,
    'viewports': {
        'front': 0,
        'right': 0,
        'back': 0,
        'left': 0
    }
}

# Track active detection sessions per robot
active_detection_sessions = {}
active_patrol_context = {}

# Violation smoothing state per robot
violation_history = {}
violation_ema = {}
last_yolo_payload = None

# Map image buffer storage for chunked transfers
map_image_buffers = {}

# MQTT topic monitoring (stores recent messages)
mqtt_message_history = []
MAX_MQTT_HISTORY = 100

# Cloud MQTT Monitor
cloud_monitor = None
cloud_monitor_started = False
violation_data_store = []
MAX_VIOLATIONS = 1000

# YOLO topic configuration (editable via settings)
yolo_topics = []  # Will be loaded from settings

# Thread-safe access to shared state
yolo_state_lock = threading.Lock()
mqtt_history_lock = threading.Lock()

# Schedule runner state
schedule_runner_thread = None
schedule_runner_started = False

# YOLO subprocess
yolo_process = None
yolo_process_lock = threading.Lock()


def _parse_schedule_config(raw_config):
    if raw_config is None:
        return {}
    if isinstance(raw_config, dict):
        return raw_config
    try:
        return json.loads(raw_config)
    except Exception:
        return {}


def _should_run_schedule(schedule, now: datetime) -> bool:
    """Return True if schedule should run now."""
    schedule_type = schedule.get('schedule_type', '')
    config = _parse_schedule_config(schedule.get('schedule_config'))
    last_run_at = schedule.get('last_run_at')

    last_run_date = None
    if last_run_at:
        try:
            last_run_date = datetime.fromisoformat(str(last_run_at)).date()
        except Exception:
            pass

    if schedule_type == 'daily':
        time_str = config.get('time', '09:00')
        if now.strftime('%H:%M') != time_str:
            return False
        return last_run_date != now.date()

    if schedule_type == 'weekly':
        time_str = config.get('time', '09:00')
        days = config.get('days', [])
        day_key = now.strftime('%a').lower()[:3]
        if day_key not in days:
            return False
        if now.strftime('%H:%M') != time_str:
            return False
        return last_run_date != now.date()

    if schedule_type == 'once':
        dt_str = config.get('datetime')
        if not dt_str:
            return False
        try:
            target = datetime.fromisoformat(dt_str)
        except Exception:
            return False
        if now < target:
            return False
        return last_run_at is None

    # Custom schedules not implemented
    return False


def schedule_runner_loop():
    """Background schedule runner that starts patrols based on schedules."""
    logger.info("Schedule runner started")
    while True:
        try:
            schedules = db.get_all_schedules(enabled_only=True)
            now = datetime.now()
            for schedule in schedules:
                try:
                    if not _should_run_schedule(schedule, now):
                        continue

                    route_id = schedule.get('route_id')
                    route = db.get_route_by_id(route_id)
                    if not route:
                        logger.warning("Schedule %s route not found", schedule.get('id'))
                        continue

                    robot_id = route.get('robot_id')
                    if not ensure_robot_connected(robot_id):
                        logger.warning("Schedule %s robot not connected", schedule.get('id'))
                        continue

                    run_id = db.create_schedule_run(schedule['id'], route_id, robot_id, status='running')
                    started = patrol_manager.start_patrol(robot_id, route)
                    if started:
                        _start_patrol_tracking(robot_id, route)
                        db.update_schedule_last_run(schedule['id'], now)
                        db.update_schedule_run(run_id, 'started', 'Patrol started')
                        db.add_activity_log(
                            robot_id=robot_id,
                            level='info',
                            message=f"Schedule started patrol: {schedule.get('name', 'schedule')}",
                            details=f"route_id={route_id}"
                        )
                        try:
                            session_id = db.start_detection_session(robot_id, route_id)
                            active_detection_sessions[robot_id] = session_id
                        except Exception as exc:
                            logger.error(f"Failed to start detection session: {exc}")
                        emit_socketio('schedule_started', {
                            'schedule_id': schedule['id'],
                            'route_id': route_id,
                            'robot_id': robot_id,
                            'timestamp': now.isoformat()
                        })
                        emit_active_patrol_count()
                    else:
                        db.update_schedule_run(run_id, 'failed', 'Failed to start patrol')
                        logger.warning("Schedule %s failed to start patrol", schedule.get('id'))
                except Exception as exc:
                    logger.error("Schedule runner error: %s", exc)
        except Exception as exc:
            logger.error("Schedule runner loop error: %s", exc)

        time.sleep(30)


def start_schedule_runner():
    global schedule_runner_thread, schedule_runner_started
    if schedule_runner_started:
        return
    schedule_runner_thread = threading.Thread(target=schedule_runner_loop, daemon=True)
    schedule_runner_thread.start()
    schedule_runner_started = True


def _start_patrol_tracking(robot_id: int, route: dict) -> None:
    """Track patrol start for summaries and history."""
    try:
        route_id = route.get('id') if isinstance(route, dict) else None
        history_id = None
        if route_id:
            history_id = db.start_patrol_history(robot_id, route_id)
        active_patrol_context[robot_id] = {
            'history_id': history_id,
            'route_id': route_id,
            'route_name': route.get('name') if isinstance(route, dict) else None,
            'started_at': datetime.now().isoformat()
        }
    except Exception as exc:
        logger.error(f"Failed to start patrol tracking: {exc}")


def _finalize_patrol_tracking(robot_id: int, status: str) -> dict:
    """Finalize patrol tracking and build summary payload."""
    end_time = datetime.now().isoformat()
    ctx = active_patrol_context.pop(robot_id, None)
    history = None
    if not ctx:
        try:
            history = db.get_active_patrol_history(robot_id)
        except Exception as exc:
            logger.error(f"Failed to load active patrol history: {exc}")
    history_id = ctx.get('history_id') if ctx else (history.get('id') if history else None)
    route_id = ctx.get('route_id') if ctx else (history.get('route_id') if history else None)
    route_name = ctx.get('route_name') if ctx else None
    started_at = ctx.get('started_at') if ctx else (history.get('started_at') if history else None)

    if history_id:
        try:
            db.update_patrol_history(history_id, status=status, ended_at=end_time)
        except Exception as exc:
            logger.error(f"Failed to update patrol history: {exc}")
    elif history and history.get('id'):
        try:
            db.update_patrol_history(history['id'], status=status, ended_at=end_time)
        except Exception as exc:
            logger.error(f"Failed to update patrol history: {exc}")

    if not route_name and route_id:
        try:
            route = db.get_route_by_id(route_id)
            if route:
                route_name = route.get('name')
        except Exception:
            pass

    summaries = []
    try:
        summaries = db.get_waypoint_summaries(
            robot_id=robot_id,
            route_id=route_id,
            start_date=started_at,
            end_date=end_time,
            limit=500
        )
    except Exception as exc:
        logger.error(f"Failed to load waypoint summaries: {exc}")

    aggregated = {}
    for row in summaries:
        name = row.get('waypoint_name') or 'unknown'
        entry = aggregated.setdefault(name, {'waypoint_name': name, 'total_violations': 0, 'total_people': 0})
        try:
            entry['total_violations'] += int(row.get('total_violations', 0) or 0)
        except Exception:
            pass
        try:
            entry['total_people'] += int(row.get('total_people', 0) or 0)
        except Exception:
            pass

    waypoint_list = list(aggregated.values())
    total_violations = sum(wp.get('total_violations', 0) for wp in waypoint_list)
    total_people = sum(wp.get('total_people', 0) for wp in waypoint_list)

    return {
        'robot_id': robot_id,
        'route_id': route_id,
        'route_name': route_name or 'Unknown route',
        'started_at': started_at or '',
        'ended_at': end_time,
        'total_violations': total_violations,
        'total_people': total_people,
        'waypoints': waypoint_list,
        'status': status
    }


def start_yolo_pipeline() -> bool:
    """Start YOLO subprocess if configured."""
    global yolo_process
    script_path = db.get_setting('yolo_script_path')
    if not script_path:
        return False
    script_path = os.path.abspath(script_path)
    if not os.path.exists(script_path):
        logger.warning("YOLO script path not found: %s", script_path)
        return False
    with yolo_process_lock:
        if yolo_process and yolo_process.poll() is None:
            return True
        try:
            yolo_process = subprocess.Popen(
                ['python', script_path],
                cwd=os.path.dirname(script_path) or None
            )
            logger.info("YOLO pipeline started (PID: %s)", yolo_process.pid)
            return True
        except Exception as exc:
            logger.error("Failed to start YOLO pipeline: %s", exc)
            return False


def stop_yolo_pipeline() -> bool:
    """Stop YOLO subprocess if running."""
    global yolo_process
    with yolo_process_lock:
        if not yolo_process or yolo_process.poll() is not None:
            return True
        try:
            yolo_process.terminate()
            yolo_process.wait(timeout=10)
            return True
        except Exception as exc:
            logger.error("Failed to stop YOLO pipeline: %s", exc)
            return False


def get_yolo_snapshot():
    """Provide a snapshot of YOLO state and last payload for patrol logic"""
    with yolo_state_lock:
        snapshot = {
            'enabled': yolo_state.get('enabled'),
            'last_message_time': yolo_state.get('last_message_time'),
            'total_violations': yolo_state.get('total_violations', 0),
            'total_people': yolo_state.get('total_people', 0),
            'viewports': dict(yolo_state.get('viewports', {})),
            'yolo_payload': last_yolo_payload
        }
    return snapshot


def _parse_bool_setting(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def notifications_enabled() -> bool:
    return _parse_bool_setting(db.get_setting('notifications_enabled', 'true'), True)


def in_app_notifications_enabled() -> bool:
    if not notifications_enabled():
        return False
    return _parse_bool_setting(db.get_setting('notify_in_app', 'true'), True)


def emit_active_patrol_count() -> None:
    """Emit active patrol count to all clients."""
    try:
        count = patrol_manager.get_active_patrol_count()
        emit_socketio('patrol_count_update', {'count': count})
    except Exception as exc:
        logger.error(f"Failed to emit patrol count: {exc}")


def ensure_robot_connected(robot_id: int) -> bool:
    """Ensure robot has an active MQTT connection"""
    if mqtt_manager.is_robot_connected(robot_id):
        return True

    robot = db.get_robot_by_id(robot_id)
    if not robot:
        return False

    return mqtt_manager.add_robot(
        robot_id, robot['serial_number'],
        robot['mqtt_broker_url'], robot['mqtt_port'],
        robot['mqtt_username'], robot['mqtt_password'],
        robot['use_tls']
    )


def connect_saved_robots():
    """Connect all robots stored in the database"""
    robots = db.get_all_robots()
    if not robots:
        logger.warning("No robots configured in database")
        return

    for robot in robots:
        try:
            mqtt_manager.add_robot(
                robot['id'], robot['serial_number'],
                robot['mqtt_broker_url'], robot['mqtt_port'],
                robot['mqtt_username'], robot['mqtt_password'],
                robot['use_tls']
            )
        except Exception as e:
            logger.error(f"Failed to connect robot {robot['id']}: {e}")


def _save_map_image(serial: str, image_bytes: bytes, fmt: str = 'png') -> Optional[str]:
    if not serial:
        return None
    ext = 'png' if fmt.lower() != 'jpg' and fmt.lower() != 'jpeg' else 'jpg'
    os.makedirs(os.path.join('static', 'maps'), exist_ok=True)
    filename = f"{serial}_map_{int(time.time())}.{ext}"
    path = os.path.join('static', 'maps', filename)
    try:
        with open(path, 'wb') as f:
            f.write(image_bytes)
    except Exception as exc:
        logger.error(f"Failed to write map image: {exc}")
        return None
    return f"/static/maps/{filename}"


def _handle_map_image_message(robot_id: Optional[int], serial: Optional[str], topic: str, payload: Any) -> None:
    if not serial or not topic:
        return

    if not isinstance(payload, dict):
        return

    request_id = payload.get('request_id') or payload.get('id') or 'default'

    if topic.endswith('/status/map/image'):
        image_b64 = payload.get('image_base64')
        fmt = payload.get('format', 'png')
        if not image_b64:
            return
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception as exc:
            logger.error(f"Failed to decode map image: {exc}")
            return
        url = _save_map_image(serial, image_bytes, fmt)
        if url and robot_id:
            db.update_robot(robot_id, map_image_url=url)
            emit_socketio('map_image_updated', {'robot_id': robot_id, 'url': url})
        return

    if topic.endswith('/status/map/image/meta'):
        try:
            total = int(payload.get('total_chunks', 0))
        except (TypeError, ValueError):
            total = 0
        fmt = payload.get('format', 'png')
        if total <= 0:
            return
        map_image_buffers[(serial, request_id)] = {
            'total': total,
            'chunks': {},
            'format': fmt
        }
        return

    if topic.endswith('/status/map/image/chunk'):
        try:
            index = int(payload.get('index', -1))
            total = int(payload.get('total', 0))
        except (TypeError, ValueError):
            return
        data = payload.get('data')
        if index < 0 or total <= 0 or not data:
            return

        key = (serial, request_id)
        buffer = map_image_buffers.get(key)
        if not buffer:
            buffer = {'total': total, 'chunks': {}, 'format': payload.get('format', 'png')}
            map_image_buffers[key] = buffer
        buffer['chunks'][index] = data
        if len(buffer['chunks']) >= buffer['total']:
            try:
                ordered = ''.join(buffer['chunks'][i] for i in range(buffer['total']))
            except Exception:
                return
            try:
                image_bytes = base64.b64decode(ordered)
            except Exception as exc:
                logger.error(f"Failed to decode map image chunks: {exc}")
                return
            url = _save_map_image(serial, image_bytes, buffer.get('format', 'png'))
            if url and robot_id:
                db.update_robot(robot_id, map_image_url=url)
                emit_socketio('map_image_updated', {'robot_id': robot_id, 'url': url})
            map_image_buffers.pop(key, None)


def start_cloud_monitor_from_settings():
    """Start cloud MQTT monitor using saved settings"""
    global cloud_monitor, cloud_monitor_started

    if cloud_monitor_started and cloud_monitor and cloud_monitor.connected:
        return

    mqtt_broker = db.get_setting('default_mqtt_broker')
    mqtt_port = int(db.get_setting('default_mqtt_port', 8883))
    mqtt_username = db.get_setting('default_mqtt_username')
    mqtt_password = db.get_setting('default_mqtt_password')
    use_tls = _parse_bool_setting(db.get_setting('default_mqtt_use_tls', 'true'), True)

    if not mqtt_broker:
        logger.warning("Cloud MQTT broker not configured (default_mqtt_broker missing)")
        return

    logger.info("=" * 60)
    logger.info("Initializing Cloud MQTT Monitor")
    logger.info(f"Broker: {mqtt_broker}:{mqtt_port}")
    logger.info("=" * 60)

    cloud_monitor = initialize_cloud_monitor(
        mqtt_broker, mqtt_port, mqtt_username, mqtt_password, use_tls=use_tls
    )

    # Get configurable YOLO topics
    topics_str = db.get_setting(
        'yolo_topics',
        'nokia/safety/violations/summary,nokia/safety/violations/counts,nokia/safety/violations/new'
    )
    yolo_topics_list = [t.strip() for t in topics_str.split(',') if t.strip()]

    # Override topics with configurable list and add wildcard for all messages
    cloud_monitor.topics = [(topic, 0) for topic in yolo_topics_list]
    cloud_monitor.topics.append(('#', 0))

    cloud_monitor.set_callbacks(
        on_message=on_cloud_mqtt_message,
        on_violation=on_cloud_violation
    )

    if cloud_monitor.connect():
        logger.info("Cloud MQTT monitor connected successfully")
        logger.info(f"Subscribed to {len(cloud_monitor.topics)} topic(s):")
        for topic, qos in cloud_monitor.topics:
            logger.info(f"  - {topic}")
    else:
        logger.error("Cloud MQTT monitor failed to connect")
    cloud_monitor_started = True


# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Cloud MQTT Callbacks
def on_cloud_mqtt_message(topic, payload):
    """Handle ALL cloud MQTT messages (like HiveMQ webclient)"""
    global mqtt_message_history, yolo_state, violation_data_store

    try:
        # Try to parse JSON string payloads
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                pass

        # Store ALL messages in history (like HiveMQ webclient)
        with mqtt_history_lock:
            mqtt_message_history.insert(0, {
                'timestamp': datetime.now().isoformat(),
                'robot_id': None,
                'serial_number': 'CLOUD',
                'topic': topic,
                'payload': payload
            })

            # Keep only recent messages
            if len(mqtt_message_history) > MAX_MQTT_HISTORY:
                mqtt_message_history = mqtt_message_history[:MAX_MQTT_HISTORY]

        # Emit to MQTT monitor (using thread-safe emit)
        emit_socketio('mqtt_message', {
            'timestamp': datetime.now().isoformat(),
            'robot_id': 'CLOUD',
            'topic': topic,
            'payload': payload
        })

        # Position tracking updates from cloud broker
        if '/status/position' in topic and isinstance(payload, dict):
            try:
                parts = topic.split('/')
                serial = parts[1] if len(parts) > 1 else None
                robot_id = None
                if serial:
                    robot = db.get_robot_by_serial(serial)
                    robot_id = robot['id'] if robot else None

                x = float(payload.get('x', 0.0))
                y = float(payload.get('y', 0.0))
                theta = float(payload.get('theta', 0.0))
                timestamp = payload.get('timestamp', datetime.now().timestamp())
                if isinstance(timestamp, str):
                    try:
                        timestamp = float(timestamp)
                    except Exception:
                        timestamp = datetime.now().timestamp()
                try:
                    timestamp = float(timestamp)
                except Exception:
                    timestamp = datetime.now().timestamp()
                if timestamp > 1e11:
                    timestamp = timestamp / 1000.0

                if robot_id is None:
                    robot_id = abs(hash(serial)) % 100000 if serial else 0

                position_tracker.update_position(robot_id, x, y, theta, timestamp)
                emit_socketio('position_update', {
                    'robot_id': robot_id,
                    'position': {
                        'x': x,
                        'y': y,
                        'theta': theta,
                        'timestamp': timestamp
                    },
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as exc:
                logger.error(f"Failed to process cloud position update: {exc}")

        # Map image updates from cloud broker
        if '/status/map/image' in topic and isinstance(payload, dict):
            try:
                parts = topic.split('/')
                serial = parts[1] if len(parts) > 1 else None
                robot_id = None
                if serial:
                    robot = db.get_robot_by_serial(serial)
                    robot_id = robot['id'] if robot else None
                _handle_map_image_message(robot_id, serial, topic, payload)
            except Exception as exc:
                logger.error(f"Failed to process cloud map image: {exc}")

        # Battery/status updates from cloud broker
        if '/status/' in topic and isinstance(payload, dict):
            try:
                parts = topic.split('/')
                serial = parts[1] if len(parts) > 1 else None
                robot_id = None
                if serial:
                    robot = db.get_robot_by_serial(serial)
                    robot_id = robot['id'] if robot else None

                if robot_id is None:
                    robot_id = abs(hash(serial)) % 100000 if serial else 0

                def extract_battery(data: dict):
                    for key in ['percentage', 'battery_percentage', 'battery', 'level', 'percent']:
                        if key in data and data.get(key) is not None:
                            try:
                                return int(float(data.get(key))), True
                            except Exception:
                                continue
                    return 0, False

                if '/status/info' in topic:
                    waypoint_list = payload.get('waypoint_list') or payload.get('locations') or []
                    battery, has_battery = extract_battery(payload)
                    if waypoint_list:
                        db.update_robot_waypoints(robot_id, waypoint_list)
                    if has_battery:
                        db.update_robot_status(robot_id, 'connected', battery_level=battery)
                    emit_socketio('robot_status', {
                        'robot_id': robot_id,
                        'waypoints': waypoint_list,
                        'battery': battery if has_battery else None,
                        'timestamp': datetime.now().isoformat()
                    })
                    if has_battery:
                        emit_socketio('battery_update', {
                            'robot_id': robot_id,
                            'battery': battery,
                            'is_charging': payload.get('is_charging', False),
                            'timestamp': datetime.now().isoformat()
                        })
                elif '/status/utils/battery' in topic:
                    battery, has_battery = extract_battery(payload)
                    is_charging = payload.get('is_charging', False)
                    if has_battery:
                        db.update_robot_status(robot_id, 'connected', battery_level=battery, is_charging=is_charging)
                        patrol_manager.update_battery_level(robot_id, battery, is_charging)
                        emit_socketio('battery_update', {
                            'robot_id': robot_id,
                            'battery': battery,
                            'is_charging': is_charging,
                            'timestamp': datetime.now().isoformat()
                        })
            except Exception as exc:
                logger.error(f"Failed to process cloud battery update: {exc}")

        # Process YOLO-related topics (filter for YOLO monitor)
        if any(yolo_topic in topic for yolo_topic in ['safety', 'violations', 'yolo']):
            process_yolo_topic(topic, payload)

    except Exception as e:
        logger.error(f"Error handling cloud MQTT message: {e}")


def process_yolo_topic(topic, payload):
    """Process YOLO-related topics and update YOLO monitor"""
    global yolo_state, violation_data_store, last_yolo_payload

    try:
        if not yolo_state.get('enabled', True):
            return
        def _safe_int(value, default=0):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return default

        def _clamp_violations(total_violations, total_people):
            total_violations = _safe_int(total_violations, 0)
            total_people = _safe_int(total_people, 0)
            if total_people < 0:
                total_people = 0
            if total_violations < 0:
                total_violations = 0
            if total_people >= 0 and total_violations > total_people:
                total_violations = total_people
            return total_violations, total_people

        def _smooth_violations(robot_id: int, value: int) -> int:
            try:
                window = int(db.get_setting('violation_debounce_window', 10) or 10)
            except (TypeError, ValueError):
                window = 10
            try:
                alpha = float(db.get_setting('violation_smoothing_factor', 0.3) or 0.3)
            except (TypeError, ValueError):
                alpha = 0.3
            try:
                outlier = float(db.get_setting('outlier_threshold', 3.0) or 3.0)
            except (TypeError, ValueError):
                outlier = 3.0

            if window < 3:
                window = 3
            hist = violation_history.get(robot_id)
            if hist is None:
                hist = deque(maxlen=window)
                violation_history[robot_id] = hist

            # Outlier rejection based on z-score
            if len(hist) >= 3:
                mean = sum(hist) / len(hist)
                variance = sum((x - mean) ** 2 for x in hist) / len(hist)
                std = variance ** 0.5
                if std > 0 and abs(value - mean) / std > outlier:
                    value = int(round(mean))

            # EMA smoothing
            prev = violation_ema.get(robot_id, value)
            ema = (alpha * value) + ((1 - alpha) * prev)
            violation_ema[robot_id] = ema

            hist.append(value)
            return int(round(ema))

        # Detect topic type and process accordingly
        violation_data = {
            'topic': topic,
            'timestamp': datetime.now().isoformat(),
            'payload': payload,
            'type': 'unknown'
        }

        with yolo_state_lock:
            last_yolo_payload = {
                'topic': topic,
                'timestamp': violation_data['timestamp'],
                'payload': payload
            }

        # Type 1: Summary messages (nokia/safety/violations/summary)
        if 'summary' in topic.lower():
            violation_data['type'] = 'summary'
            with yolo_state_lock:
                yolo_state['last_message_time'] = violation_data['timestamp']
                total_violations, total_people = _clamp_violations(
                    payload.get('total_violations', 0),
                    payload.get('total_people', yolo_state.get('total_people', 0))
                )
                if payload.get('robot_id'):
                    total_violations = _smooth_violations(int(payload.get('robot_id')), total_violations)
                yolo_state['total_violations'] = total_violations
                yolo_state['total_people'] = total_people

                # Parse viewports
                viewports = payload.get('viewports', {})
                for vp_name, vp_data in viewports.items():
                    if vp_name in yolo_state['viewports']:
                        if isinstance(vp_data, dict):
                            yolo_state['viewports'][vp_name] = vp_data.get('violations', vp_data.get('violation_count', 0))
                        else:
                            yolo_state['viewports'][vp_name] = vp_data

                yolo_snapshot = {
                    'enabled': yolo_state['enabled'],
                    'last_message_time': yolo_state['last_message_time'],
                    'total_violations': yolo_state['total_violations'],
                    'total_people': yolo_state['total_people'],
                    'viewports': dict(yolo_state['viewports'])
                }

            emit_socketio('yolo_summary', yolo_snapshot)

        # Type 2: Count messages (nokia/safety/violations/counts)
        elif 'count' in topic.lower():
            violation_data['type'] = 'counts'
            with yolo_state_lock:
                yolo_state['last_message_time'] = violation_data['timestamp']
                total_violations, total_people = _clamp_violations(
                    payload.get('total_violations', 0),
                    payload.get('total_people', 0)
                )
                if payload.get('robot_id'):
                    total_violations = _smooth_violations(int(payload.get('robot_id')), total_violations)
                yolo_state['total_violations'] = total_violations
                yolo_state['total_people'] = total_people

                # Parse viewports
                viewports = payload.get('viewports', {})
                for vp_name, vp_data in viewports.items():
                    if vp_name in yolo_state['viewports']:
                        if isinstance(vp_data, dict):
                            yolo_state['viewports'][vp_name] = vp_data.get('violations', vp_data.get('violation_count', 0))
                        else:
                            yolo_state['viewports'][vp_name] = vp_data

                yolo_snapshot = {
                    'enabled': yolo_state['enabled'],
                    'last_message_time': yolo_state['last_message_time'],
                    'total_violations': yolo_state['total_violations'],
                    'total_people': yolo_state['total_people'],
                    'viewports': dict(yolo_state['viewports'])
                }

            emit_socketio('yolo_counts', yolo_snapshot)

        # Type 3: New violation events (nokia/safety/violations/new)
        elif 'new' in topic.lower():
            violation_data['type'] = 'new_violation'
            violation_data['event_id'] = payload.get('event_id')
            violation_data['track_id'] = payload.get('track_id')
            violation_data['violation_type'] = payload.get('violation_type')
            violation_data['viewport'] = payload.get('viewport')
            violation_data['confidence'] = payload.get('confidence')
            violation_data['robot_id'] = payload.get('robot_id')
            location = payload.get('location') or payload.get('waypoint') or payload.get('zone')
            if isinstance(location, dict):
                location = location.get('name') or json.dumps(location)
            violation_data['location'] = location
            violation_data['severity'] = payload.get('severity', 'medium')

            # Emit individual violation alert
            if in_app_notifications_enabled():
                emit_socketio('violation_alert', violation_data)
            alert_manager.notify_violation(violation_data)

            # Persist violation if robot_id is provided
            if violation_data.get('robot_id') and violation_data.get('location'):
                try:
                    db.add_violation(
                        robot_id=violation_data['robot_id'],
                        location=violation_data['location'],
                        violation_type=violation_data.get('violation_type') or 'unknown',
                        image_path=payload.get('image_path'),
                        severity=violation_data.get('severity', 'medium'),
                        details=json.dumps(payload)
                    )
                except Exception as exc:
                    logger.error(f"Failed to persist violation: {exc}")

        # Store detailed violation data
        violation_data_store.insert(0, violation_data)
        if len(violation_data_store) > MAX_VIOLATIONS:
            violation_data_store = violation_data_store[:MAX_VIOLATIONS]

    except Exception as e:
        logger.error(f"Error processing YOLO topic: {e}")


def on_cloud_violation(violation_data):
    """Handle parsed violation data from cloud_mqtt_monitor"""
    global yolo_state, violation_data_store, last_yolo_payload

    try:
        if not yolo_state.get('enabled', True):
            return
        def _safe_int(value, default=0):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return default

        def _clamp_violations(total_violations, total_people):
            total_violations = _safe_int(total_violations, 0)
            total_people = _safe_int(total_people, 0)
            if total_people < 0:
                total_people = 0
            if total_violations < 0:
                total_violations = 0
            if total_people >= 0 and total_violations > total_people:
                total_violations = total_people
            return total_violations, total_people

        # This is called by cloud_mqtt_monitor.py after parsing
        violation_data_store.insert(0, violation_data)
        if len(violation_data_store) > MAX_VIOLATIONS:
            violation_data_store = violation_data_store[:MAX_VIOLATIONS]

        with yolo_state_lock:
            last_yolo_payload = {
                'topic': violation_data.get('topic', 'nokia/safety/violations'),
                'timestamp': violation_data.get('timestamp'),
                'payload': violation_data.get('payload')
            }

        # Update YOLO state based on violation type
        if violation_data['type'] == 'summary':
            with yolo_state_lock:
                yolo_state['last_message_time'] = violation_data['timestamp']
                total_violations, total_people = _clamp_violations(
                    violation_data.get('total_violations', 0),
                    violation_data.get('total_people', yolo_state.get('total_people', 0))
                )
                robot_id = violation_data.get('robot_id')
                if robot_id:
                    total_violations = _smooth_violations(int(robot_id), total_violations)
                yolo_state['total_violations'] = total_violations
                yolo_state['total_people'] = total_people

                viewports = violation_data.get('viewports', {})
                for vp_name, vp_data in viewports.items():
                    if vp_name in yolo_state['viewports']:
                        yolo_state['viewports'][vp_name] = vp_data.get('violations', 0)

                yolo_snapshot = {
                    'enabled': yolo_state['enabled'],
                    'last_message_time': yolo_state['last_message_time'],
                    'total_violations': yolo_state['total_violations'],
                    'total_people': yolo_state['total_people'],
                    'viewports': dict(yolo_state['viewports'])
                }

            emit_socketio('yolo_summary', yolo_snapshot)

        elif violation_data['type'] == 'counts':
            with yolo_state_lock:
                yolo_state['last_message_time'] = violation_data['timestamp']
                total_violations, total_people = _clamp_violations(
                    violation_data.get('total_violations', 0),
                    violation_data.get('total_people', 0)
                )
                robot_id = violation_data.get('robot_id')
                if robot_id:
                    total_violations = _smooth_violations(int(robot_id), total_violations)
                yolo_state['total_violations'] = total_violations
                yolo_state['total_people'] = total_people

                viewports = violation_data.get('viewports', {})
                for vp_name, vp_data in viewports.items():
                    if vp_name in yolo_state['viewports']:
                        yolo_state['viewports'][vp_name] = vp_data.get('violations', 0)

                yolo_snapshot = {
                    'enabled': yolo_state['enabled'],
                    'last_message_time': yolo_state['last_message_time'],
                    'total_violations': yolo_state['total_violations'],
                    'total_people': yolo_state['total_people'],
                    'viewports': dict(yolo_state['viewports'])
                }

            emit_socketio('yolo_counts', yolo_snapshot)

        elif violation_data['type'] == 'new_violation':
            # Ensure location is a string, not a dict
            location = violation_data.get('location')
            if isinstance(location, dict):
                location = location.get('name') or json.dumps(location)
                violation_data['location'] = location

            if in_app_notifications_enabled():
                emit_socketio('violation_alert', violation_data)
            alert_manager.notify_violation(violation_data)

            if violation_data.get('robot_id') and violation_data.get('location'):
                try:
                    db.add_violation(
                        robot_id=violation_data['robot_id'],
                        location=violation_data['location'],
                        violation_type=violation_data.get('violation_type') or 'unknown',
                        image_path=violation_data.get('image_path'),
                        severity=violation_data.get('severity', 'medium'),
                        details=json.dumps(violation_data.get('payload', {}))
                    )
                except Exception as exc:
                    logger.error(f"Failed to persist violation: {exc}")

    except Exception as e:
        logger.error(f"Error handling cloud violation: {e}")


# MQTT Callbacks
def on_mqtt_message(robot_id, serial_number, topic, payload):
    """Handle MQTT messages from robots"""
    try:
        logger.info(f"MQTT message from robot {robot_id}: {topic}")

        # Store message in history for monitoring tab
        global mqtt_message_history
        with mqtt_history_lock:
            mqtt_message_history.insert(0, {
                'timestamp': datetime.now().isoformat(),
                'robot_id': robot_id,
                'serial_number': serial_number,
                'topic': topic,
                'payload': payload
            })
            # Keep only recent messages
            if len(mqtt_message_history) > MAX_MQTT_HISTORY:
                mqtt_message_history = mqtt_message_history[:MAX_MQTT_HISTORY]

        # Emit to monitoring tab (BROADCAST to all connected clients)
        emit_socketio('mqtt_message', {
            'timestamp': datetime.now().isoformat(),
            'robot_id': robot_id,
            'topic': topic,
            'payload': payload
        })

        # Parse topic
        topic_parts = topic.split('/')
        
        if len(topic_parts) >= 4:
            category = topic_parts[2]  # status or event
            subcategory = topic_parts[3]
            
            # Handle different message types
            if category == 'status':
                if subcategory == 'info':
                    # Robot status info (waypoint list, battery)
                    waypoint_list = payload.get('waypoint_list', [])
                    battery = None
                    for key in ['battery_percentage', 'percentage', 'battery', 'level', 'percent']:
                        if key in payload and payload.get(key) is not None:
                            battery = payload.get(key)
                            break
                    has_battery = battery is not None
                    
                    # Update robot waypoints
                    db.update_robot_waypoints(robot_id, waypoint_list)
                    
                    # Update battery
                    if has_battery:
                        db.update_robot_status(robot_id, 'connected', battery_level=battery)
                    
                    # Emit to frontend
                    emit_socketio('robot_status', {
                        'robot_id': robot_id,
                        'waypoints': waypoint_list,
                        'battery': battery if has_battery else None,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                elif subcategory == 'utils' and len(topic_parts) >= 5 and topic_parts[4] == 'battery':
                    # Battery status update
                    battery = None
                    for key in ['percentage', 'battery_percentage', 'battery', 'level', 'percent']:
                        if key in payload and payload.get(key) is not None:
                            battery = payload.get(key)
                            break
                    has_battery = battery is not None
                    is_charging = payload.get('is_charging', False)
                    
                    # Update database
                    if has_battery:
                        db.update_robot_status(robot_id, 'connected', battery_level=battery, is_charging=is_charging)
                    
                    # Update patrol manager
                    if has_battery:
                        patrol_manager.update_battery_level(robot_id, battery, is_charging)
                    
                    # Emit to frontend
                    if has_battery:
                        emit_socketio('battery_update', {
                            'robot_id': robot_id,
                            'battery': battery,
                            'is_charging': is_charging,
                            'timestamp': datetime.now().isoformat()
                        })
                    
                    # Check for low battery alert
                    if has_battery:
                        low_battery_threshold = int(db.get_setting('low_battery_threshold', 10))
                        if battery <= low_battery_threshold and not is_charging and in_app_notifications_enabled():
                            emit_socketio('low_battery_alert', {
                                'robot_id': robot_id,
                                'battery': battery,
                                'timestamp': datetime.now().isoformat()
                            })

                            # Log activity
                            db.add_activity_log(robot_id, 'warning',
                                              f'Low battery alert: {battery}%')

                elif subcategory == 'position':
                    # Position tracking update (X, Y, theta)
                    x = payload.get('x', 0.0)
                    y = payload.get('y', 0.0)
                    theta = payload.get('theta', 0.0)
                    timestamp = payload.get('timestamp', datetime.now().timestamp())
                    try:
                        timestamp = float(timestamp)
                    except Exception:
                        timestamp = datetime.now().timestamp()
                    if timestamp > 1e11:
                        timestamp = timestamp / 1000.0

                    # Update position tracker
                    position_tracker.update_position(robot_id, x, y, theta, timestamp)

                    # Emit to frontend
                    emit_socketio('position_update', {
                        'robot_id': robot_id,
                        'position': {
                            'x': x,
                            'y': y,
                            'theta': theta,
                            'timestamp': timestamp
                        },
                        'timestamp': datetime.now().isoformat()
                    })

                    # Log activity (only every 10th update to reduce noise)
                    if timestamp % 10 == 0:
                        db.add_activity_log(robot_id, 'debug',
                                          f'Position: X={x:.2f}, Y={y:.2f}, θ={theta:.1f}°')

                elif subcategory == 'map':
                    try:
                        _handle_map_image_message(robot_id, serial_number, topic, payload)
                    except Exception as exc:
                        logger.error(f"Failed to process map image: {exc}")

            elif category == 'event':
                if subcategory == 'waypoint':
                    if len(topic_parts) >= 5:
                        event_type = topic_parts[4]  # goto or arrived
                        
                        location = payload.get('location', '')
                        status = payload.get('status', '')
                        
                        # Update patrol manager
                        patrol_manager.on_waypoint_event(robot_id, event_type, location, status)
                        
                        # Update robot location if arrived
                        if event_type == 'arrived' or (event_type == 'goto' and status == 'complete'):
                            db.update_robot_status(robot_id, 'connected', current_location=location)
                        
                        # Emit to frontend
                        emit_socketio('waypoint_event', {
                            'robot_id': robot_id,
                            'event_type': event_type,
                            'location': location,
                            'status': status,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        # Log activity
                        db.add_activity_log(robot_id, 'info', 
                                          f'Waypoint event: {event_type} - {location} ({status})')
                
                elif subcategory == 'user':
                    # User interaction or detection events
                    emit_socketio('user_event', {
                        'robot_id': robot_id,
                        'payload': payload,
                        'timestamp': datetime.now().isoformat()
                    })
    
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}")


def on_mqtt_connect(robot_id, serial_number):
    """Handle MQTT connection"""
    logger.info(f"Robot {robot_id} connected to MQTT")
    
    # Update database
    db.update_robot_status(robot_id, 'connected')
    
    # Emit to frontend
    emit_socketio('robot_connected', {
        'robot_id': robot_id,
        'serial_number': serial_number,
        'timestamp': datetime.now().isoformat()
    })
    
    # Log activity
    db.add_activity_log(robot_id, 'info', f'Robot connected to MQTT')


def on_mqtt_disconnect(robot_id, serial_number, rc):
    """Handle MQTT disconnection"""
    logger.info(f"Robot {robot_id} disconnected from MQTT (rc: {rc})")
    
    # Update database
    db.update_robot_status(robot_id, 'disconnected')
    
    # Emit to frontend
    emit_socketio('robot_disconnected', {
        'robot_id': robot_id,
        'serial_number': serial_number,
        'rc': rc,
        'timestamp': datetime.now().isoformat()
    })
    
    # Log activity
    db.add_activity_log(robot_id, 'warning', f'Robot disconnected from MQTT')


# Patrol Manager Callbacks
def on_patrol_status_update(status):
    """Handle patrol status updates"""
    emit_socketio('patrol_status_update', status)
    emit_active_patrol_count()


def on_patrol_waypoint_reached(robot_id, waypoint_index, waypoint):
    """Handle patrol waypoint reached"""
    logger.info(f"Robot {robot_id} reached waypoint {waypoint_index}: {waypoint['waypoint_name']}")
    
    emit_socketio('patrol_waypoint_reached', {
        'robot_id': robot_id,
        'waypoint_index': waypoint_index,
        'waypoint': waypoint,
        'timestamp': datetime.now().isoformat()
    })
    
    # Log activity
    db.add_activity_log(robot_id, 'info', 
                       f"Reached waypoint: {waypoint['waypoint_name']}")


def on_patrol_complete(robot_id):
    """Handle patrol completion"""
    logger.info(f"Patrol completed for robot {robot_id}")
    
    emit_socketio('patrol_complete', {
        'robot_id': robot_id,
        'timestamp': datetime.now().isoformat()
    })

    try:
        with yolo_process_lock:
            running = yolo_process and yolo_process.poll() is None
        if running:
            timeout = int(db.get_setting('yolo_shutdown_timeout', 30) or 30)
            emit_socketio('yolo_shutdown_prompt', {
                'robot_id': robot_id,
                'timeout': timeout
            })
    except Exception as exc:
        logger.error(f"Failed to emit YOLO shutdown prompt: {exc}")

    try:
        session_id = active_detection_sessions.pop(robot_id, None)
        if session_id:
            with yolo_state_lock:
                violations_count = yolo_state.get('total_violations', 0)
            db.end_detection_session(session_id, violations_count)
    except Exception as exc:
        logger.error(f"Failed to end detection session: {exc}")

    try:
        summary_data = _finalize_patrol_tracking(robot_id, 'completed')
        if summary_data:
            emit_socketio('patrol_summary', summary_data)
            alert_manager.send_patrol_summary(summary_data)
    except Exception as exc:
        logger.error(f"Failed to send patrol summary: {exc}")
    
    # Log activity
    db.add_activity_log(robot_id, 'info', 'Patrol completed')
    emit_active_patrol_count()


def on_patrol_error(robot_id, error_message):
    """Handle patrol errors"""
    logger.error(f"Patrol error for robot {robot_id}: {error_message}")
    
    emit_socketio('patrol_error', {
        'robot_id': robot_id,
        'error': error_message,
        'timestamp': datetime.now().isoformat()
    })
    
    # Log activity
    db.add_activity_log(robot_id, 'error', f'Patrol error: {error_message}')
    try:
        _finalize_patrol_tracking(robot_id, 'error')
    except Exception as exc:
        logger.error(f"Failed to finalize patrol tracking on error: {exc}")
    emit_active_patrol_count()


def on_waypoint_summary(robot_id, route, waypoint, summary, action_taken, notes):
    """Handle waypoint summary logging"""
    try:
        route_id = route.get('id') if isinstance(route, dict) else None
        waypoint_name = waypoint.get('waypoint_name') if isinstance(waypoint, dict) else 'unknown'
        db.add_waypoint_summary(
            robot_id,
            route_id,
            waypoint_name,
            summary,
            action_taken=action_taken,
            notes=notes
        )
        db.add_activity_log(
            robot_id,
            'info',
            f"Waypoint summary recorded for {waypoint_name}",
            details=json.dumps({
                'total_violations': summary.get('total_violations', 0),
                'total_people': summary.get('total_people', 0),
                'action_taken': action_taken,
                'notes': notes
            })
        )
    except Exception as exc:
        logger.error(f"Failed to record waypoint summary: {exc}")


# Set callbacks
mqtt_manager.set_callbacks(
    on_message=on_mqtt_message,
    on_connect=on_mqtt_connect,
    on_disconnect=on_mqtt_disconnect
)

patrol_manager.set_callbacks(
    on_status_update=on_patrol_status_update,
    on_waypoint_reached=on_patrol_waypoint_reached,
    on_complete=on_patrol_complete,
    on_error=on_patrol_error,
    yolo_state_provider=get_yolo_snapshot,
    on_waypoint_summary=on_waypoint_summary
)


_system_initialized = False


@app.before_request
def initialize_system():
    """Initialize MQTT connections on first request (Flask 3 compatible)"""
    global _system_initialized
    if _system_initialized:
        return
    connect_saved_robots()
    start_cloud_monitor_from_settings()
    _system_initialized = True


# Routes
@app.route('/')
def index():
    """Redirect to dashboard"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = db.authenticate_user(username, password)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True
            
            logger.info(f"User {username} logged in")
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"User {username} logged out")
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page"""
    robots = db.get_all_robots()
    return render_template('dashboard.html', robots=robots, username=session.get('username'))


@app.route('/robots')
@login_required
def robots():
    """Robots management page"""
    robots_list = db.get_all_robots()
    return render_template('robots.html', robots=robots_list, username=session.get('username'))


@app.route('/routes')
@login_required
def routes():
    """Routes management page"""
    routes_list = db.get_all_routes()
    robots_list = db.get_all_robots()
    return render_template('routes.html', routes=routes_list, robots=robots_list, 
                         username=session.get('username'))


@app.route('/settings')
@login_required
def settings_page():
    """Settings page"""
    settings = db.get_all_settings()
    return render_template('settings.html', settings=settings, username=session.get('username'))


@app.route('/logs')
@login_required
def logs():
    """Activity logs page"""
    logs_list = db.get_activity_logs(limit=500)
    robots_list = db.get_all_robots()
    return render_template('logs.html', logs=logs_list, robots=robots_list,
                         username=session.get('username'))


@app.route('/commands')
@login_required
def commands_page():
    """Commands testing page"""
    robots_list = db.get_all_robots()
    return render_template('commands.html', robots=robots_list,
                         username=session.get('username'))


@app.route('/sdk-commands')
@login_required
def sdk_commands_page():
    """SDK commands control page"""
    robots_list = db.get_all_robots()
    return render_template('sdk_commands.html', robots=robots_list,
                         username=session.get('username'))


@app.route('/yolo')
@login_required
def yolo_monitor():
    """YOLO monitoring page"""
    return render_template('yolo.html', username=session.get('username'))


@app.route('/mqtt-monitor')
@login_required
def mqtt_monitor():
    """MQTT topic monitoring page"""
    return render_template('mqtt_monitor.html', username=session.get('username'))


@app.route('/patrol-control')
@login_required
def patrol_control():
    """Full size patrol control page"""
    return render_template('patrol_control.html', username=session.get('username'))


@app.route('/position-tracking')
@login_required
def position_tracking_page():
    """Position tracking page"""
    robots_list = db.get_all_robots()
    return render_template('position_tracking.html', robots=robots_list,
                         username=session.get('username'))


@app.route('/map-management')
@login_required
def map_management_page():
    """Map management page"""
    robots_list = db.get_all_robots()
    return render_template('map_management.html', robots=robots_list,
                         username=session.get('username'))


@app.route('/schedules')
@login_required
def schedules_page():
    """Patrol scheduling page"""
    routes_list = db.get_all_routes()
    robots_list = db.get_all_robots()
    return render_template('schedules.html', routes=routes_list, robots=robots_list,
                         username=session.get('username'))


@app.route('/detection-sessions')
@login_required
def detection_sessions_page():
    """Detection sessions page"""
    robots_list = db.get_all_robots()
    routes_list = db.get_all_routes()
    return render_template('detection_sessions.html', robots=robots_list, routes=routes_list,
                         username=session.get('username'))


@app.route('/violations')
@login_required
def violations_page():
    """Violations tracking page"""
    robots_list = db.get_all_robots()
    return render_template('violations.html', robots=robots_list, username=session.get('username'))


# API Routes - Robots
@app.route('/api/robots', methods=['GET'])
@login_required
def api_get_robots():
    """Get all robots"""
    robots = db.get_all_robots()
    
    # Add connection status from MQTT manager
    for robot in robots:
        robot['mqtt_connected'] = mqtt_manager.is_robot_connected(robot['id'])
        robot['waypoints'] = json.loads(robot.get('waypoints_json', '[]'))
    
    return jsonify({'success': True, 'robots': robots})


@app.route('/api/robots/<int:robot_id>', methods=['GET'])
@login_required
def api_get_robot(robot_id):
    """Get robot by ID"""
    robot = db.get_robot_by_id(robot_id)
    
    if robot:
        robot['mqtt_connected'] = mqtt_manager.is_robot_connected(robot_id)
        robot['waypoints'] = json.loads(robot.get('waypoints_json', '[]'))
        return jsonify({'success': True, 'robot': robot})
    
    return jsonify({'success': False, 'error': 'Robot not found'}), 404


@app.route('/api/robots/<int:robot_id>/upload-map', methods=['POST'])
@login_required
def api_upload_robot_map(robot_id):
    """Upload a map image for a robot"""
    if 'map_image' not in request.files:
        return jsonify({'success': False, 'error': 'No map_image file provided'}), 400

    robot = db.get_robot(robot_id)
    if not robot:
        return jsonify({'success': False, 'error': 'Robot not found'}), 404

    file = request.files['map_image']
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'Invalid file'}), 400

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg']:
        return jsonify({'success': False, 'error': 'Only PNG/JPG images allowed'}), 400

    os.makedirs(os.path.join('static', 'maps'), exist_ok=True)
    safe_name = f"{robot['serial_number']}{ext}"
    path = os.path.join('static', 'maps', safe_name)
    file.save(path)
    url = f"/static/maps/{safe_name}"

    db.update_robot(robot_id, map_image_url=url)
    return jsonify({'success': True, 'url': url})


@app.route('/api/robots', methods=['POST'])
@login_required
def api_create_robot():
    """Create new robot"""
    data = request.json
    
    name = data.get('name')
    serial_number = data.get('serial_number')
    
    if not name or not serial_number:
        return jsonify({'success': False, 'error': 'Name and serial number required'}), 400
    
    # MQTT config
    mqtt_config = {
        'broker_url': data.get('mqtt_broker_url') or db.get_setting('default_mqtt_broker'),
        'port': int(data.get('mqtt_port') or db.get_setting('default_mqtt_port', 8883)),
        'username': data.get('mqtt_username') or db.get_setting('default_mqtt_username'),
        'password': data.get('mqtt_password') or db.get_setting('default_mqtt_password', ''),
        'use_tls': data.get('use_tls', True)
    }
    
    try:
        robot_id = db.create_robot(name, serial_number, mqtt_config)
        
        # Connect to MQTT
        mqtt_manager.add_robot(
            robot_id, serial_number,
            mqtt_config['broker_url'], mqtt_config['port'],
            mqtt_config['username'], mqtt_config['password'],
            mqtt_config['use_tls']
        )
        
        # Log activity
        db.add_activity_log(robot_id, 'info', f'Robot created: {name}')
        
        return jsonify({'success': True, 'robot_id': robot_id})
        
    except Exception as e:
        logger.error(f"Error creating robot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/robots/<int:robot_id>', methods=['PUT'])
@login_required
def api_update_robot(robot_id):
    """Update robot"""
    data = request.json
    
    # Filter allowed fields
    allowed_fields = ['name', 'mqtt_broker_url', 'mqtt_port', 'mqtt_username', 
                     'mqtt_password', 'use_tls']
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    
    if db.update_robot(robot_id, **updates):
        # If MQTT config changed, reconnect
        if any(k in updates for k in ['mqtt_broker_url', 'mqtt_port', 'mqtt_username', 
                                      'mqtt_password', 'use_tls']):
            robot = db.get_robot_by_id(robot_id)
            mqtt_manager.remove_robot(robot_id)
            mqtt_manager.add_robot(
                robot_id, robot['serial_number'],
                robot['mqtt_broker_url'], robot['mqtt_port'],
                robot['mqtt_username'], robot['mqtt_password'],
                robot['use_tls']
            )
        
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to update robot'}), 500


@app.route('/api/robots/<int:robot_id>', methods=['DELETE'])
@login_required
def api_delete_robot(robot_id):
    """Delete robot"""
    # Disconnect from MQTT
    mqtt_manager.remove_robot(robot_id)
    
    # Delete from database
    if db.delete_robot(robot_id):
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to delete robot'}), 500


@app.route('/api/robots/<int:robot_id>/connect', methods=['POST'])
@login_required
def api_connect_robot(robot_id):
    """Connect robot to MQTT"""
    robot = db.get_robot_by_id(robot_id)
    
    if not robot:
        return jsonify({'success': False, 'error': 'Robot not found'}), 404
    
    # Connect to MQTT (idempotent)
    success = ensure_robot_connected(robot_id)
    
    if success:
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to connect'}), 500


@app.route('/api/robots/<int:robot_id>/disconnect', methods=['POST'])
@login_required
def api_disconnect_robot(robot_id):
    """Disconnect robot from MQTT"""
    mqtt_manager.remove_robot(robot_id)
    return jsonify({'success': True})


# API Routes - Routes
@app.route('/api/routes', methods=['GET'])
@login_required
def api_get_routes():
    """Get all routes"""
    robot_id = request.args.get('robot_id', type=int)
    routes_list = db.get_all_routes(robot_id)
    return jsonify({'success': True, 'routes': routes_list})


@app.route('/api/routes/<int:route_id>', methods=['GET'])
@login_required
def api_get_route(route_id):
    """Get route by ID"""
    route = db.get_route_by_id(route_id)
    
    if route:
        return jsonify({'success': True, 'route': route})
    
    return jsonify({'success': False, 'error': 'Route not found'}), 404


@app.route('/api/routes', methods=['POST'])
@login_required
def api_create_route():
    """Create new route"""
    data = request.json
    
    name = data.get('name')
    robot_id = data.get('robot_id')
    waypoints = data.get('waypoints', [])
    loop_count = data.get('loop_count', 1)  # Default to 1 loop
    return_location = data.get('return_location')
    
    if not name or not robot_id or not waypoints:
        return jsonify({'success': False, 'error': 'Name, robot_id, and waypoints required'}), 400
    
    try:
        route_id = db.create_route(name, robot_id, waypoints, loop_count, return_location)
        
        # Log activity
        loop_text = "infinite loops" if loop_count <= 0 else f"{loop_count} loop(s)"
        db.add_activity_log(robot_id, 'info', f'Route created: {name} ({loop_text})')
        
        return jsonify({'success': True, 'route_id': route_id})
        
    except Exception as e:
        logger.error(f"Error creating route: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/routes/<int:route_id>', methods=['PUT'])
@login_required
def api_update_route(route_id):
    """Update route"""
    data = request.json
    
    name = data.get('name')
    waypoints = data.get('waypoints')
    loop_count = data.get('loop_count')
    return_location = data.get('return_location')
    
    if db.update_route(route_id, name, waypoints, loop_count, return_location):
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to update route'}), 500


@app.route('/api/routes/<int:route_id>', methods=['DELETE'])
@login_required
def api_delete_route(route_id):
    """Delete route"""
    if db.delete_route(route_id):
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to delete route'}), 500


# API Routes - Patrol Control
@app.route('/api/patrol/start', methods=['POST'])
@login_required
def api_start_patrol():
    """Start patrol"""
    data = request.json
    
    robot_id = data.get('robot_id')
    route_id = data.get('route_id')
    
    if not robot_id or not route_id:
        return jsonify({'success': False, 'error': 'robot_id and route_id required'}), 400
    
    # Get route
    route = db.get_route_by_id(route_id)
    
    if not route:
        return jsonify({'success': False, 'error': 'Route not found'}), 404
    
    # Start patrol
    success = patrol_manager.start_patrol(robot_id, route)
    
    if success:
        _start_patrol_tracking(robot_id, route)
        try:
            start_yolo_pipeline()
        except Exception as exc:
            logger.error(f"Failed to start YOLO pipeline: {exc}")
        try:
            session_id = db.start_detection_session(robot_id, route_id)
            active_detection_sessions[robot_id] = session_id
        except Exception as exc:
            logger.error(f"Failed to start detection session: {exc}")
        db.add_activity_log(robot_id, 'info', f'Started patrol: {route["name"]}')
        emit_active_patrol_count()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to start patrol'}), 500


@app.route('/api/patrol/stop', methods=['POST'])
@login_required
def api_stop_patrol():
    """Stop patrol"""
    data = request.json
    robot_id = data.get('robot_id')
    
    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400
    
    if patrol_manager.stop_patrol(robot_id):
        try:
            session_id = active_detection_sessions.pop(robot_id, None)
            if session_id:
                with yolo_state_lock:
                    violations_count = yolo_state.get('total_violations', 0)
                db.end_detection_session(session_id, violations_count)
        except Exception as exc:
            logger.error(f"Failed to end detection session: {exc}")
        try:
            _finalize_patrol_tracking(robot_id, 'stopped')
        except Exception as exc:
            logger.error(f"Failed to finalize patrol tracking: {exc}")
        db.add_activity_log(robot_id, 'info', 'Stopped patrol')
        emit_active_patrol_count()
        emit_socketio('patrol_status_update', {
            'robot_id': robot_id,
            'state': 'stopped',
            'current_waypoint_index': 0,
            'total_waypoints': 0,
            'current_waypoint': None,
            'current_loop': 0,
            'total_loops': 0,
            'is_infinite_loop': False
        })
        emit_socketio('patrol_complete', {
            'robot_id': robot_id,
            'timestamp': datetime.now().isoformat(),
            'stopped': True
        })
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to stop patrol'}), 500


@app.route('/api/patrol/pause', methods=['POST'])
@login_required
def api_pause_patrol():
    """Pause patrol"""
    data = request.json
    robot_id = data.get('robot_id')
    
    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400
    
    if patrol_manager.pause_patrol(robot_id):
        db.add_activity_log(robot_id, 'info', 'Paused patrol')
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to pause patrol'}), 500


@app.route('/api/patrol/resume', methods=['POST'])
@login_required
def api_resume_patrol():
    """Resume patrol"""
    data = request.json
    robot_id = data.get('robot_id')
    
    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400
    
    if patrol_manager.resume_patrol(robot_id):
        db.add_activity_log(robot_id, 'info', 'Resumed patrol')
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to resume patrol'}), 500


@app.route('/api/patrol/speed', methods=['POST'])
@login_required
def api_set_patrol_speed():
    """Set patrol speed"""
    data = request.json
    robot_id = data.get('robot_id')
    speed = data.get('speed')
    
    if not robot_id or speed is None:
        return jsonify({'success': False, 'error': 'robot_id and speed required'}), 400
    
    if patrol_manager.set_patrol_speed(robot_id, float(speed)):
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to set speed'}), 500


@app.route('/api/patrol/status/<int:robot_id>', methods=['GET'])
@login_required
def api_get_patrol_status(robot_id):
    """Get patrol status"""
    status = patrol_manager.get_patrol_status(robot_id)
    
    if status:
        return jsonify({'success': True, 'status': status})
    
    return jsonify({'success': True, 'status': None})


@app.route('/api/patrol/active-count', methods=['GET'])
@login_required
def api_get_active_patrol_count():
    """Get active patrol count"""
    count = patrol_manager.get_active_patrol_count()
    return jsonify({'success': True, 'count': count})


# API Routes - Commands
@app.route('/api/command/goto', methods=['POST'])
@login_required
def api_goto_waypoint():
    """Send goto waypoint command"""
    data = request.json
    robot_id = data.get('robot_id')
    location = data.get('location')
    
    if not robot_id or not location:
        return jsonify({'success': False, 'error': 'robot_id and location required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400
    
    if mqtt_manager.goto_waypoint(robot_id, location):
        db.add_activity_log(robot_id, 'info', f'Sent goto command: {location}')
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/home', methods=['POST'])
@login_required
def api_goto_home():
    """Send goto home base command"""
    data = request.json
    robot_id = data.get('robot_id')
    
    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400
    
    home_location = db.get_setting('home_base_location', 'home base')
    
    if mqtt_manager.goto_waypoint(robot_id, home_location):
        db.add_activity_log(robot_id, 'info', f'Sent goto home base: {home_location}')
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/stop', methods=['POST'])
@login_required
def api_stop_movement():
    """Send stop movement command"""
    data = request.json
    robot_id = data.get('robot_id')

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    if mqtt_manager.stop_movement(robot_id):
        db.add_activity_log(robot_id, 'info', 'Sent stop movement command')
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/webview', methods=['POST'])
@login_required
def api_show_webview():
    """Send webview command to display HTML file or URL"""
    data = request.json
    robot_id = data.get('robot_id')
    url = data.get('url')

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not url:
        return jsonify({'success': False, 'error': 'url required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    # If path doesn't start with file:// or http(s)://, assume it's a local file path
    if not url.startswith('file://') and not url.startswith('http://') and not url.startswith('https://'):
        # Convert local path to file:// URL
        # For Android, storage paths are typically /storage/emulated/0/...
        if not url.startswith('/'):
            url = '/storage/emulated/0/' + url
        url = 'file://' + url

    if mqtt_manager.show_webview(robot_id, url):
        db.add_activity_log(robot_id, 'info', f'Sent webview command: {url}')
        return jsonify({'success': True, 'url': url})

    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/webviewclose', methods=['POST'])
@login_required
def api_close_webview():
    """Close webview on robot"""
    data = request.json
    robot_id = data.get('robot_id')

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    if mqtt_manager.close_webview(robot_id):
        db.add_activity_log(robot_id, 'info', 'Sent webview close command')
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/tts', methods=['POST'])
@login_required
def api_send_tts():
    """Send text-to-speech command"""
    data = request.json
    robot_id = data.get('robot_id')
    utterance = data.get('utterance')

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not utterance:
        return jsonify({'success': False, 'error': 'utterance required'}), 400

    # Check if robot is connected
    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    if mqtt_manager.speak_tts(robot_id, utterance):
        db.add_activity_log(robot_id, 'info', f'Sent TTS command: {utterance[:50]}...')
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Failed to send command. Check MQTT connection.'}), 500


@app.route('/api/command/video', methods=['POST'])
@login_required
def api_play_video():
    """Send video playback command"""
    data = request.json
    robot_id = data.get('robot_id')
    url = data.get('url')

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not url:
        return jsonify({'success': False, 'error': 'url required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    # If path doesn't start with file:// or http(s)://, assume it's a local file path
    if not url.startswith('file://') and not url.startswith('http://') and not url.startswith('https://'):
        # Convert local path to file:// URL
        if not url.startswith('/'):
            url = '/storage/emulated/0/' + url
        url = 'file://' + url

    if mqtt_manager.play_video(robot_id, url):
        db.add_activity_log(robot_id, 'info', f'Sent video command: {url}')
        return jsonify({'success': True, 'url': url})

    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/joystick', methods=['POST'])
@login_required
def api_joystick_move():
    """Send joystick movement command"""
    data = request.json
    robot_id = data.get('robot_id')
    x = data.get('x', 0.0)
    y = data.get('y', 0.0)
    theta = data.get('theta', 0.0)

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    if mqtt_manager.joystick_move(robot_id, x, y, theta):
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/tilt', methods=['POST'])
@login_required
def api_tilt_camera():
    """Tilt camera command"""
    data = request.json
    robot_id = data.get('robot_id')
    degrees = data.get('degrees', 0)

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    try:
        degrees = int(degrees)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'degrees must be an integer'}), 400

    if degrees < -25 or degrees > 60:
        return jsonify({'success': False, 'error': 'degrees must be between -25 and 60'}), 400

    if mqtt_manager.tilt_camera(robot_id, degrees):
        db.add_activity_log(robot_id, 'info', f'Tilted camera to {degrees} degrees')
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/turn', methods=['POST'])
@login_required
def api_turn_by_angle():
    """Turn by angle command"""
    data = request.json
    robot_id = data.get('robot_id')
    angle = data.get('angle', 0)

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    try:
        angle = int(angle)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'angle must be an integer'}), 400

    if angle < -360 or angle > 360:
        return jsonify({'success': False, 'error': 'angle must be between -360 and 360'}), 400

    if mqtt_manager.turn_by_angle(robot_id, angle):
        db.add_activity_log(robot_id, 'info', f'Turned by {angle} degrees')
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Failed to send command'}), 500


@app.route('/api/command/waypoints', methods=['POST'])
@login_required
def api_request_waypoints():
    """Request waypoint list from robot"""
    data = request.json
    robot_id = data.get('robot_id')
    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    if mqtt_manager.request_waypoints(robot_id):
        db.add_activity_log(robot_id, 'info', 'Requested waypoint list')
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to request waypoints'}), 500


@app.route('/api/command/custom', methods=['POST'])
@login_required
def api_custom_mqtt():
    """Send custom MQTT topic/payload"""
    data = request.json or {}
    robot_id = data.get('robot_id')
    topic = (data.get('topic') or '').strip()
    payload = data.get('payload')

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400
    if not topic:
        return jsonify({'success': False, 'error': 'topic required'}), 400

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot is not connected to MQTT. Please connect robot first.'}), 400

    if payload is None:
        payload = {}

    if not isinstance(payload, dict):
        return jsonify({'success': False, 'error': 'payload must be a JSON object'}), 400

    if mqtt_manager.publish_raw(robot_id, topic, payload):
        db.add_activity_log(robot_id, 'info', f'Custom MQTT: {topic}')
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to send MQTT command'}), 500


# Volume Control Endpoint
@app.route('/api/command/volume', methods=['POST'])
@login_required
def api_set_volume():
    """Set robot volume via MQTT"""
    try:
        data = request.json or {}
        robot_id = data.get('robot_id')
        volume = data.get('volume')

        if not robot_id:
            return jsonify({'success': False, 'error': 'robot_id required'}), 400

        if volume is None:
            return jsonify({'success': False, 'error': 'volume required'}), 400

        # Validate range (0-100)
        try:
            volume = int(volume)
            if volume < 0 or volume > 100:
                return jsonify({'success': False, 'error': 'Volume must be 0-100'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Volume must be a number'}), 400

        robot = db.get_robot(robot_id)
        if not robot:
            return jsonify({'success': False, 'error': 'Robot not found'}), 404

        if not ensure_robot_connected(robot_id):
            return jsonify({'success': False, 'error': 'Robot is not connected to MQTT'}), 400

        # Publish volume command via MQTT
        if mqtt_manager.publish_volume(robot_id, volume):
            # Store volume setting in database
            db.set_robot_setting(robot_id, 'volume_level', str(volume))

            # Log activity
            db.add_activity_log(robot_id, 'info', f'Set volume to {volume}%')

            # Emit to all connected clients
            emit_socketio('volume_changed', {
                'robot_id': robot_id,
                'volume': volume,
                'timestamp': datetime.now().isoformat()
            })

            return jsonify({'success': True, 'volume': volume})
        else:
            return jsonify({'success': False, 'error': 'Failed to publish MQTT command'}), 500

    except Exception as e:
        logger.error(f'Error setting volume: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# Get Current Volume Setting
@app.route('/api/robots/<int:robot_id>/volume', methods=['GET'])
@login_required
def api_get_volume(robot_id):
    """Get robot's volume setting"""
    try:
        robot = db.get_robot(robot_id)
        if not robot:
            return jsonify({'success': False, 'error': 'Robot not found'}), 404

        # Get stored volume level (default to 50)
        volume = int(db.get_robot_setting(robot_id, 'volume_level', '50'))

        return jsonify({'success': True, 'volume': volume})
    except Exception as e:
        logger.error(f'Error getting volume: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# System Control - Restart Robot
@app.route('/api/command/system/restart', methods=['POST'])
@login_required
def api_restart_robot():
    """Restart the robot"""
    try:
        data = request.json or {}
        robot_id = data.get('robot_id')

        if not robot_id:
            return jsonify({'success': False, 'error': 'robot_id required'}), 400

        robot = db.get_robot(robot_id)
        if not robot:
            return jsonify({'success': False, 'error': 'Robot not found'}), 404

        if not ensure_robot_connected(robot_id):
            return jsonify({'success': False, 'error': 'Robot is not connected to MQTT'}), 400

        # Log critical action
        db.add_activity_log(robot_id, 'critical', 'System restart initiated')

        # Publish restart command
        if mqtt_manager.publish_system_command(robot_id, 'restart'):
            # Update robot state
            db.set_robot_setting(robot_id, 'state', 'restarting')

            emit_socketio('robot_restarting', {
                'robot_id': robot_id,
                'message': 'Robot is restarting... (approximately 30 seconds)',
                'timestamp': datetime.now().isoformat()
            })

            # Start background monitoring for reconnection
            def monitor_restart():
                start_time = time.time()
                timeout = 60  # 60 second timeout
                while time.time() - start_time < timeout:
                    time.sleep(5)
                    current_robot = db.get_robot(robot_id)
                    if current_robot and current_robot.get('is_connected'):
                        # Robot reconnected
                        db.set_robot_setting(robot_id, 'state', 'ready')
                        emit_socketio('robot_restarted', {
                            'robot_id': robot_id,
                            'message': 'Robot has successfully restarted and reconnected!',
                            'timestamp': datetime.now().isoformat()
                        })
                        return

                # Timeout - robot didn't reconnect
                emit_socketio('robot_restart_timeout', {
                    'robot_id': robot_id,
                    'message': 'Robot did not reconnect after restart. Please check manually.',
                    'timestamp': datetime.now().isoformat()
                })

            monitoring_thread = threading.Thread(target=monitor_restart, daemon=True)
            monitoring_thread.start()

            return jsonify({
                'success': True,
                'message': 'Restart command sent. Robot will reconnect in ~30 seconds.'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to publish restart command'}), 500

    except Exception as e:
        logger.error(f'Error restarting robot: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# System Control - Shutdown Robot
@app.route('/api/command/system/shutdown', methods=['POST'])
@login_required
def api_shutdown_robot():
    """Shutdown the robot"""
    try:
        data = request.json or {}
        robot_id = data.get('robot_id')

        if not robot_id:
            return jsonify({'success': False, 'error': 'robot_id required'}), 400

        robot = db.get_robot(robot_id)
        if not robot:
            return jsonify({'success': False, 'error': 'Robot not found'}), 404

        # Log critical action with IP for audit trail
        user = session.get('username', 'unknown')
        ip_address = request.remote_addr
        db.add_activity_log(
            robot_id,
            'critical',
            f'System shutdown initiated by {user} from {ip_address}'
        )

        # Publish shutdown command only if connected
        if robot.get('is_connected'):
            if not mqtt_manager.publish_system_command(robot_id, 'shutdown'):
                return jsonify({'success': False, 'error': 'Failed to publish shutdown command'}), 500

        # Update state
        db.set_robot_setting(robot_id, 'state', 'shutting_down')

        emit_socketio('robot_shutting_down', {
            'robot_id': robot_id,
            'message': 'Shutdown command sent. Robot is powering off.',
            'timestamp': datetime.now().isoformat()
        })

        return jsonify({
            'success': True,
            'message': 'Shutdown initiated. Robot will power off.'
        })

    except Exception as e:
        logger.error(f'Error shutting down robot: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# YOLO API Routes
@app.route('/api/yolo/status', methods=['GET'])
@login_required
def api_get_yolo_status():
    """Get current YOLO status"""
    with yolo_state_lock:
        yolo_snapshot = {
            'enabled': yolo_state['enabled'],
            'last_message_time': yolo_state['last_message_time'],
            'total_violations': yolo_state['total_violations'],
            'total_people': yolo_state['total_people'],
            'viewports': dict(yolo_state['viewports'])
        }
    return jsonify({'success': True, 'yolo': yolo_snapshot})


@app.route('/api/yolo/enable', methods=['POST'])
@login_required
def api_enable_yolo():
    """Enable YOLO monitoring"""
    global yolo_state
    with yolo_state_lock:
        yolo_state['enabled'] = True
    return jsonify({'success': True})


@app.route('/api/yolo/disable', methods=['POST'])
@login_required
def api_disable_yolo():
    """Disable YOLO monitoring"""
    global yolo_state
    with yolo_state_lock:
        yolo_state['enabled'] = False
    return jsonify({'success': True})


@app.route('/api/yolo/start', methods=['POST'])
@login_required
def api_start_yolo():
    """Start YOLO pipeline subprocess"""
    if start_yolo_pipeline():
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to start YOLO'}), 400


@app.route('/api/yolo/stop', methods=['POST'])
@login_required
def api_stop_yolo():
    """Stop YOLO pipeline subprocess"""
    if stop_yolo_pipeline():
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to stop YOLO'}), 400


@app.route('/api/yolo/violations', methods=['GET'])
@login_required
def api_get_yolo_violations():
    """Get detailed violation data"""
    limit = request.args.get('limit', type=int, default=50)
    return jsonify({
        'success': True,
        'violations': violation_data_store[:limit]
    })


@app.route('/api/yolo/topics', methods=['GET'])
@login_required
def api_get_yolo_topics():
    """Get configured YOLO topics"""
    topics_str = db.get_setting('yolo_topics', 'nokia/safety/violations/summary,nokia/safety/violations/counts,nokia/safety/violations/new')
    topics = [t.strip() for t in topics_str.split(',') if t.strip()]
    return jsonify({
        'success': True,
        'topics': topics
    })


@app.route('/api/yolo/topics', methods=['POST'])
@login_required
def api_update_yolo_topics():
    """Update YOLO topics to monitor"""
    data = request.json
    topics = data.get('topics', [])

    # Save to database
    topics_str = ','.join(topics)
    db.update_setting('yolo_topics', topics_str)

    # Reconnect cloud monitor with new topics
    global cloud_monitor
    if cloud_monitor:
        logger.info("Reconnecting cloud monitor with new topics...")
        cloud_monitor.disconnect()
        cloud_monitor.topics = [(topic, 0) for topic in topics]
        cloud_monitor.connect()
    else:
        start_cloud_monitor_from_settings()

    return jsonify({'success': True})


@app.route('/api/yolo/history', methods=['GET'])
@login_required
def api_get_yolo_history():
    """Get YOLO message history (filtered from mqtt_message_history)"""
    limit = request.args.get('limit', type=int, default=50)

    # Filter messages that are YOLO-related
    with mqtt_history_lock:
        yolo_messages = [
            msg for msg in mqtt_message_history
            if msg['serial_number'] == 'CLOUD' and
            any(keyword in msg['topic'].lower() for keyword in ['safety', 'violations', 'yolo'])
        ]

    return jsonify({
        'success': True,
        'messages': yolo_messages[:limit]
    })


@app.route('/api/yolo/shutdown', methods=['POST'])
@login_required
def api_yolo_shutdown():
    """Terminate YOLO pipeline process"""
    success = stop_yolo_pipeline()
    return jsonify({'success': success})


@app.route('/api/patrol/summary', methods=['POST'])
@login_required
def api_send_patrol_summary():
    """Send patrol summary via notifications"""
    data = request.json or {}
    robot_id = data.get('robot_id')
    route_name = data.get('route_name', 'Unknown')
    loops_completed = data.get('loops_completed', 0)
    waypoints = data.get('waypoints', [])
    total_violations = sum(wp.get('total_violations', 0) for wp in waypoints)
    duration = data.get('duration', 'Unknown')

    # Build summary message
    summary_text = f"""
Patrol Summary - {route_name}

Loops Completed: {loops_completed}
Duration: {duration}
Total Violations: {total_violations}

Waypoint Breakdown:
"""

    for wp in waypoints:
        summary_text += f"  • {wp.get('name', 'Unknown')}: {wp.get('total_violations', 0)} violations\n"

    try:
        # Send via Telegram if enabled
        if db.get_setting('telegram_enabled', '').lower() in ('true', '1', 'yes', 'on'):
            alert_manager.notify_violation({
                'violation_type': 'patrol_summary',
                'location': route_name,
                'message': summary_text,
                'severity': 'info'
            })

        # Send via WhatsApp if enabled
        if db.get_setting('whatsapp_enabled', '').lower() in ('true', '1', 'yes', 'on'):
            result = alert_manager.send_whatsapp_alert(summary_text)
            if not result.get('success'):
                logger.warning(f"WhatsApp notification failed: {result.get('error')}")

        # Send via SMS if enabled
        if db.get_setting('notify_sms', '').lower() in ('true', '1', 'yes', 'on'):
            result = alert_manager.send_sms(summary_text[:160])  # SMS limited to 160 chars
            if not result.get('success'):
                logger.warning(f"SMS notification failed: {result.get('error')}")

        # Send via Email if enabled
        if db.get_setting('notify_email', '').lower() in ('true', '1', 'yes', 'on'):
            result = alert_manager.send_email('Patrol Summary', summary_text)
            if not result.get('success'):
                logger.warning(f"Email notification failed: {result.get('error')}")

        return jsonify({'success': True, 'message': 'Summary notifications sent'})

    except Exception as exc:
        logger.error(f"Failed to send patrol summary: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/stream')
@login_required
def api_stream_proxy():
    """Proxy a local stream URL to avoid mixed-content issues"""
    stream_url = request.args.get('url', '').strip()
    if not stream_url:
        return jsonify({'success': False, 'error': 'url required'}), 400

    if not stream_url.startswith('http://') and not stream_url.startswith('https://'):
        stream_url = f"http://{stream_url}"

    def generate():
        try:
            with requests.get(stream_url, stream=True, timeout=5) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        yield chunk
        except Exception as exc:
            logger.error(f"Stream proxy error: {exc}")

    content_type = 'multipart/x-mixed-replace'
    try:
        head = requests.head(stream_url, timeout=3)
        if head.ok:
            content_type = head.headers.get('Content-Type', content_type)
    except Exception:
        pass

    return Response(stream_with_context(generate()), content_type=content_type)


# Position Tracking API Routes
@app.route('/api/position/current/<int:robot_id>', methods=['GET'])
@login_required
def api_get_current_position(robot_id):
    """Get current position of a robot"""
    position = position_tracker.get_current_position(robot_id)
    if position:
        return jsonify({'success': True, 'position': position})
    return jsonify({'success': False, 'error': 'No position data available'}), 404


@app.route('/api/position/history/<int:robot_id>', methods=['GET'])
@login_required
def api_get_position_history(robot_id):
    """Get position history for a robot"""
    limit = request.args.get('limit', type=int, default=100)
    history = position_tracker.get_position_history(robot_id, limit)
    return jsonify({'success': True, 'history': history, 'count': len(history)})


@app.route('/api/position/all', methods=['GET'])
@login_required
def api_get_all_positions():
    """Get current positions of all robots"""
    all_positions = position_tracker.get_all_current_positions()
    return jsonify({'success': True, 'positions': all_positions})


@app.route('/api/position/trajectory/<int:robot_id>', methods=['GET'])
@login_required
def api_get_trajectory(robot_id):
    """Get trajectory data with distance traveled"""
    trajectory = position_tracker.get_position_history(robot_id, limit=1000)
    distance = position_tracker.calculate_distance_traveled(robot_id)
    return jsonify({
        'success': True,
        'trajectory': trajectory,
        'distance_traveled': distance,
        'point_count': len(trajectory)
    })


@app.route('/api/position/export/<int:robot_id>/<format>', methods=['GET'])
@login_required
def api_export_position_data(robot_id, format):
    """Export position data in JSON or CSV format"""
    if format.lower() == 'json':
        data = position_tracker.export_trajectory_as_json(robot_id)
        return jsonify({'success': True, 'data': data})
    elif format.lower() == 'csv':
        csv_data = position_tracker.export_trajectory_as_csv(robot_id)
        return Response(csv_data, mimetype='text/csv',
                       headers={"Content-Disposition": f"attachment;filename=position_{robot_id}.csv"})
    else:
        return jsonify({'success': False, 'error': 'Format must be json or csv'}), 400


@app.route('/api/position/clear/<int:robot_id>', methods=['POST'])
@login_required
def api_clear_position_history(robot_id):
    """Clear position history for a robot"""
    position_tracker.clear_history(robot_id)
    return jsonify({'success': True, 'message': f'Position history cleared for robot {robot_id}'})


@app.route('/api/position/request/<int:robot_id>', methods=['POST'])
@login_required
def api_request_position(robot_id):
    """Request current position from robot via MQTT"""
    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot not connected'}), 503

    robot_client = mqtt_manager.get_robot_client(robot_id)
    if robot_client and robot_client.request_position():
        return jsonify({'success': True, 'message': 'Position request sent to robot'})
    else:
        return jsonify({'success': False, 'error': 'Failed to send position request'}), 500


@app.route('/api/command/map-image', methods=['POST'])
@login_required
def api_request_map_image():
    """Request map image from robot via MQTT"""
    data = request.json or {}
    robot_id = data.get('robot_id')
    fmt = (data.get('format') or 'png').lower()
    chunk_size = data.get('chunk_size', 120000)

    if not robot_id:
        return jsonify({'success': False, 'error': 'robot_id required'}), 400

    try:
        chunk_size = int(chunk_size)
    except (TypeError, ValueError):
        chunk_size = 120000

    if fmt not in ('png', 'jpg', 'jpeg'):
        fmt = 'png'

    if not ensure_robot_connected(robot_id):
        return jsonify({'success': False, 'error': 'Robot not connected'}), 503

    if mqtt_manager.request_map_image(robot_id, chunk_size=chunk_size, fmt=fmt):
        db.add_activity_log(robot_id, 'info', 'Requested map image')
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Failed to request map image'}), 500


# MQTT Monitor API Routes
@app.route('/api/mqtt/history', methods=['GET'])
@login_required
def api_get_mqtt_history():
    """Get MQTT message history"""
    limit = request.args.get('limit', type=int, default=50)
    with mqtt_history_lock:
        messages = list(mqtt_message_history[:limit])
    return jsonify({'success': True, 'messages': messages})


@app.route('/api/mqtt/clear', methods=['POST'])
@login_required
def api_clear_mqtt_history():
    """Clear MQTT message history"""
    global mqtt_message_history
    with mqtt_history_lock:
        mqtt_message_history = []
    return jsonify({'success': True})


@app.route('/api/mqtt/publish', methods=['POST'])
@login_required
def api_mqtt_publish():
    """Publish raw MQTT message to robot"""
    try:
        data = request.json
        topic = data.get('topic')
        payload = data.get('payload', {})

        logger.info(f"[API] MQTT publish request: topic={topic}, payload={payload}")

        if not topic:
            return jsonify({'success': False, 'error': 'Missing topic'}), 400

        # Extract serial number from topic (format: temi/{serial}/command/...)
        topic_parts = topic.split('/')
        if len(topic_parts) < 2:
            return jsonify({'success': False, 'error': 'Invalid topic format'}), 400

        serial_number = topic_parts[1]
        logger.info(f"[API] Extracted serial: {serial_number}")

        robot = db.get_robot_by_serial(serial_number)

        if not robot:
            logger.error(f"[API] Robot not found: {serial_number}")
            return jsonify({'success': False, 'error': f'Robot not found: {serial_number}'}), 404

        robot_id = robot['id']
        logger.info(f"[API] Found robot: {robot_id}")

        # Ensure robot is connected (with retry)
        connected = mqtt_manager.is_robot_connected(robot_id)
        logger.info(f"[API] Robot already connected: {connected}")

        if not connected:
            logger.info(f"[API] Attempting to reconnect robot {robot_id}...")
            connected = ensure_robot_connected(robot_id)
            logger.info(f"[API] Reconnection result: {connected}")

            if not connected:
                logger.error(f"[API] Failed to connect robot {robot_id}")
                # Try anyway - the robot might be reconnecting
                # return jsonify({'success': False, 'error': 'Robot not connected to MQTT'}), 503

        # Publish to robot via MQTT
        logger.info(f"[API] Publishing via mqtt_manager.publish_raw({robot_id}, {topic}, {payload})")
        success = mqtt_manager.publish_raw(robot_id, topic, payload)
        logger.info(f"[API] Publish result: {success}")

        if success:
            logger.info(f"[API] Published to {topic}: {json.dumps(payload)}")
            db.add_activity_log(robot_id, 'info', f"MQTT publish: {topic}")
            return jsonify({'success': True, 'topic': topic})
        else:
            logger.error(f"[API] mqtt_manager.publish_raw returned False")
            return jsonify({'success': False, 'error': 'Failed to publish MQTT message'}), 500

    except Exception as e:
        logger.error(f"[API] MQTT publish exception: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# API Routes - Settings
@app.route('/api/settings', methods=['GET'])
@login_required
def api_get_settings():
    """Get all settings"""
    settings = db.get_all_settings()
    return jsonify({'success': True, 'settings': settings})


@app.route('/api/settings', methods=['POST'])
@login_required
def api_update_settings():
    """Update settings"""
    data = request.json
    
    for key, value in data.items():
        db.update_setting(key, value)
    
    # Refresh global settings
    global settings
    settings = db.get_all_settings()

    # Restart cloud monitor if MQTT settings changed
    mqtt_keys = {
        'default_mqtt_broker', 'default_mqtt_port', 'default_mqtt_username',
        'default_mqtt_password', 'default_mqtt_use_tls', 'yolo_topics'
    }
    if any(k in data for k in mqtt_keys):
        global cloud_monitor, cloud_monitor_started
        if cloud_monitor:
            cloud_monitor.disconnect()
        cloud_monitor_started = False
        start_cloud_monitor_from_settings()
    
    return jsonify({'success': True})


@app.route('/api/settings/test_smtp', methods=['POST'])
@login_required
def api_test_smtp():
    """Send a test SMTP email using current settings"""
    result = alert_manager.send_test_email()
    if result.get("success"):
        return jsonify({'success': True, 'message': 'Test email sent'})
    return jsonify({'success': False, 'error': result.get("error", "SMTP test failed")}), 400


@app.route('/api/settings/test_telegram', methods=['POST'])
@login_required
def api_test_telegram():
    """Send a test Telegram message using current settings"""
    result = alert_manager.send_test_telegram()
    if result.get("success"):
        return jsonify({'success': True, 'message': 'Test Telegram message sent'})
    return jsonify({'success': False, 'error': result.get("error", "Telegram test failed")}), 400


@app.route('/api/settings/test_whatsapp', methods=['POST'])
@login_required
def api_test_whatsapp():
    """Send a test WhatsApp message using current settings"""
    result = alert_manager.send_test_whatsapp()
    if result.get("success"):
        return jsonify({'success': True, 'message': 'Test WhatsApp message sent'})
    return jsonify({'success': False, 'error': result.get("error", "WhatsApp test failed")}), 400


# API Routes - Activity Logs
@app.route('/api/logs', methods=['GET'])
@login_required
def api_get_logs():
    """Get activity logs"""
    robot_id = request.args.get('robot_id', type=int)
    limit = request.args.get('limit', type=int, default=100)
    
    logs_list = db.get_activity_logs(robot_id, limit)
    return jsonify({'success': True, 'logs': logs_list})


@app.route('/api/logs/clear', methods=['POST'])
@login_required
def api_clear_logs():
    """Clear activity logs"""
    data = request.json
    robot_id = data.get('robot_id')
    
    db.clear_activity_logs(robot_id)
    return jsonify({'success': True})


# Register additional API routes
register_violation_routes(app, socketio, login_required)
register_schedule_routes(app, login_required, patrol_manager, mqtt_manager)
register_detection_routes(app, mqtt_manager, login_required)


# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info("WebSocket client connected")
    emit('connected', {'message': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info("WebSocket client disconnected")


if __name__ == '__main__':
    try:
        connect_saved_robots()
        start_cloud_monitor_from_settings()
        start_schedule_runner()

        # Start application
        logger.info("")
        logger.info("=" * 60)
        logger.info("Starting Temi Control Application...")
        logger.info("Access: http://localhost:5000")
        logger.info("Login: admin / admin123")
        logger.info("=" * 60)

        # Run with SocketIO
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("Shutting down...")
        mqtt_manager.disconnect_all()
        if 'cloud_monitor' in globals() and cloud_monitor:
            cloud_monitor.disconnect()
            logger.info("OK Cloud MQTT monitor disconnected")
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
