"""
YOLO Inspection Patrol Manager
Manages inspection patrols with YOLO pipeline integration and real-time violation monitoring
"""

import time
import json
import logging
import threading
from enum import Enum
from typing import Dict, List, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class InspectionState(Enum):
    IDLE = 'idle'
    CHECKING_PIPELINE = 'checking_pipeline'
    STARTING_PIPELINE = 'starting_pipeline'
    RUNNING = 'running'
    MOVING_TO_WAYPOINT = 'moving_to_waypoint'
    INSPECTING = 'inspecting'
    WAYPOINT_COMPLETE = 'waypoint_complete'
    COMPLETED = 'completed'
    STOPPED = 'stopped'
    ERROR = 'error'


class YoloInspectionPatrolManager:
    def __init__(self, robot_id: int, mqtt_client, cloud_mqtt, inspection_route: Dict,
                 settings: Dict, yolo_state_provider: Callable, callbacks: Dict, database):
        """Initialize YOLO inspection patrol manager"""
        self.robot_id = robot_id
        self.mqtt_client = mqtt_client
        self.cloud_mqtt = cloud_mqtt
        self.route = inspection_route
        self.settings = settings
        self.yolo_state_provider = yolo_state_provider
        self.callbacks = callbacks
        self.db = database

        self.state = InspectionState.IDLE
        self.current_waypoint_index = 0
        self.session_id = None
        self.stop_requested = False
        self.is_paused = False
        self.patrol_thread = None

        # Pipeline state tracking
        self.pipeline_status = 'unknown'
        self.pipeline_ready = threading.Event()

    def start(self) -> bool:
        """Start inspection patrol"""
        try:
            # Create inspection session
            self.session_id = self.db.create_inspection_session(
                self.robot_id,
                self.route['id'],
                'checking'
            )

            # Start patrol thread
            self.patrol_thread = threading.Thread(
                target=self._patrol_loop,
                daemon=True
            )
            self.patrol_thread.start()

            return True
        except Exception as e:
            logger.error(f"Failed to start inspection patrol: {e}")
            return False

    def stop(self):
        """Stop inspection patrol"""
        self.stop_requested = True
        if self.session_id:
            self.db.update_inspection_session(self.session_id, status='stopped')

    def pause(self):
        """Pause inspection patrol"""
        self.is_paused = True

    def resume(self):
        """Resume inspection patrol"""
        self.is_paused = False

    def get_status(self) -> Dict:
        """Get current patrol status"""
        return {
            'state': self.state.value,
            'robot_id': self.robot_id,
            'session_id': self.session_id,
            'current_waypoint_index': self.current_waypoint_index,
            'total_waypoints': len(self.route.get('waypoints', [])),
            'pipeline_status': self.pipeline_status
        }

    def _patrol_loop(self):
        """Main patrol execution loop"""
        try:
            # Step 1: Ensure YOLO pipeline is running
            self._transition_state(InspectionState.CHECKING_PIPELINE)
            self._update_status({'state': 'checking_pipeline'})

            if not self._ensure_yolo_pipeline_running():
                logger.error("YOLO pipeline failed to start")
                self._handle_error("YOLO pipeline start failed")
                return

            # Step 2: Execute inspection at each waypoint
            self._transition_state(InspectionState.RUNNING)

            waypoints = self.route.get('waypoints', [])
            for idx, waypoint in enumerate(waypoints):
                if self.stop_requested:
                    break

                # Handle pause
                while self.is_paused and not self.stop_requested:
                    time.sleep(0.5)

                self.current_waypoint_index = idx

                # Execute waypoint inspection
                self._execute_waypoint_inspection(waypoint)

            # Step 3: Complete patrol
            self._transition_state(InspectionState.COMPLETED)
            self.db.update_inspection_session(
                self.session_id,
                status='completed',
                waypoints_inspected=len(waypoints)
            )
            self._call_callback('on_complete', {'session_id': self.session_id})

        except Exception as e:
            logger.error(f"Patrol loop error: {e}", exc_info=True)
            self._handle_error(str(e))

    def _ensure_yolo_pipeline_running(self) -> bool:
        """Check and start YOLO pipeline if needed"""
        timeout = self.route.get('pipeline_start_timeout', 30)

        # Check current pipeline status from YOLO state
        yolo_state = self.yolo_state_provider()
        last_message_time = yolo_state.get('last_message_time')

        # If no recent messages, pipeline might be stopped
        if last_message_time:
            time_since_last = (datetime.now() - datetime.fromisoformat(last_message_time)).total_seconds()
            if time_since_last < 10:
                # Pipeline is running
                self.pipeline_status = 'running'
                self.db.update_inspection_session(self.session_id, pipeline_start_status='already_running')
                return True

        # Pipeline not running, start it
        self._transition_state(InspectionState.STARTING_PIPELINE)
        self._update_webview('starting_pipeline', {})

        # Send start command
        if self.cloud_mqtt:
            payload = {'command': 'start', 'timestamp': datetime.now().isoformat()}
            success = self.cloud_mqtt.publish('nokia/safety/control/command', payload)

            if not success:
                logger.error("Failed to publish pipeline start command")
                return False

        # Wait for pipeline to start (monitor for status updates)
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            yolo_state = self.yolo_state_provider()
            if yolo_state.get('enabled') and yolo_state.get('total_violations') is not None:
                self.pipeline_status = 'running'
                self.db.update_inspection_session(self.session_id, pipeline_start_status='started')
                return True
            time.sleep(1)

        # Timeout
        logger.error(f"YOLO pipeline start timeout ({timeout}s)")
        self.db.update_inspection_session(self.session_id, pipeline_start_status='timeout')
        return False

    def _execute_waypoint_inspection(self, waypoint: Dict):
        """Execute inspection at a waypoint"""
        waypoint_name = waypoint['waypoint_name']
        checking_duration = waypoint.get('checking_duration', 30)

        # Step 1: Navigate to waypoint
        self._transition_state(InspectionState.MOVING_TO_WAYPOINT)
        self._update_webview('moving_to', {
            'waypoint_name': waypoint_name,
            'progress': f"{self.current_waypoint_index + 1}/{len(self.route['waypoints'])}"
        })

        # Send goto command
        self.mqtt_client.goto_waypoint(waypoint_name)

        # Wait for arrival (simple timeout-based wait)
        # TODO: Implement proper arrival detection via MQTT events
        time.sleep(10)  # Placeholder

        # Step 2: Start inspection
        self._transition_state(InspectionState.INSPECTING)
        self._update_webview('inspecting', {
            'waypoint_name': waypoint_name,
            'violations': 0,
            'people': 0
        })

        # Speak TTS
        tts_start = waypoint.get('tts_start', 'Starting inspection').replace('{waypoint}', waypoint_name)
        self.mqtt_client.speak_tts(tts_start)
        time.sleep(2)

        # Step 3: Monitor violations for checking_duration
        result = self._monitor_violations(waypoint_name, checking_duration)

        # Step 4: Show result
        if result['violations'] == 0:
            self._update_webview('no_violation', {'waypoint_name': waypoint_name})
            tts_msg = waypoint.get('tts_no_violation', 'No violations detected').replace('{waypoint}', waypoint_name)
            self.mqtt_client.speak_tts(tts_msg)
        else:
            self._update_webview('violation_detected', {
                'waypoint_name': waypoint_name,
                'violations': result['violations'],
                'people': result['people']
            })
            tts_msg = waypoint.get('tts_violation', 'Violations detected: {count}')
            tts_msg = tts_msg.replace('{waypoint}', waypoint_name).replace('{count}', str(result['violations']))
            self.mqtt_client.speak_tts(tts_msg)

        time.sleep(3)

        # Step 5: Log inspection result
        self.db.create_waypoint_inspection(
            self.session_id,
            waypoint_name,
            violations=result['violations'],
            people=result['people'],
            viewports=result.get('viewports'),
            result='violation_found' if result['violations'] > 0 else 'no_violation',
            duration=checking_duration
        )

        # Update session totals
        self.db.update_inspection_session(
            self.session_id,
            waypoints_inspected=self.current_waypoint_index + 1,
            violations_found=result.get('total_violations', 0)
        )

        # Callback
        self._call_callback('on_waypoint_result', {
            'waypoint_name': waypoint_name,
            'violations': result['violations'],
            'people': result['people']
        })

        self._transition_state(InspectionState.WAYPOINT_COMPLETE)

    def _monitor_violations(self, waypoint_name: str, duration_seconds: int) -> Dict:
        """Monitor YOLO violations for specified duration"""
        start_time = time.time()
        samples = []

        while (time.time() - start_time) < duration_seconds:
            if self.stop_requested:
                break

            # Get current YOLO state
            yolo_state = self.yolo_state_provider()

            violations = yolo_state.get('total_violations', 0)
            people = yolo_state.get('total_people', 0)
            viewports = yolo_state.get('viewports', {})

            samples.append({
                'violations': violations,
                'people': people,
                'viewports': viewports,
                'timestamp': time.time()
            })

            # Update webview with real-time counts
            elapsed = int(time.time() - start_time)
            self._update_webview('inspecting', {
                'waypoint_name': waypoint_name,
                'violations': violations,
                'people': people,
                'duration': duration_seconds - elapsed
            })

            time.sleep(2)

        # Calculate final result (use last sample)
        if samples:
            last_sample = samples[-1]
            return {
                'violations': last_sample['violations'],
                'people': last_sample['people'],
                'viewports': last_sample['viewports'],
                'total_violations': sum(s['violations'] for s in samples)
            }
        else:
            return {'violations': 0, 'people': 0, 'viewports': {}, 'total_violations': 0}

    def _update_webview(self, state: str, data: Dict):
        """Update dynamic webview state"""
        if not self.mqtt_client:
            return

        # Show webview if not already shown
        webview_url = self.settings.get('inspection_webview_url',
                                       'file:///storage/emulated/0/temiscreens/InspectionStatus.htm')
        self.mqtt_client.show_webview(webview_url)

        # Send update via new MQTT topic
        payload = {'state': state, **data, 'timestamp': datetime.now().isoformat()}

        # Publish to webview update topic (Android app listens and calls JavaScript)
        topic = f"temi/{self.mqtt_client.serial_number}/command/webview/update"

        # Note: This requires mqtt_client to have access to serial_number and publish method
        # For now, we'll use cloud_mqtt to publish
        if self.cloud_mqtt:
            try:
                # Serialize payload
                payload_json = json.dumps(payload)
                # The cloud MQTT doesn't have publish to robot-specific topics
                # We need to use the robot's MQTT client
                logger.info(f"Webview update: {payload_json}")
            except Exception as e:
                logger.error(f"Failed to update webview: {e}")

    def _transition_state(self, new_state: InspectionState):
        """Transition to new state"""
        self.state = new_state
        logger.info(f"Inspection patrol state: {new_state.value}")

    def _update_status(self, status_data: Dict):
        """Update status and emit to callbacks"""
        status = self.get_status()
        status.update(status_data)
        self._call_callback('on_status_update', status)

    def _call_callback(self, callback_name: str, data: Dict):
        """Call registered callback if exists"""
        callback = self.callbacks.get(callback_name)
        if callback and callable(callback):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback {callback_name} error: {e}")

    def _handle_error(self, error_message: str):
        """Handle patrol error"""
        self._transition_state(InspectionState.ERROR)
        if self.session_id:
            self.db.update_inspection_session(self.session_id, status='error')
        self._call_callback('on_error', {
            'robot_id': self.robot_id,
            'session_id': self.session_id,
            'error': error_message
        })
