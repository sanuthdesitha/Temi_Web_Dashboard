"""
WebView Management API Module
Handles CRUD operations for webview templates and their usage tracking
"""

from flask import request, jsonify
from database import get_db
import logging

logger = logging.getLogger(__name__)


def register_webview_routes(app, login_required):
    """Register all webview-related API routes"""

    @app.route('/api/webviews', methods=['GET'])
    @login_required
    def api_get_webviews():
        """Get all webview templates"""
        try:
            category = request.args.get('category')
            system_only = request.args.get('system_only', type=bool, default=False)

            with get_db() as conn:
                cursor = conn.cursor()

                if system_only:
                    cursor.execute('''
                        SELECT id, name, category, description, file_path, system_template
                        FROM webview_templates
                        WHERE system_template = 1
                        ORDER BY category, name
                    ''')
                elif category:
                    cursor.execute('''
                        SELECT id, name, category, description, file_path, system_template
                        FROM webview_templates
                        WHERE category = ?
                        ORDER BY name
                    ''', (category,))
                else:
                    cursor.execute('''
                        SELECT id, name, category, description, file_path, system_template
                        FROM webview_templates
                        ORDER BY category, name
                    ''')

                templates = [dict(row) for row in cursor.fetchall()]

            return jsonify({'success': True, 'templates': templates})
        except Exception as e:
            logger.error(f"Error fetching webviews: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/webviews/<int:template_id>', methods=['GET'])
    @login_required
    def api_get_webview(template_id):
        """Get specific webview template"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, category, description, file_path, html_content, system_template
                    FROM webview_templates
                    WHERE id = ?
                ''', (template_id,))

                row = cursor.fetchone()
                if not row:
                    return jsonify({'success': False, 'error': 'Template not found'}), 404

                template = dict(row)

            return jsonify({'success': True, 'template': template})
        except Exception as e:
            logger.error(f"Error fetching webview {template_id}: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/webviews', methods=['POST'])
    @login_required
    def api_create_webview():
        """Create new custom webview template"""
        try:
            data = request.json
            name = data.get('name')
            category = data.get('category')
            description = data.get('description')
            file_path = data.get('file_path')
            html_content = data.get('html_content')

            if not all([name, category, file_path]):
                return jsonify({'success': False, 'error': 'Missing required fields'}), 400

            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO webview_templates
                    (name, category, description, file_path, html_content, system_template)
                    VALUES (?, ?, ?, ?, ?, 0)
                ''', (name, category, description, file_path, html_content))
                conn.commit()
                template_id = cursor.lastrowid

            logger.info(f"Created webview template: {name} (ID: {template_id})")
            return jsonify({'success': True, 'template_id': template_id}), 201
        except Exception as e:
            logger.error(f"Error creating webview: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/webviews/<int:template_id>', methods=['PUT'])
    @login_required
    def api_update_webview(template_id):
        """Update webview template"""
        try:
            data = request.json

            with get_db() as conn:
                cursor = conn.cursor()

                # Check if system template
                cursor.execute('SELECT system_template FROM webview_templates WHERE id = ?', (template_id,))
                row = cursor.fetchone()
                if not row:
                    return jsonify({'success': False, 'error': 'Template not found'}), 404

                if row['system_template']:
                    return jsonify({'success': False, 'error': 'Cannot modify system templates'}), 403

                # Update fields
                updates = []
                params = []
                for field in ['name', 'category', 'description', 'file_path', 'html_content']:
                    if field in data:
                        updates.append(f"{field} = ?")
                        params.append(data[field])

                if not updates:
                    return jsonify({'success': False, 'error': 'No fields to update'}), 400

                params.append(template_id)
                cursor.execute(
                    f"UPDATE webview_templates SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    params
                )
                conn.commit()

            logger.info(f"Updated webview template ID: {template_id}")
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error updating webview {template_id}: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/webviews/<int:template_id>', methods=['DELETE'])
    @login_required
    def api_delete_webview(template_id):
        """Delete custom webview template"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()

                # Check if system template
                cursor.execute('SELECT system_template FROM webview_templates WHERE id = ?', (template_id,))
                row = cursor.fetchone()
                if not row:
                    return jsonify({'success': False, 'error': 'Template not found'}), 404

                if row['system_template']:
                    return jsonify({'success': False, 'error': 'Cannot delete system templates'}), 403

                cursor.execute('DELETE FROM webview_templates WHERE id = ?', (template_id,))
                conn.commit()

            logger.info(f"Deleted webview template ID: {template_id}")
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error deleting webview {template_id}: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/webviews/categories', methods=['GET'])
    @login_required
    def api_get_webview_categories():
        """Get all webview template categories"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT category FROM webview_templates ORDER BY category
                ''')
                categories = [row['category'] for row in cursor.fetchall()]

            return jsonify({'success': True, 'categories': categories})
        except Exception as e:
            logger.error(f"Error fetching categories: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/webviews/<int:template_id>/stats', methods=['GET'])
    @login_required
    def api_get_webview_stats(template_id):
        """Get usage statistics for a webview template"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        COUNT(*) as display_count,
                        SUM(total_display_time_seconds) as total_time,
                        MIN(first_used) as first_used,
                        MAX(last_used) as last_used
                    FROM webview_usage_stats
                    WHERE webview_template_id = ?
                ''', (template_id,))

                row = cursor.fetchone()
                stats = {
                    'display_count': row['display_count'] or 0,
                    'total_display_time': row['total_time'] or 0.0,
                    'first_used': row['first_used'],
                    'last_used': row['last_used']
                }

            return jsonify({'success': True, 'stats': stats})
        except Exception as e:
            logger.error(f"Error fetching webview stats: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/webviews/track-usage', methods=['POST'])
    @login_required
    def api_track_webview_usage():
        """Track webview usage for analytics"""
        try:
            data = request.json
            template_id = data.get('template_id')
            patrol_id = data.get('patrol_id')
            display_time = data.get('display_time_seconds', 0.0)

            if not template_id:
                return jsonify({'success': False, 'error': 'Missing template_id'}), 400

            with get_db() as conn:
                cursor = conn.cursor()

                # Check if record exists
                cursor.execute('''
                    SELECT id FROM webview_usage_stats
                    WHERE webview_template_id = ? AND patrol_id = ?
                ''', (template_id, patrol_id))

                existing = cursor.fetchone()

                if existing:
                    cursor.execute('''
                        UPDATE webview_usage_stats
                        SET display_count = display_count + 1,
                            total_display_time_seconds = total_display_time_seconds + ?,
                            last_used = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (display_time, existing['id']))
                else:
                    cursor.execute('''
                        INSERT INTO webview_usage_stats
                        (webview_template_id, patrol_id, display_count, total_display_time_seconds, first_used, last_used)
                        VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (template_id, patrol_id, display_time))

                conn.commit()

            logger.debug(f"Tracked webview {template_id} usage in patrol {patrol_id}")
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error tracking webview usage: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    return {
        'get_webviews': api_get_webviews,
        'get_webview': api_get_webview,
        'create_webview': api_create_webview,
        'update_webview': api_update_webview,
        'delete_webview': api_delete_webview,
        'get_categories': api_get_webview_categories,
        'get_stats': api_get_webview_stats,
        'track_usage': api_track_webview_usage,
    }
