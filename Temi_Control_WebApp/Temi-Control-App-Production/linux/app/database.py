"""
Database module for Temi Control Application
Handles SQLite database operations and models
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from contextlib import contextmanager
from typing import Dict, List, Optional, Any

DATABASE_PATH = 'temi_control.db'


def _ensure_columns(conn, table: str, columns: List[Dict[str, str]]) -> None:
    """Ensure columns exist in a table (SQLite)"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}

    for col in columns:
        name = col['name']
        col_type = col['type']
        default = col.get('default')
        if name in existing:
            continue
        if default is not None:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type} DEFAULT {default}")
        else:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")
    conn.commit()


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize database with all required tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Robots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS robots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                serial_number TEXT UNIQUE NOT NULL,
                mqtt_broker_url TEXT,
                mqtt_port INTEGER,
                mqtt_username TEXT,
                mqtt_password TEXT,
                use_tls BOOLEAN DEFAULT 1,
                connection_status TEXT DEFAULT 'disconnected',
                battery_level INTEGER DEFAULT 0,
                is_charging BOOLEAN DEFAULT 0,
                current_location TEXT,
                waypoints_json TEXT DEFAULT '[]',
                last_seen TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Routes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                robot_id INTEGER NOT NULL,
                loop_count INTEGER DEFAULT 1,
                return_location TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE
            )
        ''')
        
        # Route waypoints table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS route_waypoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id INTEGER NOT NULL,
                waypoint_name TEXT NOT NULL,
                sequence_order INTEGER NOT NULL,
                display_type TEXT,
                display_content TEXT,
                tts_message TEXT,
                dwell_time INTEGER DEFAULT 5,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
            )
        ''')

        # Waypoint summaries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waypoint_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                robot_id INTEGER,
                route_id INTEGER,
                waypoint_name TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_people INTEGER DEFAULT 0,
                total_violations INTEGER DEFAULT 0,
                total_compliant INTEGER DEFAULT 0,
                viewports_json TEXT,
                yolo_payload_json TEXT,
                action_taken TEXT,
                notes TEXT,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE SET NULL,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE SET NULL
            )
        ''')
        
        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Robot settings table (per-robot key/value)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS robot_settings (
                robot_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (robot_id, key),
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE
            )
        ''')
        
        # Activity logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                robot_id INTEGER,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE SET NULL
            )
        ''')

        # Violations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                robot_id INTEGER NOT NULL,
                location TEXT NOT NULL,
                violation_type TEXT NOT NULL,
                image_path TEXT,
                severity TEXT DEFAULT 'medium',
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged INTEGER DEFAULT 0,
                acknowledged_by TEXT,
                acknowledged_at TIMESTAMP,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE
            )
        ''')

        # Schedules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_config TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
            )
        ''')

        # Schedule runs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                route_id INTEGER NOT NULL,
                robot_id INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'running',
                message TEXT,
                FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE
            )
        ''')

        # Detection sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detection_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                robot_id INTEGER NOT NULL,
                route_id INTEGER,
                status TEXT DEFAULT 'active',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                violations_count INTEGER DEFAULT 0,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE SET NULL
            )
        ''')

        # Patrol history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patrol_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                robot_id INTEGER NOT NULL,
                route_id INTEGER NOT NULL,
                status TEXT DEFAULT 'running',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                details TEXT,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
            )
        ''')

        # YOLO Inspection Routes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS yolo_inspection_routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                robot_id INTEGER NOT NULL,
                loop_count INTEGER DEFAULT 1,
                return_location TEXT,
                pipeline_start_timeout INTEGER DEFAULT 30,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE
            )
        ''')

        # YOLO Inspection Waypoints table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS yolo_inspection_waypoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_route_id INTEGER NOT NULL,
                waypoint_name TEXT NOT NULL,
                sequence_order INTEGER NOT NULL,
                checking_duration INTEGER DEFAULT 30,
                violation_threshold INTEGER DEFAULT 0,
                tts_start TEXT DEFAULT 'Starting inspection at {waypoint}',
                tts_no_violation TEXT DEFAULT 'No violations detected at {waypoint}',
                tts_violation TEXT DEFAULT 'Safety violations detected: {count}',
                FOREIGN KEY (inspection_route_id) REFERENCES yolo_inspection_routes(id) ON DELETE CASCADE
            )
        ''')

        # YOLO Inspection Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS yolo_inspection_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                robot_id INTEGER NOT NULL,
                inspection_route_id INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                status TEXT DEFAULT 'running',
                pipeline_start_status TEXT,
                total_waypoints_inspected INTEGER DEFAULT 0,
                total_violations_found INTEGER DEFAULT 0,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE,
                FOREIGN KEY (inspection_route_id) REFERENCES yolo_inspection_routes(id) ON DELETE CASCADE
            )
        ''')

        # YOLO Waypoint Inspections table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS yolo_waypoint_inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_session_id INTEGER NOT NULL,
                waypoint_name TEXT NOT NULL,
                timestamp_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                timestamp_end TIMESTAMP,
                duration_seconds INTEGER,
                violations_detected INTEGER DEFAULT 0,
                people_detected INTEGER DEFAULT 0,
                compliant_detected INTEGER DEFAULT 0,
                viewports_json TEXT,
                result TEXT,
                FOREIGN KEY (inspection_session_id) REFERENCES yolo_inspection_sessions(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        
        # Create default admin user if not exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ('admin',))
        if cursor.fetchone()[0] == 0:
            password_hash = hash_password('admin123')
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                         ('admin', password_hash))
            conn.commit()
        
        # Create default settings if not exist
        # Note: MQTT broker credentials should be set via .env file or Settings page
        import os
        default_mqtt_broker = os.getenv('CLOUD_MQTT_HOST', '')
        default_mqtt_port = os.getenv('CLOUD_MQTT_PORT', '8883')
        default_mqtt_username = os.getenv('CLOUD_MQTT_USERNAME', '')
        default_mqtt_password = os.getenv('CLOUD_MQTT_PASSWORD', '')

        default_settings = {
            'default_mqtt_broker': default_mqtt_broker,
            'default_mqtt_port': default_mqtt_port,
            'default_mqtt_use_tls': 'true',
            'default_mqtt_username': default_mqtt_username,
            'default_mqtt_password': default_mqtt_password,
            'low_battery_threshold': '10',
            'low_battery_action': 'complete_current',  # or 'stop_immediately'
            'low_battery_webview_url': 'file:///storage/emulated/0/temiscreens/LowBattery.htm',
            'low_battery_return_webview_url': 'file:///storage/emulated/0/temiscreens/LowBatteryReturn.htm',
            'default_movement_speed': '0.5',
            'home_base_location': 'home base',
            'waypoint_timeout': '60',
            'waypoint_max_retries': '2',
            'detection_timeout_seconds': '30',
            'no_violation_seconds': '5',
            'violation_action_default': 'tts',
            'violation_tts_default': 'Please follow safety protocols and wear proper PPE.',
            'violation_display_type_default': 'webview',
            'violation_display_content_default': '',
            'yolo_stream_url': 'http://192.168.18.135:8080',
            'yolo_script_path': '',
            'patrolling_webview_url': 'file:///storage/emulated/0/temiscreens/Patrolling.htm',
            'going_to_waypoint_webview_url': 'file:///storage/emulated/0/temiscreens/GoingToWaypoint.htm',
            'arrived_waypoint_webview_url': 'file:///storage/emulated/0/temiscreens/ArrivedWaypoint.htm',
            'inspection_start_webview_url': 'file:///storage/emulated/0/temiscreens/InspectionStart.htm',
            'no_violation_webview_url': 'file:///storage/emulated/0/temiscreens/NoViolation.htm',
            'violation_webview_url': 'file:///storage/emulated/0/temiscreens/Violation.htm',
            'violation_timeout_webview_url': 'file:///storage/emulated/0/temiscreens/ViolationTimeout.htm',
            'going_home_webview_url': 'file:///storage/emulated/0/temiscreens/GoingHome.htm',
            'arrived_home_webview_url': 'file:///storage/emulated/0/temiscreens/ArrivedHome.htm',
            'no_violation_tts': 'No violation detected. Moving to next waypoint.',
            'yolo_shutdown_timeout': '30',
            'high_violation_threshold': '5',
            'violation_debounce_window': '10',
            'violation_smoothing_factor': '0.3',
            'outlier_threshold': '3.0',
            'map_scale_pixels_per_meter': '50',
            'map_origin_x': '0',
            'map_origin_y': '0',
            'tts_wait_seconds': '3',
            'display_wait_seconds': '2',
            'webview_close_delay_seconds': '5',
            'arrival_action_delay_seconds': '2',
            'patrol_stop_home_timeout_seconds': '15',
            'patrol_stop_always_send_home': 'false',
            'notifications_enabled': 'false',
            'notify_in_app': 'true',
            'notify_email': 'false',
            'notify_sms': 'false',
            'notify_webpush': 'false',
            'notify_telegram': 'false',
            'notify_whatsapp': 'false',
            'notify_only_high': 'true',
            'notify_digest_frequency': 'daily',
            'smtp_host': '',
            'smtp_port': '587',
            'smtp_user': '',
            'smtp_password': '',
            'smtp_from': '',
            'smtp_to': '',
            'smtp_use_tls': 'true',
            'twilio_account_sid': '',
            'twilio_auth_token': '',
            'twilio_from': '',
            'twilio_to': '',
            'telegram_bot_token': '',
            'telegram_chat_id': '',
            'twilio_whatsapp_from': '',
            'twilio_whatsapp_to': '',
            # YOLO Inspection Patrol settings
            'inspection_patrol_pipeline_timeout': '30',
            'inspection_checking_duration_default': '30',
            'inspection_webview_url': 'file:///storage/emulated/0/temiscreens/InspectionStatus.htm',
            'inspection_tts_start_default': 'Starting inspection at {waypoint}',
            'inspection_tts_no_violation_default': 'No violations detected at {waypoint}',
            'inspection_tts_violation_default': 'Safety violations detected: {count}'
        }

        for key, value in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                         (key, value))
        conn.commit()

        # Ensure new waypoint columns exist
        _ensure_columns(conn, 'route_waypoints', [
            {'name': 'detection_enabled', 'type': 'INTEGER', 'default': '0'},
            {'name': 'detection_timeout', 'type': 'INTEGER', 'default': '30'},
            {'name': 'no_violation_seconds', 'type': 'INTEGER', 'default': '5'},
            {'name': 'violation_action', 'type': 'TEXT', 'default': "'tts'"},
            {'name': 'violation_tts_message', 'type': 'TEXT'},
            {'name': 'violation_display_type', 'type': 'TEXT'},
            {'name': 'violation_display_content', 'type': 'TEXT'},
            {'name': 'webview_close_delay', 'type': 'INTEGER', 'default': '0'},
        ])

        _ensure_columns(conn, 'violations', [
            {'name': 'timestamp', 'type': 'TIMESTAMP', 'default': 'CURRENT_TIMESTAMP'},
            {'name': 'acknowledged', 'type': 'INTEGER', 'default': '0'},
            {'name': 'acknowledged_by', 'type': 'TEXT'},
            {'name': 'acknowledged_at', 'type': 'TIMESTAMP'},
            {'name': 'severity', 'type': 'TEXT', 'default': "'medium'"},
            {'name': 'details', 'type': 'TEXT'}
        ])

        _ensure_columns(conn, 'routes', [
            {'name': 'loop_count', 'type': 'INTEGER', 'default': '1'},
            {'name': 'return_location', 'type': 'TEXT'}
        ])

        _ensure_columns(conn, 'robots', [
            {'name': 'map_image_url', 'type': 'TEXT'},
            {'name': 'waypoints_positions_json', 'type': 'TEXT', 'default': "'[]'"}
        ])

        _ensure_columns(conn, 'activity_logs', [
            {'name': 'category', 'type': 'TEXT'}
        ])

        _ensure_columns(conn, 'schedules', [
            {'name': 'enabled', 'type': 'INTEGER', 'default': '1'},
            {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'CURRENT_TIMESTAMP'},
            {'name': 'updated_at', 'type': 'TIMESTAMP'},
            {'name': 'last_run_at', 'type': 'TIMESTAMP'}
        ])


def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == password_hash


# User operations
def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate user and return user data"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if user and verify_password(password, user['password_hash']):
            return dict(user)
        return None


def create_user(username: str, password: str) -> bool:
    """Create a new user"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            password_hash = hash_password(password)
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                         (username, password_hash))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


# Robot operations
def get_all_robots() -> List[Dict]:
    """Get all robots"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM robots ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]


def get_robot_by_id(robot_id: int) -> Optional[Dict]:
    """Get robot by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM robots WHERE id = ?", (robot_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_robot_by_serial(serial_number: str) -> Optional[Dict]:
    """Get robot by serial number"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM robots WHERE serial_number = ?", (serial_number,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_robot(name: str, serial_number: str, mqtt_config: Optional[Dict] = None) -> int:
    """Create a new robot"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if mqtt_config:
            cursor.execute('''
                INSERT INTO robots (name, serial_number, mqtt_broker_url, mqtt_port, 
                                  mqtt_username, mqtt_password, use_tls)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, serial_number, mqtt_config.get('broker_url'),
                  mqtt_config.get('port'), mqtt_config.get('username'),
                  mqtt_config.get('password'), mqtt_config.get('use_tls', True)))
        else:
            cursor.execute('''
                INSERT INTO robots (name, serial_number)
                VALUES (?, ?)
            ''', (name, serial_number))
        
        conn.commit()
        return cursor.lastrowid


