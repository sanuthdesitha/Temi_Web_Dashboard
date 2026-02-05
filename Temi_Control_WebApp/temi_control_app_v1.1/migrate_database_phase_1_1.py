#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Database Migration Script - Phase 1.1
Adds webview_templates table and patrol_executions schema enhancements
Includes system templates for Nokia-branded webviews
"""

import sqlite3
import sys
import io
from datetime import datetime
from typing import List, Dict, Optional

# Fix Unicode output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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


def migrate_phase_1_1():
    """Execute Phase 1.1 migration: WebView templates and patrol execution enhancements"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Create webview_templates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webview_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                file_path TEXT NOT NULL,
                html_content TEXT,
                requires_customization BOOLEAN DEFAULT 0,
                system_template BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(name)
            )
        ''')
        conn.commit()
        print("[OK] Created webview_templates table")

        # Create patrol_executions table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patrol_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                robot_id INTEGER NOT NULL,
                route_id INTEGER NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'running',
                current_state TEXT DEFAULT 'initializing',
                current_waypoint_index INTEGER DEFAULT 0,
                total_waypoints INTEGER DEFAULT 0,
                violations_count INTEGER DEFAULT 0,
                duration_seconds INTEGER,
                completion_percentage REAL DEFAULT 0.0,
                error_message TEXT,
                is_paused BOOLEAN DEFAULT 0,
                pause_count INTEGER DEFAULT 0,
                resume_count INTEGER DEFAULT 0,
                return_location TEXT,
                low_battery_triggered BOOLEAN DEFAULT 0,
                distance_traveled REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        print("[OK] Created patrol_executions table")

        # Enhance patrol_executions with additional columns if needed
        patrol_execution_columns = [
            {'name': 'loop_count', 'type': 'INTEGER', 'default': '1'},
            {'name': 'current_loop', 'type': 'INTEGER', 'default': '1'},
            {'name': 'waypoint_attempts', 'type': 'TEXT'},  # JSON list of attempt counts
            {'name': 'violation_log', 'type': 'TEXT'},  # JSON array of violations
            {'name': 'state_transitions', 'type': 'TEXT'},  # JSON log of state changes
            {'name': 'notes', 'type': 'TEXT'},
            {'name': 'speed_override', 'type': 'REAL'},  # Override movement speed
            {'name': 'battery_at_end', 'type': 'INTEGER'},  # Battery level when patrol ended
        ]
        _ensure_columns(conn, 'patrol_executions', patrol_execution_columns)
        print("[OK] Enhanced patrol_executions table columns")

        # Enhance violations table with patrol reference
        violations_columns = [
            {'name': 'patrol_id', 'type': 'INTEGER'},
            {'name': 'waypoint_index', 'type': 'INTEGER'},
            {'name': 'confidence_score', 'type': 'REAL'},
            {'name': 'ppe_type', 'type': 'TEXT'},  # e.g., 'vest', 'helmet', 'both'
            {'name': 'auto_corrected', 'type': 'BOOLEAN', 'default': '0'},
        ]
        _ensure_columns(conn, 'violations', violations_columns)
        print("[OK] Enhanced violations table with patrol and detection details")

        # Create violation_debounce_state table for violation debouncing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS violation_debounce_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patrol_id INTEGER NOT NULL,
                waypoint_index INTEGER NOT NULL,
                violation_count INTEGER DEFAULT 0,
                violation_window_start TIMESTAMP,
                violation_window_end TIMESTAMP,
                debounce_triggered BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patrol_id) REFERENCES patrol_executions(id) ON DELETE CASCADE,
                UNIQUE(patrol_id, waypoint_index)
            )
        ''')
        conn.commit()
        print("[OK] Created violation_debounce_state table")

        # Insert system webview templates
        system_templates = [
            {
                'name': 'Patrolling',
                'category': 'Status',
                'description': 'Displayed while robot is actively patrolling',
                'file_path': 'file:///storage/emulated/0/webviews/Patrolling.htm',
            },
            {
                'name': 'Going To Waypoint',
                'category': 'Status',
                'description': 'Shown when robot is navigating to a waypoint',
                'file_path': 'file:///storage/emulated/0/webviews/GoingToWaypoint.htm',
            },
            {
                'name': 'Arrived At Waypoint',
                'category': 'Status',
                'description': 'Displayed when robot reaches a waypoint',
                'file_path': 'file:///storage/emulated/0/webviews/ArrivedWaypoint.htm',
            },
            {
                'name': 'Inspection Starting',
                'category': 'Status',
                'description': 'Shown when inspection/detection starts at a waypoint',
                'file_path': 'file:///storage/emulated/0/webviews/InspectionStart.htm',
            },
            {
                'name': 'No Violation Detected',
                'category': 'Detection',
                'description': 'Displayed when no safety violations detected',
                'file_path': 'file:///storage/emulated/0/webviews/NoViolation.htm',
            },
            {
                'name': 'Violation Detected',
                'category': 'Detection',
                'description': 'Shown when safety violation is detected',
                'file_path': 'file:///storage/emulated/0/webviews/Violation.htm',
            },
            {
                'name': 'Violation Timeout',
                'category': 'Detection',
                'description': 'Displayed when detection timeout reached',
                'file_path': 'file:///storage/emulated/0/webviews/ViolationTimeout.htm',
            },
            {
                'name': 'Going Home',
                'category': 'Return',
                'description': 'Shown when robot is returning to home base',
                'file_path': 'file:///storage/emulated/0/webviews/GoingHome.htm',
            },
            {
                'name': 'Arrived Home',
                'category': 'Return',
                'description': 'Displayed when robot arrives at home base',
                'file_path': 'file:///storage/emulated/0/webviews/ArrivedHome.htm',
            },
        ]

        for template in system_templates:
            cursor.execute('''
                INSERT OR IGNORE INTO webview_templates
                (name, category, description, file_path, system_template)
                VALUES (?, ?, ?, ?, 1)
            ''', (template['name'], template['category'],
                  template['description'], template['file_path']))

        conn.commit()
        print(f"[OK] Inserted {len(system_templates)} system webview templates")

        # Enhance routes table with webview configuration fields
        routes_columns = [
            {'name': 'arrival_webview_template_id', 'type': 'INTEGER'},
            {'name': 'inspection_webview_template_id', 'type': 'INTEGER'},
            {'name': 'violation_webview_template_id', 'type': 'INTEGER'},
            {'name': 'no_violation_webview_template_id', 'type': 'INTEGER'},
        ]
        _ensure_columns(conn, 'routes', routes_columns)
        print("[OK] Enhanced routes table with webview template references")

        # Enhance route_waypoints with webview configuration
        waypoint_columns = [
            {'name': 'webview_template_id', 'type': 'INTEGER'},
            {'name': 'custom_webview_url', 'type': 'TEXT'},
            {'name': 'violation_action_webview_template_id', 'type': 'INTEGER'},
            {'name': 'detection_enabled', 'type': 'BOOLEAN', 'default': '0'},
            {'name': 'detection_timeout_seconds', 'type': 'INTEGER', 'default': '30'},
            {'name': 'no_violation_window_seconds', 'type': 'INTEGER', 'default': '5'},
        ]
        _ensure_columns(conn, 'route_waypoints', waypoint_columns)
        print("[OK] Enhanced route_waypoints with webview and detection configuration")

        # Create webview_usage_stats table for analytics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webview_usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webview_template_id INTEGER NOT NULL,
                patrol_id INTEGER,
                display_count INTEGER DEFAULT 0,
                total_display_time_seconds REAL DEFAULT 0.0,
                first_used TIMESTAMP,
                last_used TIMESTAMP,
                FOREIGN KEY (webview_template_id) REFERENCES webview_templates(id) ON DELETE CASCADE,
                FOREIGN KEY (patrol_id) REFERENCES patrol_executions(id) ON DELETE SET NULL
            )
        ''')
        conn.commit()
        print("[OK] Created webview_usage_stats table for analytics")

        # Create patrol_state_history table for 9-state machine tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patrol_state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patrol_id INTEGER NOT NULL,
                previous_state TEXT,
                current_state TEXT NOT NULL,
                transition_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                context TEXT,
                FOREIGN KEY (patrol_id) REFERENCES patrol_executions(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        print("[OK] Created patrol_state_history table for state machine tracking")

        print("\n" + "="*60)
        print("Phase 1.1 Migration Complete!")
        print("="*60)
        print("\nCreated/Enhanced:")
        print("  • webview_templates table with 9 system templates")
        print("  • patrol_executions table with state machine fields")
        print("  • violation_debounce_state table")
        print("  • webview_usage_stats table")
        print("  • patrol_state_history table")
        print("  • Enhanced violations, routes, and route_waypoints tables")
        print("\nReady for Phase 1: Webview API Implementation")

        return True

    except Exception as e:
        print(f"\n[FAILED] Migration failed: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    success = migrate_phase_1_1()
    sys.exit(0 if success else 1)
