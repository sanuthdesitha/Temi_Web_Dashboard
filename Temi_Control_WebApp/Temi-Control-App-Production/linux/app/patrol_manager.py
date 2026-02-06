"""
Patrol Manager module for Temi Control Application
Handles patrol state machine and route execution
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PatrolState(Enum):
    """Patrol states"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    WAITING = "waiting"
    LOW_BATTERY = "low_battery"
    ERROR = "error"


class PatrolManager:
    """Manages patrol execution for a single robot"""
    
    def __init__(self, robot_id: int, mqtt_client, route: Dict, settings: Dict,
                 on_status_update: Optional[Callable] = None,
                 on_waypoint_reached: Optional[Callable] = None,
                 on_complete: Optional[Callable] = None,
                 on_error: Optional[Callable] = None,
                 yolo_state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
                 on_waypoint_summary: Optional[Callable[[int, Dict, Dict, Dict, Optional[str], Optional[str]], None]] = None):
        self.robot_id = robot_id
        self.mqtt_client = mqtt_client
        self.route = route
        self.settings = settings
        
        # Callbacks
        self.on_status_update = on_status_update
        self.on_waypoint_reached = on_waypoint_reached
        self.on_complete = on_complete
        self.on_error = on_error
        self.yolo_state_provider = yolo_state_provider
        self.on_waypoint_summary = on_waypoint_summary
        
        # State
        self.state = PatrolState.IDLE
        self.current_waypoint_index = 0
        self.total_waypoints = len(route.get('waypoints', []))
        self.current_waypoint = None
        self.is_paused = False
        self.stop_requested = False
        
        # Loop tracking
        raw_loop_count = route.get('loop_count', 1)
        try:
            self.loop_count = int(raw_loop_count) if raw_loop_count is not None else 1
        except (TypeError, ValueError):
            self.loop_count = 1
        self.current_loop = 0
        self.is_infinite_loop = self.loop_count <= 0
        
        # Battery monitoring
        self.low_battery_threshold = int(settings.get('low_battery_threshold', 10))
        self.low_battery_action = settings.get('low_battery_action', 'complete_current')
        self.home_base_location = settings.get('home_base_location', 'home base')
        self.current_battery_level = 100
        self.is_low_battery = False
        self.return_after_current = False

        # Return location
        self.return_location = route.get('return_location') or self.home_base_location
        
        # Patrol thread
        self.patrol_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Movement speed
        self.movement_speed = float(settings.get('default_movement_speed', 0.5))
        
        # Waypoint tracking
        self.waiting_for_arrival = False
        self.last_goto_time = None
    
    def start(self):
        """Start patrol execution"""
        with self.lock:
            if self.state != PatrolState.IDLE:
                logger.warning(f"Cannot start patrol - current state: {self.state}")
                return False
            
            if self.total_waypoints == 0:
                logger.error("Cannot start patrol - no waypoints in route")
                self._emit_error("No waypoints in route")
                return False
            
            self.state = PatrolState.RUNNING
            self.current_waypoint_index = 0
            self.stop_requested = False
            self.is_paused = False
            
            # Start patrol thread
            self.patrol_thread = threading.Thread(target=self._patrol_loop, daemon=True)
            self.patrol_thread.start()
            
            self._emit_status_update()
            logger.info(f"Started patrol for robot {self.robot_id}")
            return True
    
    def stop(self):
        """Stop patrol execution"""
        with self.lock:
            if self.state == PatrolState.IDLE or self.state == PatrolState.STOPPED:
                return False
            
            self.stop_requested = True
            self.state = PatrolState.STOPPED
            
            # Stop robot movement
            self.mqtt_client.stop_movement()
            
            self._emit_status_update()
            logger.info(f"Stopped patrol for robot {self.robot_id}")
            return True
    
    def pause(self):
        """Pause patrol execution"""
        with self.lock:
            if self.state not in (PatrolState.RUNNING, PatrolState.WAITING):
                return False
            
            self.is_paused = True
            self.state = PatrolState.PAUSED
            
            # Stop robot movement
            self.mqtt_client.stop_movement()
            
            self._emit_status_update()
            logger.info(f"Paused patrol for robot {self.robot_id}")
            return True
    
    def resume(self):
        """Resume patrol execution"""
        with self.lock:
            if self.state != PatrolState.PAUSED:
                return False
            
            self.is_paused = False
            self.state = PatrolState.RUNNING

            if self.current_waypoint and self.waiting_for_arrival:
                try:
                    self.mqtt_client.goto_waypoint(self.current_waypoint.get('waypoint_name'))
                except Exception as exc:
                    logger.error(f"Failed to resume goto: {exc}")
            
            self._emit_status_update()
            logger.info(f"Resumed patrol for robot {self.robot_id}")
            return True
    
    def set_speed(self, speed: float):
        """Set movement speed"""
        self.movement_speed = max(0.1, min(1.0, speed))
        logger.info(f"Set movement speed to {self.movement_speed}")
    
    def update_battery_level(self, battery_level: int, is_charging: bool = False):
        """Update battery level and check for low battery"""
        if battery_level is None:
            return
        try:
            battery_level = int(battery_level)
        except (TypeError, ValueError):
            return
        self.current_battery_level = battery_level
        
        # Check for low battery
        if battery_level <= self.low_battery_threshold and not is_charging:
            if not self.is_low_battery:
                self.is_low_battery = True
                self.return_after_current = True
                self._handle_low_battery()
        else:
            self.is_low_battery = False
    
    def on_waypoint_event(self, event_type: str, location: str, status: str):
        """Handle waypoint navigation events from robot"""
        logger.info(f"Waypoint event: {event_type}, location: {location}, status: {status}")
        
        if event_type == "goto":
            if status == "start":
                self.waiting_for_arrival = True
                self.last_goto_time = time.time()
            elif status == "complete":
                self.waiting_for_arrival = False
                self._on_waypoint_arrival()
            elif status == "abort" or status == "fail":
                self.waiting_for_arrival = False
                self._emit_error(f"Failed to reach waypoint: {location}")
        
        elif event_type == "arrived":
            self.waiting_for_arrival = False
            self._on_waypoint_arrival()
    
    def _patrol_loop(self):
        """Main patrol execution loop with support for multiple loops"""
        try:
            # Initialize loop counter
            self.current_loop = 1
            keep_looping = True
            
            while keep_looping and not self.stop_requested:
                logger.info(f"Starting loop {self.current_loop}" + 
                          (f" of {self.loop_count}" if not self.is_infinite_loop else " (infinite)"))
                
                # Reset waypoint index for new loop
                self.current_waypoint_index = 0
                
                # Execute all waypoints in this loop
                while not self.stop_requested and self.current_waypoint_index < self.total_waypoints:
                    # Check if paused
                    if self.is_paused:
                        time.sleep(0.5)
                        continue
                    
                    # Get current waypoint
                    waypoint = self.route['waypoints'][self.current_waypoint_index]
                    self.current_waypoint = waypoint
                    
                    # Execute waypoint
                    self._execute_waypoint(waypoint)
                    
                    # Wait for completion
                    self._wait_for_waypoint_completion(waypoint)
                    
                    # Move to next waypoint
                    self.current_waypoint_index += 1
                    self._emit_status_update()
                
                # Loop completed
                if not self.stop_requested:
                    logger.info(f"Completed loop {self.current_loop}" + 
                              (f" of {self.loop_count}" if not self.is_infinite_loop else ""))
                    
                    # Check if we should continue looping
                    if self.is_infinite_loop:
                        keep_looping = True
                        self.current_loop += 1
                    else:
                        self.current_loop += 1
                        keep_looping = self.current_loop <= self.loop_count
                
            # Patrol complete
            if not self.stop_requested:
                self._return_to_location("route_complete")
                self.state = PatrolState.IDLE
                self._emit_complete()
                logger.info(f"Patrol completed for robot {self.robot_id}")
            
        except Exception as e:
            logger.error(f"Error in patrol loop: {e}")
            self.state = PatrolState.ERROR
            self._emit_error(str(e))
    
    def _execute_waypoint(self, waypoint: Dict):
        """Execute actions for a waypoint"""
        waypoint_name = waypoint['waypoint_name']
        
        logger.info(f"Executing waypoint: {waypoint_name}")
        patrolling_url = self.settings.get('patrolling_webview_url')
        if patrolling_url:
            try:
                self._show_webview_with_autoclose(patrolling_url)
            except Exception as exc:
                logger.error(f"Failed to show patrolling webview: {exc}")
        
        # Send goto command
        self.mqtt_client.goto_waypoint(waypoint_name)
        self.waiting_for_arrival = True
        self.last_goto_time = time.time()
        
        self.state = PatrolState.WAITING
        self._emit_status_update()

    def _auto_close_webview(self, close_delay: Optional[int] = None):
        """Close webview after delay using waypoint or global default."""
        try:
            delay = int(close_delay) if close_delay is not None else 0
        except (TypeError, ValueError):
            delay = 0
        if delay <= 0:
            try:
                delay = int(self.settings.get('webview_close_delay_seconds', 0))
            except (TypeError, ValueError):
                delay = 0
        if delay > 0:
            logger.info(f"[ACTION] Closing webview after {delay} seconds")
            time.sleep(delay)
            self.mqtt_client.close_webview()

    def _show_webview_with_autoclose(self, url: str, close_delay: Optional[int] = None) -> bool:
        """Show webview and auto-close after delay."""
        success = self.mqtt_client.show_webview(url)
        if success:
            self._auto_close_webview(close_delay)
        return success
    
    def _wait_for_waypoint_completion(self, waypoint: Dict):
        """Wait for waypoint arrival and execute actions with timeout and retry"""
        timeout = int(self.settings.get('waypoint_timeout', 60))  # Configurable timeout
        max_retries = int(self.settings.get('waypoint_max_retries', 2))
        retry_count = 0
        waypoint_name = waypoint['waypoint_name']
        
        while retry_count <= max_retries:
            start_time = time.time()
            
            # Wait for arrival
            while self.waiting_for_arrival and not self.stop_requested:
                if self.is_paused:
                    time.sleep(0.5)
                    start_time += 0.5
                    continue
                elapsed = time.time() - start_time
                
                # Log progress every 10 seconds
                if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                    logger.info(f"Waiting for waypoint '{waypoint_name}' arrival... ({int(elapsed)}s elapsed)")
                
                if elapsed > timeout:
                    if retry_count < max_retries:
                        logger.warning(f"Timeout waiting for waypoint '{waypoint_name}'. Retry {retry_count + 1}/{max_retries}")
                        retry_count += 1
                        # Resend goto command
                        self.mqtt_client.goto_waypoint(waypoint_name)
                        self.waiting_for_arrival = True
                        break
                    else:
                        logger.error(f"Timeout waiting for waypoint '{waypoint_name}' after {max_retries} retries")
                        self._emit_error(f"Failed to reach waypoint '{waypoint_name}' after {max_retries} retries")
                        self.waiting_for_arrival = False
                        return
                
                time.sleep(0.5)
            
            # If arrived or stopped, break retry loop
            if not self.waiting_for_arrival or self.stop_requested:
                break
        
        if self.stop_requested:
            return
        
        # Execute waypoint actions (display, TTS, etc.)
        self._execute_waypoint_actions(waypoint)

        # If low battery triggered return after completing waypoint
        if self.return_after_current:
            logger.warning("Low battery return triggered after current waypoint")
            self._return_to_location("low_battery_complete")
            self.stop_requested = True
    
    def _on_waypoint_arrival(self):
        """Called when robot arrives at waypoint"""
        if self.current_waypoint:
            logger.info(f"Arrived at waypoint: {self.current_waypoint['waypoint_name']}")
            
            if self.on_waypoint_reached:
                self.on_waypoint_reached(
                    self.robot_id,
                    self.current_waypoint_index,
                    self.current_waypoint
                )
    
    def _execute_waypoint_actions(self, waypoint: Dict):
        """Execute display and TTS actions at waypoint"""
        waypoint_name = waypoint.get('waypoint_name')
        try:
            tts_wait_seconds = int(self.settings.get('tts_wait_seconds', 3))
        except (TypeError, ValueError):
            tts_wait_seconds = 3
        try:
            display_wait_seconds = int(self.settings.get('display_wait_seconds', 2))
        except (TypeError, ValueError):
            display_wait_seconds = 2
        try:
            arrival_delay = int(self.settings.get('arrival_action_delay_seconds', 2))
        except (TypeError, ValueError):
            arrival_delay = 2

        if arrival_delay > 0:
            time.sleep(arrival_delay)

        if waypoint.get('detection_enabled'):
            self._run_detection_gate(waypoint)
        
        # Execute TTS action first (before display)
        tts_message = waypoint.get('tts_message')
        if tts_message:
            logger.info(f"[ACTION] Speaking TTS at '{waypoint_name}': {tts_message}")
            success = self.mqtt_client.speak_tts(tts_message)
            if success:
                logger.info("[ACTION] OK TTS command sent successfully")
            else:
                logger.error("[ACTION] FAILED to send TTS command")
            if tts_wait_seconds > 0:
                time.sleep(tts_wait_seconds)
        
        # Execute display action
        display_type = waypoint.get('display_type')
        display_content = waypoint.get('display_content')
        
        if display_type and display_content:
            logger.info(f"[ACTION] Displaying {display_type} at '{waypoint_name}': {display_content}")
            success = False
            
            if display_type == 'text':
                # Create HTML for text display
                html_content = f"""
                <html>
                <head><meta charset="UTF-8"></head>
                <body style='display:flex;justify-content:center;align-items:center;
                           height:100vh;font-size:48px;text-align:center;
                           background-color:#000;color:#fff;padding:20px;'>
                    {display_content}
                </body>
                </html>
                """
                # Use data URI for immediate display
                import base64
                encoded = base64.b64encode(html_content.encode()).decode()
                data_uri = f"data:text/html;base64,{encoded}"
                success = self.mqtt_client.show_webview(data_uri)
                
            elif display_type == 'image':
                success = self.mqtt_client.show_image(display_content)
                
            elif display_type == 'webview':
                success = self.mqtt_client.show_webview(display_content)

            elif display_type == 'video':
                success = self.mqtt_client.play_video(display_content)
            
            if success:
                logger.info("[ACTION] OK display command sent successfully")
            else:
                logger.error("[ACTION] FAILED to send display command")
            if display_wait_seconds > 0:
                time.sleep(display_wait_seconds)

            if display_type == 'webview' and success:
                try:
                    close_delay = waypoint.get('webview_close_delay')
                    close_delay = int(close_delay) if close_delay is not None else 0
                except (TypeError, ValueError):
                    close_delay = 0
                self._auto_close_webview(close_delay)
        
        # Dwell time at waypoint
        dwell_time = waypoint.get('dwell_time', 5)
        if dwell_time > 0:
            logger.info(f"[ACTION] Dwelling at waypoint for {dwell_time} seconds")
            
            # Wait with ability to stop
            for i in range(int(dwell_time * 2)):  # Check every 0.5 seconds
                if self.stop_requested:
                    logger.info("[ACTION] Dwell interrupted by stop request")
                    break
                time.sleep(0.5)

    def _get_yolo_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of the latest YOLO state"""
        if not self.yolo_state_provider:
            return {}
        try:
            snapshot = self.yolo_state_provider()
            return snapshot if isinstance(snapshot, dict) else {}
        except Exception as exc:
            logger.error(f"Failed to fetch YOLO snapshot: {exc}")
            return {}

    def _extract_violation_counts(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Extract violation counts from a YOLO snapshot"""
        yolo_payload = snapshot.get('yolo_payload') if isinstance(snapshot, dict) else {}
        total_violations = snapshot.get('total_violations')
        total_people = snapshot.get('total_people')
        total_compliant = snapshot.get('total_compliant')
        viewports = snapshot.get('viewports')

        if total_violations is None and isinstance(yolo_payload, dict):
            total_violations = yolo_payload.get('total_violations', 0)
        if total_people is None and isinstance(yolo_payload, dict):
            total_people = yolo_payload.get('total_people', 0)
        if total_compliant is None and isinstance(yolo_payload, dict):
            total_compliant = yolo_payload.get('total_compliant', 0)
        if viewports is None and isinstance(yolo_payload, dict):
            viewports = yolo_payload.get('viewports', {})

        try:
            total_violations = int(total_violations) if total_violations is not None else 0
        except (TypeError, ValueError):
            total_violations = 0

        try:
            total_people = int(total_people) if total_people is not None else 0
        except (TypeError, ValueError):
            total_people = 0

        try:
            total_compliant = int(total_compliant) if total_compliant is not None else 0
        except (TypeError, ValueError):
            total_compliant = 0

        return {
            'total_violations': total_violations,
            'total_people': total_people,
            'total_compliant': total_compliant,
            'viewports': viewports if isinstance(viewports, dict) else {},
            'yolo_payload': yolo_payload if isinstance(yolo_payload, dict) else {}
        }

    def _execute_violation_action(self, action: str, waypoint: Dict) -> Optional[str]:
        """Execute a violation response action"""
        if not action or action == 'none':
            return None

        if action == 'tts':
            message = waypoint.get('violation_tts_message') or self.settings.get(
                'violation_tts_default',
                'Please follow safety protocols and wear proper PPE.'
            )
            logger.info(f"[DETECTION] Speaking violation TTS: {message}")
            success = self.mqtt_client.speak_tts(message)
            return 'tts_ok' if success else 'tts_failed'

        if action == 'webview':
            url = waypoint.get('violation_display_content') or self.settings.get(
                'violation_webview_url', ''
            )
            if not url:
                url = self.settings.get('violation_display_content_default', '')
            if not url:
                return 'webview_skipped'
            logger.info(f"[DETECTION] Showing violation webview: {url}")
            success = self.mqtt_client.show_webview(url)
            if success:
                try:
                    close_delay = waypoint.get('webview_close_delay')
                    close_delay = int(close_delay) if close_delay is not None else 0
                except (TypeError, ValueError):
                    close_delay = 0
                self._auto_close_webview(close_delay)
            return 'webview_ok' if success else 'webview_failed'

        if action == 'video':
            url = waypoint.get('violation_display_content') or self.settings.get(
                'violation_webview_url', ''
            )
            if not url:
                url = self.settings.get('violation_display_content_default', '')
            if not url:
                return 'video_skipped'
            logger.info(f"[DETECTION] Playing violation video: {url}")
            success = self.mqtt_client.play_video(url)
            return 'video_ok' if success else 'video_failed'

        return None

    def _run_detection_gate(self, waypoint: Dict):
        """Wait for YOLO checks at waypoint and trigger violation action if needed"""
        waypoint_name = waypoint.get('waypoint_name')
        timeout = waypoint.get('detection_timeout')
        no_violation_seconds = waypoint.get('no_violation_seconds')

        if timeout is None:
            timeout = self.settings.get('detection_timeout_seconds', 30)
        if no_violation_seconds is None:
            no_violation_seconds = self.settings.get('no_violation_seconds', 5)

        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = 30
        try:
            no_violation_seconds = int(no_violation_seconds)
        except (TypeError, ValueError):
            no_violation_seconds = 5

        action = waypoint.get('violation_action') or self.settings.get('violation_action_default', 'tts')
        logger.info(f"[DETECTION] Monitoring at '{waypoint_name}' for up to {timeout}s")

        start_time = time.time()
        no_violation_start = None
        last_snapshot = None
        last_counts = None
        action_taken = None
        violations_seen = False

        while not self.stop_requested:
            snapshot = self._get_yolo_snapshot()
            if snapshot:
                last_snapshot = snapshot
            counts = self._extract_violation_counts(snapshot)
            last_counts = counts
            total_violations = counts['total_violations']

            if total_violations > 0:
                violations_seen = True
                no_violation_start = None
                if not action_taken:
                    action_taken = self._execute_violation_action(action, waypoint)
            else:
                if no_violation_start is None:
                    no_violation_start = time.time()
                if no_violation_seconds <= 0 or (time.time() - no_violation_start) >= no_violation_seconds:
                    break

            if (time.time() - start_time) >= timeout:
                break

            time.sleep(0.5)

        summary = self._build_waypoint_summary(last_snapshot, last_counts)
        notes = None
        if violations_seen:
            notes = "violations_detected"
        if (time.time() - start_time) >= timeout:
            notes = "timeout" if not notes else f"{notes},timeout"

        if not violations_seen and not self.stop_requested:
            no_violation_url = self.settings.get('no_violation_webview_url')
            if no_violation_url:
                try:
                    self._show_webview_with_autoclose(no_violation_url)
                except Exception as exc:
                    logger.error(f"Failed to show no-violation webview: {exc}")
                try:
                    display_wait_seconds = int(self.settings.get('display_wait_seconds', 2))
                except (TypeError, ValueError):
                    display_wait_seconds = 2
                if display_wait_seconds > 0:
                    time.sleep(display_wait_seconds)
            no_violation_tts = self.settings.get('no_violation_tts')
            if no_violation_tts:
                self.mqtt_client.speak_tts(no_violation_tts)

        if self.on_waypoint_summary and summary:
            try:
                self.on_waypoint_summary(self.robot_id, self.route, waypoint, summary, action_taken, notes)
            except Exception as exc:
                logger.error(f"Failed to record waypoint summary: {exc}")

    def _build_waypoint_summary(self, snapshot: Optional[Dict[str, Any]],
                                counts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build summary payload for waypoint logging"""
        if counts is None:
            counts = self._extract_violation_counts(snapshot or {})
        return {
            'timestamp': datetime.now().isoformat(),
            'total_people': counts.get('total_people', 0),
            'total_violations': counts.get('total_violations', 0),
            'total_compliant': counts.get('total_compliant', 0),
            'viewports': counts.get('viewports', {}),
            'yolo_payload': counts.get('yolo_payload', {})
        }
    
    def _handle_low_battery(self):
        """Handle low battery situation"""
        logger.warning(f"Low battery detected: {self.current_battery_level}%")
        
        self.state = PatrolState.LOW_BATTERY
        self._emit_status_update()

        low_battery_url = self.settings.get('low_battery_webview_url') or ''
        if low_battery_url:
            try:
                logger.info(f"[LOW BATTERY] Showing webview: {low_battery_url}")
                self._show_webview_with_autoclose(low_battery_url)
            except Exception as exc:
                logger.error(f"Failed to show low battery webview: {exc}")
        
        if self.low_battery_action == 'stop_immediately':
            # Stop immediately and go to home base
            self.stop_requested = True
            self.mqtt_client.stop_movement()
            time.sleep(1)
            self._return_to_location("low_battery_immediate")
            logger.info("Stopping immediately and returning to base")
            
        elif self.low_battery_action == 'complete_current':
            # Let current waypoint complete, then go to home base
            logger.info(f"Will complete current waypoint then go to home base")
            # The patrol loop will handle this by checking is_low_battery

    def _return_to_location(self, reason: str):
        """Send robot to the configured return location"""
        location = self.return_location or self.home_base_location
        if not location:
            return
        logger.info(f"Returning to location '{location}' (reason: {reason})")
        try:
            self.mqtt_client.goto_waypoint(location)
        except Exception as exc:
            logger.error(f"Failed to return to location '{location}': {exc}")
    
    def _emit_status_update(self):
        """Emit status update"""
        if self.on_status_update:
            status = {
                'robot_id': self.robot_id,
                'state': self.state.value,
                'current_waypoint_index': self.current_waypoint_index,
                'total_waypoints': self.total_waypoints,
                'current_waypoint': self.current_waypoint,
                'current_loop': self.current_loop,
                'total_loops': self.loop_count if not self.is_infinite_loop else -1,
                'is_infinite_loop': self.is_infinite_loop,
                'battery_level': self.current_battery_level,
                'is_low_battery': self.is_low_battery,
                'timestamp': datetime.now().isoformat()
            }
            self.on_status_update(status)
    
    def _emit_complete(self):
        """Emit patrol complete event"""
        if self.on_complete:
            self.on_complete(self.robot_id)
    
    def _emit_error(self, error_message: str):
        """Emit error event"""
        if self.on_error:
            self.on_error(self.robot_id, error_message)


class MultiRobotPatrolManager:
    """Manages patrols for multiple robots"""
    
    def __init__(self, mqtt_manager, settings: Dict):
        self.mqtt_manager = mqtt_manager
        self.settings = settings
        self.patrols: Dict[int, PatrolManager] = {}
        self.lock = threading.Lock()
        
        # Callbacks
        self.on_status_update: Optional[Callable] = None
        self.on_waypoint_reached: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.yolo_state_provider: Optional[Callable[[], Dict[str, Any]]] = None
        self.on_waypoint_summary: Optional[Callable] = None
    
    def set_callbacks(self, on_status_update: Callable = None,
                     on_waypoint_reached: Callable = None,
                     on_complete: Callable = None,
                     on_error: Callable = None,
                     yolo_state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
                     on_waypoint_summary: Optional[Callable] = None):
        """Set callback functions"""
        if on_status_update:
            self.on_status_update = on_status_update
        if on_waypoint_reached:
            self.on_waypoint_reached = on_waypoint_reached
        if on_complete:
            self.on_complete = on_complete
        if on_error:
            self.on_error = on_error
        if yolo_state_provider:
            self.yolo_state_provider = yolo_state_provider
        if on_waypoint_summary:
            self.on_waypoint_summary = on_waypoint_summary
    
    def start_patrol(self, robot_id: int, route: Dict) -> bool:
        """Start patrol for a robot"""
        with self.lock:
            # Check if patrol already running
            if robot_id in self.patrols:
                logger.warning(f"Patrol already running for robot {robot_id}")
                return False
            
            # Get MQTT client
            mqtt_client = self.mqtt_manager.get_robot_client(robot_id)
            if not mqtt_client or not mqtt_client.connected:
                logger.error(f"Robot {robot_id} not connected")
                return False
            
            # Create patrol manager
            patrol = PatrolManager(
                robot_id, mqtt_client, route, self.settings,
                on_status_update=self._on_status_update,
                on_waypoint_reached=self._on_waypoint_reached,
                on_complete=self._on_complete,
                on_error=self._on_error,
                yolo_state_provider=self.yolo_state_provider,
                on_waypoint_summary=self.on_waypoint_summary
            )
            
            # Start patrol
            success = patrol.start()
            
            if success:
                self.patrols[robot_id] = patrol
                return True
            return False
    
    def stop_patrol(self, robot_id: int) -> bool:
        """Stop patrol for a robot"""
        with self.lock:
            patrol = self.patrols.get(robot_id)
            if not patrol:
                return False
            
            success = patrol.stop()
            if success:
                del self.patrols[robot_id]
            return success
    
    def pause_patrol(self, robot_id: int) -> bool:
        """Pause patrol for a robot"""
        patrol = self.patrols.get(robot_id)
        return patrol.pause() if patrol else False
    
    def resume_patrol(self, robot_id: int) -> bool:
        """Resume patrol for a robot"""
        patrol = self.patrols.get(robot_id)
        return patrol.resume() if patrol else False
    
    def set_patrol_speed(self, robot_id: int, speed: float) -> bool:
        """Set patrol speed for a robot"""
        patrol = self.patrols.get(robot_id)
        if patrol:
            patrol.set_speed(speed)
            return True
        return False
    
    def update_battery_level(self, robot_id: int, battery_level: int, is_charging: bool = False):
        """Update battery level for a robot"""
        patrol = self.patrols.get(robot_id)
        if patrol:
            patrol.update_battery_level(battery_level, is_charging)
    
    def on_waypoint_event(self, robot_id: int, event_type: str, location: str, status: str):
        """Handle waypoint event from robot"""
        patrol = self.patrols.get(robot_id)
        if patrol:
            patrol.on_waypoint_event(event_type, location, status)
    
    def get_patrol_status(self, robot_id: int) -> Optional[Dict]:
        """Get patrol status for a robot"""
        patrol = self.patrols.get(robot_id)
        if patrol:
            return {
                'state': patrol.state.value,
                'current_waypoint_index': patrol.current_waypoint_index,
                'total_waypoints': patrol.total_waypoints,
                'current_waypoint': patrol.current_waypoint,
                'current_loop': patrol.current_loop,
                'total_loops': patrol.loop_count if not patrol.is_infinite_loop else -1,
                'is_infinite_loop': patrol.is_infinite_loop,
                'battery_level': patrol.current_battery_level,
                'is_low_battery': patrol.is_low_battery
            }
        return None

    def get_active_patrol_count(self) -> int:
        """Get number of active patrols"""
        return len(self.patrols)
    
    def _on_status_update(self, status: Dict):
        """Internal status update callback"""
        if self.on_status_update:
            self.on_status_update(status)
    
    def _on_waypoint_reached(self, robot_id: int, waypoint_index: int, waypoint: Dict):
        """Internal waypoint reached callback"""
        if self.on_waypoint_reached:
            self.on_waypoint_reached(robot_id, waypoint_index, waypoint)
    
    def _on_complete(self, robot_id: int):
        """Internal patrol complete callback"""
        with self.lock:
            if robot_id in self.patrols:
                del self.patrols[robot_id]
        
        if self.on_complete:
            self.on_complete(robot_id)
    
    def _on_error(self, robot_id: int, error_message: str):
        """Internal error callback"""
        if self.on_error:
            self.on_error(robot_id, error_message)


if __name__ == '__main__':
    # Test patrol manager
    print("Patrol Manager module loaded successfully")