def update_robot(robot_id: int, **kwargs) -> bool:
    """Update robot fields"""
    if not kwargs:
        return False
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Build SET clause dynamically
        set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [robot_id]
        
        cursor.execute(f"UPDATE robots SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cursor.rowcount > 0


def delete_robot(robot_id: int) -> bool:
    """Delete robot"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM robots WHERE id = ?", (robot_id,))
        conn.commit()
        return cursor.rowcount > 0


def update_robot_status(robot_id: int, status: str, battery_level: Optional[int] = None,
                       is_charging: Optional[bool] = None, current_location: Optional[str] = None) -> bool:
    """Update robot status"""
    updates = {'connection_status': status, 'last_seen': datetime.now()}
    
    if battery_level is not None:
        updates['battery_level'] = battery_level
    if is_charging is not None:
        updates['is_charging'] = is_charging
    if current_location is not None:
        updates['current_location'] = current_location
    
    return update_robot(robot_id, **updates)


def update_robot_waypoints(robot_id: int, waypoints: List[str]) -> bool:
    """Update robot's waypoint list"""
    return update_robot(robot_id, waypoints_json=json.dumps(waypoints))


# Route operations
def get_all_routes(robot_id: Optional[int] = None) -> List[Dict]:
    """Get all routes, optionally filtered by robot"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if robot_id:
            cursor.execute("""
                SELECT r.*, rb.name as robot_name 
                FROM routes r
                JOIN robots rb ON r.robot_id = rb.id
                WHERE r.robot_id = ?
                ORDER BY r.created_at DESC
            """, (robot_id,))
        else:
            cursor.execute("""
                SELECT r.*, rb.name as robot_name 
                FROM routes r
                JOIN robots rb ON r.robot_id = rb.id
                ORDER BY r.created_at DESC
            """)
        
        routes = [dict(row) for row in cursor.fetchall()]
        
        # Get waypoints for each route
        for route in routes:
            cursor.execute("""
                SELECT * FROM route_waypoints 
                WHERE route_id = ? 
                ORDER BY sequence_order
            """, (route['id'],))
            route['waypoints'] = [dict(row) for row in cursor.fetchall()]
        
        return routes


def get_route_by_id(route_id: int) -> Optional[Dict]:
    """Get route by ID with waypoints"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT r.*, rb.name as robot_name 
            FROM routes r
            JOIN robots rb ON r.robot_id = rb.id
            WHERE r.id = ?
        """, (route_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        route = dict(row)
        
        # Get waypoints
        cursor.execute("""
            SELECT * FROM route_waypoints 
            WHERE route_id = ? 
            ORDER BY sequence_order
        """, (route_id,))
        route['waypoints'] = [dict(row) for row in cursor.fetchall()]
        
        return route


def create_route(name: str, robot_id: int, waypoints: List[Dict], loop_count: int = 1,
                 return_location: Optional[str] = None) -> int:
    """Create a new route with waypoints"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create route
        cursor.execute("INSERT INTO routes (name, robot_id, loop_count, return_location) VALUES (?, ?, ?, ?)",
                     (name, robot_id, loop_count, return_location))
        route_id = cursor.lastrowid
        
        # Add waypoints
        for i, waypoint in enumerate(waypoints):
            cursor.execute('''
                INSERT INTO route_waypoints 
                (route_id, waypoint_name, sequence_order, display_type, 
                 display_content, tts_message, dwell_time, detection_enabled,
                 detection_timeout, no_violation_seconds, violation_action,
                 violation_tts_message, violation_display_type, violation_display_content,
                 webview_close_delay)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (route_id, waypoint['waypoint_name'], i,
                  waypoint.get('display_type'), waypoint.get('display_content'),
                  waypoint.get('tts_message'), waypoint.get('dwell_time', 5),
                  waypoint.get('detection_enabled', 0),
                  waypoint.get('detection_timeout'),
                  waypoint.get('no_violation_seconds'),
                  waypoint.get('violation_action'),
                  waypoint.get('violation_tts_message'),
                  waypoint.get('violation_display_type'),
                  waypoint.get('violation_display_content'),
                  waypoint.get('webview_close_delay')))
        
        conn.commit()
        return route_id


def update_route(route_id: int, name: Optional[str] = None,
                waypoints: Optional[List[Dict]] = None, loop_count: Optional[int] = None,
                return_location: Optional[str] = None) -> bool:
    """Update route and/or waypoints"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if name:
            cursor.execute("UPDATE routes SET name = ? WHERE id = ?", (name, route_id))
        
        if loop_count is not None:
            cursor.execute("UPDATE routes SET loop_count = ? WHERE id = ?", (loop_count, route_id))

        if return_location is not None:
            cursor.execute("UPDATE routes SET return_location = ? WHERE id = ?", (return_location, route_id))
        
        if waypoints is not None:
            # Delete existing waypoints
            cursor.execute("DELETE FROM route_waypoints WHERE route_id = ?", (route_id,))
            
            # Add new waypoints
            for i, waypoint in enumerate(waypoints):
                cursor.execute('''
                    INSERT INTO route_waypoints 
                    (route_id, waypoint_name, sequence_order, display_type, 
                     display_content, tts_message, dwell_time, detection_enabled,
                     detection_timeout, no_violation_seconds, violation_action,
                     violation_tts_message, violation_display_type, violation_display_content,
                     webview_close_delay)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (route_id, waypoint['waypoint_name'], i,
                      waypoint.get('display_type'), waypoint.get('display_content'),
                      waypoint.get('tts_message'), waypoint.get('dwell_time', 5),
                      waypoint.get('detection_enabled', 0),
                      waypoint.get('detection_timeout'),
                      waypoint.get('no_violation_seconds'),
                      waypoint.get('violation_action'),
                      waypoint.get('violation_tts_message'),
                      waypoint.get('violation_display_type'),
                      waypoint.get('violation_display_content'),
                      waypoint.get('webview_close_delay')))
        
        conn.commit()
        return True


def delete_route(route_id: int) -> bool:
    """Delete route"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM routes WHERE id = ?", (route_id,))
        conn.commit()
        return cursor.rowcount > 0


# Settings operations
def get_setting(key: str, default: Any = None) -> Any:
    """Get setting value"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default


def get_all_settings() -> Dict[str, str]:
    """Get all settings"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row['key']: row['value'] for row in cursor.fetchall()}


def update_setting(key: str, value: str) -> bool:
    """Update or create setting"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at) 
            VALUES (?, ?, ?)
        ''', (key, value, datetime.now()))
        conn.commit()
        return True


def get_robot_setting(robot_id: int, key: str, default: Any = None) -> Any:
    """Get per-robot setting value"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM robot_settings WHERE robot_id = ? AND key = ?", (robot_id, key))
        row = cursor.fetchone()
        return row['value'] if row else default


def set_robot_setting(robot_id: int, key: str, value: str) -> bool:
    """Set per-robot setting value"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO robot_settings (robot_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (robot_id, key, value, datetime.now()))
        conn.commit()
        return True


# Activity log operations
def add_activity_log(robot_id: Optional[int], level: str, message: str,
                    details: Optional[str] = None, category: Optional[str] = None) -> int:
    """Add activity log entry"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activity_logs (robot_id, level, message, details, category)
            VALUES (?, ?, ?, ?, ?)
        ''', (robot_id, level, message, details, category))
        conn.commit()
        return cursor.lastrowid


