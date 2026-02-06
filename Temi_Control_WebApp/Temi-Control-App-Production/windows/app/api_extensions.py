"""
API Extensions for Temi Control Application
Additional API endpoints for violations, schedules, detection, etc.
"""

from flask import jsonify, request, session
import database as db
import logging
from datetime import datetime
import os
import csv
import io

logger = logging.getLogger(__name__)


def _parse_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _normalize_date(value: str, end_of_day: bool = False) -> str:
    if not value:
        return value
    value = value.strip()
    if len(value) == 10 and value.count('-') == 2:
        return f"{value} 23:59:59" if end_of_day else f"{value} 00:00:00"
    return value


def register_violation_routes(app, socketio, login_required, get_yolo_state=None):
    """Register violation-related API routes"""

    @app.route('/api/violations', methods=['GET'])
    @login_required
    def get_violations():
        """Get violations with filters"""
        try:
            robot_id = request.args.get('robot_id', type=int)
            violation_type = request.args.get('type')
            severity = request.args.get('severity')
            status = request.args.get('status')
            acknowledged_raw = request.args.get('acknowledged')
            start_date = _normalize_date(request.args.get('start_date'))
            end_date = _normalize_date(request.args.get('end_date'), end_of_day=True)
            limit = request.args.get('limit', 100, type=int)

            acknowledged = _parse_bool(acknowledged_raw)
            if status:
                if status == 'pending':
                    acknowledged = False
                elif status == 'acknowledged':
                    acknowledged = True
            
            violations = db.get_violations(
                robot_id=robot_id,
                violation_type=violation_type,
                severity=severity,
                acknowledged=acknowledged,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
            
            return jsonify({'success': True, 'violations': violations})
        except Exception as e:
            logger.error(f"Error getting violations: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/violations/stats', methods=['GET'])
    @login_required
    def get_violation_stats():
        """Get violation statistics"""
        try:
            robot_id = request.args.get('robot_id', type=int)
            stats = db.get_violation_stats(robot_id=robot_id)
            if get_yolo_state:
                live = get_yolo_state() or {}
                live_total = int(live.get('total_violations', 0) or 0)
                if stats.get('total', 0) == 0 and live_total > 0:
                    stats['total'] = live_total
                    stats['today_total'] = live_total
                    stats['pending_total'] = live_total
                    stats['pending_high'] = 0
            return jsonify({'success': True, 'stats': stats})
        except Exception as e:
            logger.error(f"Error getting violation stats: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/violations/summary', methods=['GET'])
    @login_required
    def get_violation_summary():
        """Get grouped violation summary"""
        try:
            robot_id = request.args.get('robot_id', type=int)
            violation_type = request.args.get('type')
            severity = request.args.get('severity')
            status = request.args.get('status')
            acknowledged_raw = request.args.get('acknowledged')
            start_date = _normalize_date(request.args.get('start_date'))
            end_date = _normalize_date(request.args.get('end_date'), end_of_day=True)
            group_by = request.args.get('group_by', 'day')

            acknowledged = _parse_bool(acknowledged_raw)
            if status:
                if status == 'pending':
                    acknowledged = False
                elif status == 'acknowledged':
                    acknowledged = True

            summary = db.get_violation_summary(
                group_by=group_by,
                robot_id=robot_id,
                violation_type=violation_type,
                severity=severity,
                acknowledged=acknowledged,
                start_date=start_date,
                end_date=end_date,
                limit=365
            )
            if not summary and get_yolo_state:
                live = get_yolo_state() or {}
                live_total = int(live.get('total_violations', 0) or 0)
                if live_total > 0:
                    summary = [{
                        'period': datetime.now().strftime('%Y-%m-%d'),
                        'total': live_total,
                        'high_count': 0,
                        'medium_count': 0,
                        'low_count': 0,
                        'acknowledged_count': 0
                    }]
            return jsonify({'success': True, 'summary': summary})
        except Exception as e:
            logger.error(f"Error getting violation summary: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/violations', methods=['POST'])
    def report_violation():
        """Report a new violation (called by YOLO server)"""
        try:
            data = request.json
            
            robot_id = data.get('robot_id')
            location = data.get('location')
            violation_type = data.get('violation_type')
            image_path = data.get('image_path')
            severity = data.get('severity', 'medium')
            details = data.get('details')
            
            if not all([robot_id, location, violation_type]):
                return jsonify({'success': False, 'error': 'Missing required fields'}), 400
            
            # Add violation to database
            violation_id = db.add_violation(
                robot_id=robot_id,
                location=location,
                violation_type=violation_type,
                image_path=image_path,
                severity=severity,
                details=details
            )
            
            # Log activity
            db.add_activity_log(
                robot_id=robot_id,
                level='warning',
                message=f"PPE violation detected: {violation_type} at {location}",
                details=details
            )
            
            # Emit real-time alert via WebSocket (if enabled)
            notifications_enabled = _parse_bool(db.get_setting('notifications_enabled', 'true'))
            notify_in_app = _parse_bool(db.get_setting('notify_in_app', 'true'))
            if notifications_enabled and notify_in_app:
                socketio.emit('violation_alert', {
                    'violation_id': violation_id,
                    'robot_id': robot_id,
                    'location': location,
                    'violation_type': violation_type,
                    'severity': severity,
                    'image_path': image_path,
                    'timestamp': datetime.now().isoformat()
                })
            
            return jsonify({'success': True, 'violation_id': violation_id})
        except Exception as e:
            logger.error(f"Error reporting violation: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/violations/<int:violation_id>/acknowledge', methods=['POST'])
    @login_required
    def acknowledge_violation(violation_id):
        """Acknowledge a violation"""
        try:
            acknowledged_by = request.json.get('acknowledged_by', session.get('username', 'unknown'))
            success = db.acknowledge_violation(violation_id, acknowledged_by)
            
            if success:
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Violation not found'}), 404
        except Exception as e:
            logger.error(f"Error acknowledging violation: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/violations/export', methods=['GET'])
    @login_required
    def export_violations():
        """Export violations to CSV"""
        try:
            robot_id = request.args.get('robot_id', type=int)
            violation_type = request.args.get('type')
            severity = request.args.get('severity')
            status = request.args.get('status')
            acknowledged_raw = request.args.get('acknowledged')
            start_date = _normalize_date(request.args.get('start_date'))
            end_date = _normalize_date(request.args.get('end_date'), end_of_day=True)

            acknowledged = _parse_bool(acknowledged_raw)
            if status:
                if status == 'pending':
                    acknowledged = False
                elif status == 'acknowledged':
                    acknowledged = True

            violations = db.get_violations(
                robot_id=robot_id,
                violation_type=violation_type,
                severity=severity,
                acknowledged=acknowledged,
                start_date=start_date,
                end_date=end_date,
                limit=1000
            )
            
            # Create CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                'id', 'robot_name', 'location', 'timestamp', 'violation_type', 
                'severity', 'acknowledged', 'acknowledged_by'
            ])
            writer.writeheader()
            
            for v in violations:
                writer.writerow({
                    'id': v['id'],
                    'robot_name': v.get('robot_name', ''),
                    'location': v['location'],
                    'timestamp': v['timestamp'],
                    'violation_type': v['violation_type'],
                    'severity': v['severity'],
                    'acknowledged': v['acknowledged'],
                    'acknowledged_by': v.get('acknowledged_by', '')
                })
            
            output.seek(0)
            return output.getvalue(), 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=violations_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        except Exception as e:
            logger.error(f"Error exporting violations: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


def register_schedule_routes(app, login_required, patrol_manager=None, mqtt_manager=None):
    """Register schedule-related API routes"""
    
    @app.route('/api/schedules', methods=['GET'])
    @login_required
    def get_schedules():
        """Get all schedules"""
        try:
            enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
            schedules = db.get_all_schedules(enabled_only=enabled_only)
            return jsonify({'success': True, 'schedules': schedules})
        except Exception as e:
            logger.error(f"Error getting schedules: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/schedules/history', methods=['GET'])
    @login_required
    def get_schedule_history():
        """Get recent schedule runs"""
        try:
            limit = request.args.get('limit', 50, type=int)
            runs = db.get_schedule_runs(limit=limit)
            return jsonify({'success': True, 'runs': runs})
        except Exception as e:
            logger.error(f"Error getting schedule history: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/schedules', methods=['POST'])
    @login_required
    def create_schedule():
        """Create a new schedule"""
        try:
            data = request.json
            route_id = data.get('route_id')
            name = data.get('name')
            schedule_type = data.get('schedule_type')  # 'daily', 'weekly', 'custom'
            schedule_config = data.get('schedule_config')
            enabled = 1 if data.get('enabled', 1) else 0
            
            if not all([route_id, name, schedule_type, schedule_config]):
                return jsonify({'success': False, 'error': 'Missing required fields'}), 400

            # Basic validation & conflict detection
            if schedule_type not in ('daily', 'weekly', 'once', 'custom'):
                return jsonify({'success': False, 'error': 'Invalid schedule type'}), 400

            def _conflicts(existing, candidate):
                if existing.get('schedule_type') != candidate.get('schedule_type'):
                    return False
                if int(existing.get('route_id')) != int(candidate.get('route_id')):
                    return False
                a = existing.get('schedule_config') or {}
                b = candidate.get('schedule_config') or {}
                if schedule_type == 'daily':
                    return a.get('time') == b.get('time')
                if schedule_type == 'weekly':
                    days_a = sorted(a.get('days') or [])
                    days_b = sorted(b.get('days') or [])
                    return days_a == days_b and a.get('time') == b.get('time')
                if schedule_type == 'once':
                    return a.get('datetime') == b.get('datetime')
                return False

            existing_schedules = db.get_all_schedules(enabled_only=False)
            for existing in existing_schedules:
                if _conflicts(existing, {
                    'route_id': route_id,
                    'schedule_type': schedule_type,
                    'schedule_config': schedule_config
                }):
                    return jsonify({'success': False, 'error': f"Schedule conflicts with '{existing.get('name')}'"}), 400
            
            schedule_id = db.create_schedule(route_id, name, schedule_type, schedule_config, enabled=enabled)
            
            db.add_activity_log(
                robot_id=None,
                level='info',
                message=f"Schedule created: {name}",
                category='schedule'
            )
            
            return jsonify({'success': True, 'schedule_id': schedule_id})
        except Exception as e:
            logger.error(f"Error creating schedule: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/schedules/<int:schedule_id>/run', methods=['POST'])
    @login_required
    def run_schedule_now(schedule_id):
        """Run a schedule immediately"""
        try:
            schedule = db.get_schedule_by_id(schedule_id)
            if not schedule:
                return jsonify({'success': False, 'error': 'Schedule not found'}), 404

            route_id = schedule.get('route_id')
            route = db.get_route_by_id(route_id)
            if not route:
                return jsonify({'success': False, 'error': 'Route not found'}), 404

            robot_id = route.get('robot_id')
            if mqtt_manager and not mqtt_manager.is_robot_connected(robot_id):
                return jsonify({'success': False, 'error': 'Robot not connected'}), 400

            run_id = db.create_schedule_run(schedule_id, route_id, robot_id, status='running')
            started = False
            try:
                if patrol_manager:
                    started = patrol_manager.start_patrol(robot_id, route)
            except Exception as exc:
                logger.error(f"Run schedule now error: {exc}")

            if started:
                try:
                    db.start_patrol_history(robot_id, route_id)
                except Exception as exc:
                    logger.error(f"Failed to start patrol history: {exc}")
                db.update_schedule_run(run_id, 'started', 'Manual run started')
                db.update_schedule_last_run(schedule_id)
                return jsonify({'success': True})

            db.update_schedule_run(run_id, 'failed', 'Failed to start patrol')
            return jsonify({'success': False, 'error': 'Failed to start patrol'}), 500
        except Exception as e:
            logger.error(f"Error running schedule now: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/schedules/<int:schedule_id>', methods=['PUT'])
    @login_required
    def update_schedule(schedule_id):
        """Update a schedule"""
        try:
            data = request.json
            success = db.update_schedule(schedule_id, **data)
            
            if success:
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Schedule not found'}), 404
        except Exception as e:
            logger.error(f"Error updating schedule: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
    @login_required
    def delete_schedule(schedule_id):
        """Delete a schedule"""
        try:
            success = db.delete_schedule(schedule_id)
            
            if success:
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Schedule not found'}), 404
        except Exception as e:
            logger.error(f"Error deleting schedule: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


def register_detection_routes(app, mqtt_manager, login_required):
    """Register detection-related API routes"""
    
    @app.route('/api/detection/start', methods=['POST'])
    @login_required
    def start_detection():
        """Start detection for a robot"""
        try:
            data = request.json
            robot_id = data.get('robot_id')
            route_id = data.get('route_id')
            
            if not robot_id:
                return jsonify({'success': False, 'error': 'Missing robot_id'}), 400
            
            # Start detection session
            session_id = db.start_detection_session(robot_id, route_id)
            
            db.add_activity_log(
                robot_id=robot_id,
                level='info',
                message=f"Detection started",
                category='detection'
            )
            
            return jsonify({'success': True, 'session_id': session_id})
        except Exception as e:
            logger.error(f"Error starting detection: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/detection/stop', methods=['POST'])
    @login_required
    def stop_detection():
        """Stop detection for a robot"""
        try:
            data = request.json
            robot_id = data.get('robot_id')
            
            if not robot_id:
                return jsonify({'success': False, 'error': 'Missing robot_id'}), 400
            
            # Get active session
            session = db.get_active_detection_session(robot_id)
            if session:
                # Count violations in this session
                violations = db.get_violations(robot_id=robot_id, limit=1000)
                # Filter to this session timeframe
                session_violations = [v for v in violations 
                                     if v['timestamp'] >= session['started_at']]
                
                db.end_detection_session(session['id'], len(session_violations))
                
                db.add_activity_log(
                    robot_id=robot_id,
                    level='info',
                    message=f"Detection stopped. {len(session_violations)} violations detected",
                    category='detection'
                )
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error stopping detection: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/detection/status/<int:robot_id>', methods=['GET'])
    @login_required
    def get_detection_status(robot_id):
        """Get detection status for a robot"""
        try:
            session = db.get_active_detection_session(robot_id)
            
            if session:
                return jsonify({'success': True, 'active': True, 'session': session})
            else:
                return jsonify({'success': True, 'active': False})
        except Exception as e:
            logger.error(f"Error getting detection status: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/detection/sessions', methods=['GET'])
    @login_required
    def get_detection_sessions():
        """Get detection sessions"""
        try:
            robot_id = request.args.get('robot_id', type=int)
            status = request.args.get('status')
            start_date = _normalize_date(request.args.get('start_date'))
            end_date = _normalize_date(request.args.get('end_date'), end_of_day=True)
            limit = request.args.get('limit', 100, type=int)

            sessions = db.get_detection_sessions(
                robot_id=robot_id,
                status=status,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
            return jsonify({'success': True, 'sessions': sessions})
        except Exception as e:
            logger.error(f"Error getting detection sessions: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/detection/sessions/export', methods=['GET'])
    @login_required
    def export_detection_sessions():
        """Export detection sessions to CSV"""
        try:
            sessions = db.get_detection_sessions(limit=1000)
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                'id', 'robot_id', 'robot_name', 'route_id', 'route_name',
                'status', 'started_at', 'ended_at', 'violations_count'
            ])
            writer.writeheader()
            for s in sessions:
                writer.writerow({
                    'id': s.get('id'),
                    'robot_id': s.get('robot_id'),
                    'robot_name': s.get('robot_name'),
                    'route_id': s.get('route_id'),
                    'route_name': s.get('route_name'),
                    'status': s.get('status'),
                    'started_at': s.get('started_at'),
                    'ended_at': s.get('ended_at'),
                    'violations_count': s.get('violations_count')
                })
            output.seek(0)
            return output.getvalue(), 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=detection_sessions_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        except Exception as e:
            logger.error(f"Error exporting detection sessions: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