def get_activity_logs(robot_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
    """Get activity logs, optionally filtered by robot"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if robot_id:
            cursor.execute("""
                SELECT al.*, r.name as robot_name
                FROM activity_logs al
                LEFT JOIN robots r ON al.robot_id = r.id
                WHERE al.robot_id = ?
                ORDER BY al.created_at DESC
                LIMIT ?
            """, (robot_id, limit))
        else:
            cursor.execute("""
                SELECT al.*, r.name as robot_name
                FROM activity_logs al
                LEFT JOIN robots r ON al.robot_id = r.id
                ORDER BY al.created_at DESC
                LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]


def clear_activity_logs(robot_id: Optional[int] = None) -> bool:
    """Clear activity logs"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if robot_id:
            cursor.execute("DELETE FROM activity_logs WHERE robot_id = ?", (robot_id,))
        else:
            cursor.execute("DELETE FROM activity_logs")
        
        conn.commit()
        return True


# Violation operations
def add_violation(robot_id: int, location: str, violation_type: str, 
                  image_path: Optional[str] = None, severity: str = 'medium',
                  details: Optional[str] = None) -> int:
    """Add violation record"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO violations 
            (robot_id, location, violation_type, image_path, severity, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (robot_id, location, violation_type, image_path, severity, details))
        conn.commit()
        return cursor.lastrowid


def get_violations(robot_id: Optional[int] = None, violation_type: Optional[str] = None,
                   severity: Optional[str] = None, acknowledged: Optional[bool] = None,
                   start_date: Optional[str] = None, end_date: Optional[str] = None,
                   limit: int = 100) -> List[Dict]:
    """Get violations with filters"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT v.*, r.name as robot_name
            FROM violations v
            LEFT JOIN robots r ON v.robot_id = r.id
            WHERE 1=1
        """
        params = []
        
        if robot_id:
            query += " AND v.robot_id = ?"
            params.append(robot_id)
        
        if violation_type:
            query += " AND v.violation_type = ?"
            params.append(violation_type)

        if severity:
            query += " AND v.severity = ?"
            params.append(severity)
        
        if acknowledged is not None:
            query += " AND v.acknowledged = ?"
            params.append(1 if acknowledged else 0)

        if start_date:
            query += " AND v.timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND v.timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY v.timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_violation_summary(group_by: str = 'day', robot_id: Optional[int] = None,
                          violation_type: Optional[str] = None, severity: Optional[str] = None,
                          acknowledged: Optional[bool] = None,
                          start_date: Optional[str] = None, end_date: Optional[str] = None,
                          limit: int = 365) -> List[Dict]:
    """Get violation summary grouped by day/week/month/year"""
    group_format = {
        'day': "%Y-%m-%d",
        'week': "%Y-%W",
        'month': "%Y-%m",
        'year': "%Y"
    }.get(group_by, "%Y-%m-%d")

    with get_db() as conn:
        cursor = conn.cursor()
        query = f"""
            SELECT strftime('{group_format}', timestamp, 'localtime') as period,
                   COUNT(*) as total,
                   SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high_count,
                   SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END) as medium_count,
                   SUM(CASE WHEN severity = 'low' THEN 1 ELSE 0 END) as low_count,
                   SUM(CASE WHEN acknowledged = 1 THEN 1 ELSE 0 END) as acknowledged_count
            FROM violations
            WHERE 1=1
        """
        params = []

        if robot_id:
            query += " AND robot_id = ?"
            params.append(robot_id)
        if violation_type:
            query += " AND violation_type = ?"
            params.append(violation_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if acknowledged is not None:
            query += " AND acknowledged = ?"
            params.append(1 if acknowledged else 0)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " GROUP BY period ORDER BY period DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_violation_stats(robot_id: Optional[int] = None) -> Dict:
    """Get violation statistics"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Total violations
        if robot_id:
            cursor.execute("SELECT COUNT(*) as total FROM violations WHERE robot_id = ?", (robot_id,))
        else:
            cursor.execute("SELECT COUNT(*) as total FROM violations")
        total = cursor.fetchone()['total']
        
        # By type
        if robot_id:
            cursor.execute("""
                SELECT violation_type, COUNT(*) as count 
                FROM violations WHERE robot_id = ?
                GROUP BY violation_type
            """, (robot_id,))
        else:
            cursor.execute("""
                SELECT violation_type, COUNT(*) as count 
                FROM violations
                GROUP BY violation_type
            """)
        by_type = {row['violation_type']: row['count'] for row in cursor.fetchall()}
        
        # By severity
        if robot_id:
            cursor.execute("""
                SELECT severity, COUNT(*) as count 
                FROM violations WHERE robot_id = ?
                GROUP BY severity
            """, (robot_id,))
        else:
            cursor.execute("""
                SELECT severity, COUNT(*) as count 
                FROM violations
                GROUP BY severity
            """)
        by_severity = {row['severity']: row['count'] for row in cursor.fetchall()}

        # Today's violations
        if robot_id:
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM violations
                WHERE robot_id = ? AND date(timestamp, 'localtime') = date('now', 'localtime')
            """, (robot_id,))
        else:
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM violations
                WHERE date(timestamp, 'localtime') = date('now', 'localtime')
            """)
        today_total = cursor.fetchone()['total']

        # Pending violations (not acknowledged)
        if robot_id:
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM violations
                WHERE robot_id = ? AND (acknowledged = 0 OR acknowledged IS NULL)
            """, (robot_id,))
        else:
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM violations
                WHERE (acknowledged = 0 OR acknowledged IS NULL)
            """)
        pending_total = cursor.fetchone()['total']

        # Pending high severity
        if robot_id:
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM violations
                WHERE robot_id = ? AND (acknowledged = 0 OR acknowledged IS NULL) AND severity = 'high'
            """, (robot_id,))
        else:
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM violations
                WHERE (acknowledged = 0 OR acknowledged IS NULL) AND severity = 'high'
            """)
        pending_high = cursor.fetchone()['total']
        
        return {
            'total': total,
            'by_type': by_type,
            'by_severity': by_severity,
            'today_total': today_total,
            'pending_total': pending_total,
            'pending_high': pending_high
        }


def acknowledge_violation(violation_id: int, acknowledged_by: str) -> bool:
    """Acknowledge a violation"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE violations 
            SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = ?
            WHERE id = ?
        """, (acknowledged_by, datetime.now(), violation_id))
        conn.commit()
        return cursor.rowcount > 0


# Waypoint summary operations
def add_waypoint_summary(robot_id: Optional[int], route_id: Optional[int], waypoint_name: str,
                         summary: Dict, action_taken: Optional[str] = None,
                         notes: Optional[str] = None) -> int:
    """Add waypoint summary record"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO waypoint_summaries
            (robot_id, route_id, waypoint_name, timestamp,
             total_people, total_violations, total_compliant,
             viewports_json, yolo_payload_json, action_taken, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            robot_id,
            route_id,
            waypoint_name,
            summary.get('timestamp'),
            summary.get('total_people', 0),
            summary.get('total_violations', 0),
            summary.get('total_compliant', 0),
            json.dumps(summary.get('viewports', {})),
            json.dumps(summary.get('yolo_payload', {})),
            action_taken,
            notes
        ))
        conn.commit()
        return cursor.lastrowid


def get_waypoint_summaries(robot_id: Optional[int] = None, route_id: Optional[int] = None,
                           start_date: Optional[str] = None, end_date: Optional[str] = None,
                           limit: int = 100) -> List[Dict]:
    """Get waypoint summaries"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT ws.*
            FROM waypoint_summaries ws
            WHERE 1=1
        """
        params = []
        if robot_id:
            query += " AND ws.robot_id = ?"
            params.append(robot_id)
        if route_id:
            query += " AND ws.route_id = ?"
            params.append(route_id)
        if start_date:
            query += " AND ws.timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND ws.timestamp <= ?"
            params.append(end_date)
        query += " ORDER BY ws.timestamp DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# Schedule operations
def create_schedule(route_id: int, name: str, schedule_type: str, 
                   schedule_config: Dict, enabled: int = 1) -> int:
    """Create a new schedule"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO schedules (route_id, name, schedule_type, schedule_config, enabled)
            VALUES (?, ?, ?, ?, ?)
        ''', (route_id, name, schedule_type, json.dumps(schedule_config), enabled))
        conn.commit()
        return cursor.lastrowid


def get_all_schedules(enabled_only: bool = False) -> List[Dict]:
    """Get all schedules"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT s.*, r.name as route_name, rb.name as robot_name
            FROM schedules s
            JOIN routes r ON s.route_id = r.id
            JOIN robots rb ON r.robot_id = rb.id
        """
        
        if enabled_only:
            query += " WHERE s.enabled = 1"
        
        query += " ORDER BY s.created_at DESC"
        
        cursor.execute(query)
        schedules = [dict(row) for row in cursor.fetchall()]
        
        # Parse schedule_config JSON
        for schedule in schedules:
            schedule['schedule_config'] = json.loads(schedule['schedule_config'])
        
        return schedules


def get_schedule_by_id(schedule_id: int) -> Optional[Dict]:
    """Get schedule by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.*, r.name as route_name, rb.name as robot_name
            FROM schedules s
            JOIN routes r ON s.route_id = r.id
            JOIN robots rb ON r.robot_id = rb.id
            WHERE s.id = ?
        ''', (schedule_id,))
        row = cursor.fetchone()
        if not row:
            return None
        schedule = dict(row)
        try:
            schedule['schedule_config'] = json.loads(schedule['schedule_config'])
        except Exception:
            schedule['schedule_config'] = {}
        return schedule


def update_schedule(schedule_id: int, **kwargs) -> bool:
    """Update schedule"""
    if not kwargs:
        return False
    
    # Convert schedule_config dict to JSON if present
    if 'schedule_config' in kwargs and isinstance(kwargs['schedule_config'], dict):
        kwargs['schedule_config'] = json.dumps(kwargs['schedule_config'])
    
    kwargs['updated_at'] = datetime.now()

    with get_db() as conn:
        cursor = conn.cursor()
        set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [schedule_id]
        cursor.execute(f"UPDATE schedules SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cursor.rowcount > 0


def update_schedule_last_run(schedule_id: int, run_time: Optional[datetime] = None) -> bool:
    """Update schedule last run time"""
    if run_time is None:
        run_time = datetime.now()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE schedules SET last_run_at = ?, updated_at = ? WHERE id = ?",
                       (run_time, datetime.now(), schedule_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_schedule(schedule_id: int) -> bool:
    """Delete schedule"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        conn.commit()
        return cursor.rowcount > 0


def create_schedule_run(schedule_id: int, route_id: int, robot_id: int,
                       status: str = 'running', message: Optional[str] = None) -> int:
    """Create a schedule run record"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO schedule_runs (schedule_id, route_id, robot_id, status, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (schedule_id, route_id, robot_id, status, message))
        conn.commit()
        return cursor.lastrowid


def update_schedule_run(run_id: int, status: str, message: Optional[str] = None) -> bool:
    """Update schedule run status"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE schedule_runs SET status = ?, message = ?
            WHERE id = ?
        ''', (status, message, run_id))
        conn.commit()
        return cursor.rowcount > 0


def get_schedule_runs(limit: int = 50) -> List[Dict]:
    """Get recent schedule runs"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sr.*, s.name as schedule_name, r.name as route_name, rb.name as robot_name
            FROM schedule_runs sr
            JOIN schedules s ON sr.schedule_id = s.id
            JOIN routes r ON sr.route_id = r.id
            JOIN robots rb ON sr.robot_id = rb.id
            ORDER BY sr.started_at DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]


# Detection session operations
def start_detection_session(robot_id: int, route_id: Optional[int] = None) -> int:
    """Start a detection session"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO detection_sessions (robot_id, route_id, status)
            VALUES (?, ?, 'active')
        ''', (robot_id, route_id))
        conn.commit()
        return cursor.lastrowid


def end_detection_session(session_id: int, violations_count: int) -> bool:
    """End a detection session"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE detection_sessions 
            SET ended_at = ?, status = 'completed', violations_count = ?
            WHERE id = ?
        """, (datetime.now(), violations_count, session_id))
        conn.commit()
        return cursor.rowcount > 0


def get_active_detection_session(robot_id: int) -> Optional[Dict]:
    """Get active detection session for robot"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM detection_sessions 
            WHERE robot_id = ? AND status = 'active'
            ORDER BY started_at DESC LIMIT 1
        """, (robot_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_detection_sessions(robot_id: Optional[int] = None, status: Optional[str] = None,
                          start_date: Optional[str] = None, end_date: Optional[str] = None,
                          limit: int = 100) -> List[Dict]:
    """Get detection sessions with filters"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT ds.*, r.name as robot_name, rt.name as route_name
            FROM detection_sessions ds
            LEFT JOIN robots r ON ds.robot_id = r.id
            LEFT JOIN routes rt ON ds.route_id = rt.id
            WHERE 1=1
        """
        params = []

        if robot_id:
            query += " AND ds.robot_id = ?"
            params.append(robot_id)
        if status:
            query += " AND ds.status = ?"
            params.append(status)
        if start_date:
            query += " AND ds.started_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND ds.started_at <= ?"
            params.append(end_date)

        query += " ORDER BY ds.started_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# Patrol history operations
def start_patrol_history(robot_id: int, route_id: int) -> int:
    """Start patrol history record"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO patrol_history (robot_id, route_id, status)
            VALUES (?, ?, 'running')
        ''', (robot_id, route_id))
        conn.commit()
        return cursor.lastrowid


def update_patrol_history(history_id: int, **kwargs) -> bool:
    """Update patrol history"""
    if not kwargs:
        return False
    
    with get_db() as conn:
        cursor = conn.cursor()
        set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [history_id]
        cursor.execute(f"UPDATE patrol_history SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cursor.rowcount > 0


def get_patrol_history(robot_id: Optional[int] = None, limit: int = 50) -> List[Dict]:
    """Get patrol history"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if robot_id:
            cursor.execute("""
                SELECT ph.*, r.name as robot_name, rt.name as route_name
                FROM patrol_history ph
                JOIN robots r ON ph.robot_id = r.id
                JOIN routes rt ON ph.route_id = rt.id
                WHERE ph.robot_id = ?
                ORDER BY ph.started_at DESC LIMIT ?
            """, (robot_id, limit))
        else:
            cursor.execute("""
                SELECT ph.*, r.name as robot_name, rt.name as route_name
                FROM patrol_history ph
                JOIN robots r ON ph.robot_id = r.id
                JOIN routes rt ON ph.route_id = rt.id
                ORDER BY ph.started_at DESC LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]


def get_active_patrol_history(robot_id: int) -> Optional[Dict]:
    """Get the most recent running patrol history entry for a robot"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM patrol_history
            WHERE robot_id = ? AND status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """, (robot_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ============================================================================
# YOLO Inspection Patrol Operations
# ============================================================================

def create_inspection_route(name: str, robot_id: int, waypoints: List[Dict],
                            loop_count: int = 1, return_location: Optional[str] = None,
                            pipeline_timeout: int = 30) -> int:
    """Create a new YOLO inspection route with waypoints"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Insert route
        cursor.execute("""
            INSERT INTO yolo_inspection_routes
            (name, robot_id, loop_count, return_location, pipeline_start_timeout)
            VALUES (?, ?, ?, ?, ?)
        """, (name, robot_id, loop_count, return_location, pipeline_timeout))

        route_id = cursor.lastrowid

        # Insert waypoints
        for waypoint in waypoints:
            cursor.execute("""
                INSERT INTO yolo_inspection_waypoints
                (inspection_route_id, waypoint_name, sequence_order, checking_duration,
                 violation_threshold, tts_start, tts_no_violation, tts_violation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                route_id,
                waypoint.get('waypoint_name'),
                waypoint.get('sequence_order', 0),
                waypoint.get('checking_duration', 30),
                waypoint.get('violation_threshold', 0),
                waypoint.get('tts_start', 'Starting inspection at {waypoint}'),
                waypoint.get('tts_no_violation', 'No violations detected at {waypoint}'),
                waypoint.get('tts_violation', 'Safety violations detected: {count}')
            ))

        conn.commit()
        return route_id


def get_inspection_routes(robot_id: Optional[int] = None) -> List[Dict]:
    """Get all YOLO inspection routes"""
    with get_db() as conn:
        cursor = conn.cursor()

        if robot_id:
            cursor.execute("""
                SELECT ir.*, r.name as robot_name
                FROM yolo_inspection_routes ir
                JOIN robots r ON ir.robot_id = r.id
                WHERE ir.robot_id = ?
                ORDER BY ir.created_at DESC
            """, (robot_id,))
        else:
            cursor.execute("""
                SELECT ir.*, r.name as robot_name
                FROM yolo_inspection_routes ir
                JOIN robots r ON ir.robot_id = r.id
                ORDER BY ir.created_at DESC
            """)

        routes = [dict(row) for row in cursor.fetchall()]

        # Fetch waypoints for each route
        for route in routes:
            cursor.execute("""
                SELECT * FROM yolo_inspection_waypoints
                WHERE inspection_route_id = ?
                ORDER BY sequence_order
            """, (route['id'],))
            route['waypoints'] = [dict(row) for row in cursor.fetchall()]

        return routes


def get_inspection_route(route_id: int) -> Optional[Dict]:
    """Get a specific YOLO inspection route with waypoints"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ir.*, r.name as robot_name
            FROM yolo_inspection_routes ir
            JOIN robots r ON ir.robot_id = r.id
            WHERE ir.id = ?
        """, (route_id,))

        row = cursor.fetchone()
        if not row:
            return None

        route = dict(row)

        # Fetch waypoints
        cursor.execute("""
            SELECT * FROM yolo_inspection_waypoints
            WHERE inspection_route_id = ?
            ORDER BY sequence_order
        """, (route_id,))

        route['waypoints'] = [dict(row) for row in cursor.fetchall()]

        return route


def update_inspection_route(route_id: int, name: Optional[str] = None,
                            loop_count: Optional[int] = None,
                            waypoints: Optional[List[Dict]] = None) -> bool:
    """Update a YOLO inspection route"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            if name:
                cursor.execute("UPDATE yolo_inspection_routes SET name = ? WHERE id = ?",
                             (name, route_id))

            if loop_count is not None:
                cursor.execute("UPDATE yolo_inspection_routes SET loop_count = ? WHERE id = ?",
                             (loop_count, route_id))

            if waypoints is not None:
                # Delete existing waypoints
                cursor.execute("DELETE FROM yolo_inspection_waypoints WHERE inspection_route_id = ?",
                             (route_id,))

                # Insert new waypoints
                for waypoint in waypoints:
                    cursor.execute("""
                        INSERT INTO yolo_inspection_waypoints
                        (inspection_route_id, waypoint_name, sequence_order, checking_duration,
                         violation_threshold, tts_start, tts_no_violation, tts_violation)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        route_id,
                        waypoint.get('waypoint_name'),
                        waypoint.get('sequence_order', 0),
                        waypoint.get('checking_duration', 30),
                        waypoint.get('violation_threshold', 0),
                        waypoint.get('tts_start', 'Starting inspection at {waypoint}'),
                        waypoint.get('tts_no_violation', 'No violations detected at {waypoint}'),
                        waypoint.get('tts_violation', 'Safety violations detected: {count}')
                    ))

            conn.commit()
            return True
    except Exception:
        return False


def delete_inspection_route(route_id: int) -> bool:
    """Delete a YOLO inspection route (cascade deletes waypoints)"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM yolo_inspection_routes WHERE id = ?", (route_id,))
            conn.commit()
            return True
    except Exception:
        return False


def create_inspection_session(robot_id: int, route_id: int,
                              pipeline_status: str = 'unknown') -> int:
    """Create a new inspection session"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO yolo_inspection_sessions
            (robot_id, inspection_route_id, pipeline_start_status)
            VALUES (?, ?, ?)
        """, (robot_id, route_id, pipeline_status))
        conn.commit()
        return cursor.lastrowid


def update_inspection_session(session_id: int, status: Optional[str] = None,
                              waypoints_inspected: Optional[int] = None,
                              violations_found: Optional[int] = None) -> bool:
    """Update inspection session"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            updates = []
            params = []

            if status:
                updates.append("status = ?")
                params.append(status)
                if status in ('completed', 'stopped', 'error'):
                    updates.append("ended_at = CURRENT_TIMESTAMP")

            if waypoints_inspected is not None:
                updates.append("total_waypoints_inspected = ?")
                params.append(waypoints_inspected)

            if violations_found is not None:
                updates.append("total_violations_found = ?")
                params.append(violations_found)

            if updates:
                params.append(session_id)
                cursor.execute(f"""
                    UPDATE yolo_inspection_sessions
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
                conn.commit()

            return True
    except Exception:
        return False


def create_waypoint_inspection(session_id: int, waypoint_name: str,
                               violations: int = 0, people: int = 0,
                               compliant: int = 0, viewports: Optional[Dict] = None,
                               result: str = 'no_violation',
                               duration: Optional[int] = None) -> int:
    """Create a waypoint inspection record"""
    with get_db() as conn:
        cursor = conn.cursor()

        viewports_json = json.dumps(viewports) if viewports else None

        cursor.execute("""
            INSERT INTO yolo_waypoint_inspections
            (inspection_session_id, waypoint_name, violations_detected,
             people_detected, compliant_detected, viewports_json, result,
             timestamp_end, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (session_id, waypoint_name, violations, people, compliant,
              viewports_json, result, duration))

        conn.commit()
        return cursor.lastrowid


def get_inspection_sessions(robot_id: Optional[int] = None,
                            limit: int = 50) -> List[Dict]:
    """Get inspection sessions with route info"""
    with get_db() as conn:
        cursor = conn.cursor()

        if robot_id:
            cursor.execute("""
                SELECT
                    s.*,
                    r.name as route_name,
                    rob.name as robot_name
                FROM yolo_inspection_sessions s
                JOIN yolo_inspection_routes r ON s.inspection_route_id = r.id
                JOIN robots rob ON s.robot_id = rob.id
                WHERE s.robot_id = ?
                ORDER BY s.started_at DESC
                LIMIT ?
            """, (robot_id, limit))
        else:
            cursor.execute("""
                SELECT
                    s.*,
                    r.name as route_name,
                    rob.name as robot_name
                FROM yolo_inspection_sessions s
                JOIN yolo_inspection_routes r ON s.inspection_route_id = r.id
                JOIN robots rob ON s.robot_id = rob.id
                ORDER BY s.started_at DESC
                LIMIT ?
            """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


def get_waypoint_inspections(session_id: int) -> List[Dict]:
    """Get all waypoint inspections for a session"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM yolo_waypoint_inspections
            WHERE inspection_session_id = ?
            ORDER BY timestamp_start
        """, (session_id,))

        inspections = [dict(row) for row in cursor.fetchall()]

        # Parse viewports JSON
        for inspection in inspections:
            if inspection['viewports_json']:
                inspection['viewports'] = json.loads(inspection['viewports_json'])
            else:
                inspection['viewports'] = {}

        return inspections


if __name__ == '__main__':
    # Initialize database
    print("Initializing database...")
    init_database()
    print("Database initialized successfully!")
    print("Default admin credentials: username='admin', password='admin123'")
