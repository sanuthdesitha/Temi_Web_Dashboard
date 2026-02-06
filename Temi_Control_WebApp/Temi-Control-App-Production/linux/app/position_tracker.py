"""
Position Tracking Module for Temi Control Application

Handles real-time position updates from robots and maintains position history
for visualization, analytics, and route planning.
"""

import json
import logging
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks robot positions and maintains history for visualization"""

    def __init__(self, max_history_per_robot: int = 500):
        """
        Initialize position tracker

        Args:
            max_history_per_robot: Maximum position points to keep per robot
        """
        self.max_history = max_history_per_robot
        self.positions: Dict[int, Dict] = {}  # robot_id -> current position
        self.history: Dict[int, List[Dict]] = {}  # robot_id -> list of positions
        self.lock = Lock()

    def update_position(self, robot_id: int, x: float, y: float, theta: float,
                       timestamp: Optional[float] = None) -> Dict:
        """
        Update robot position

        Args:
            robot_id: Robot ID
            x: X coordinate
            y: Y coordinate
            theta: Heading angle in degrees
            timestamp: Unix timestamp (uses current time if not provided)

        Returns:
            Position data dict
        """
        if timestamp is None:
            timestamp = datetime.now().timestamp()
        else:
            try:
                timestamp = float(timestamp)
            except (TypeError, ValueError):
                timestamp = datetime.now().timestamp()

        # Normalize millisecond timestamps to seconds
        if timestamp > 1e11:
            timestamp = timestamp / 1000.0

        position_data = {
            'robot_id': robot_id,
            'x': float(x),
            'y': float(y),
            'theta': float(theta),
            'timestamp': timestamp,
            'datetime': datetime.fromtimestamp(timestamp).isoformat()
        }

        with self.lock:
            # Update current position
            self.positions[robot_id] = position_data

            # Add to history
            if robot_id not in self.history:
                self.history[robot_id] = []

            self.history[robot_id].append(position_data)

            # Trim history if it exceeds max
            if len(self.history[robot_id]) > self.max_history:
                self.history[robot_id] = self.history[robot_id][-self.max_history:]

        return position_data

    def get_current_position(self, robot_id: int) -> Optional[Dict]:
        """Get current position for a robot"""
        with self.lock:
            return self.positions.get(robot_id)

    def get_position_history(self, robot_id: int, limit: Optional[int] = None) -> List[Dict]:
        """
        Get position history for a robot

        Args:
            robot_id: Robot ID
            limit: Maximum number of points to return (None = all)

        Returns:
            List of position dicts
        """
        with self.lock:
            history = self.history.get(robot_id, [])
            if limit:
                return history[-limit:]
            return list(history)

    def get_position_history_since(self, robot_id: int, timestamp: float) -> List[Dict]:
        """
        Get position history since a specific timestamp

        Args:
            robot_id: Robot ID
            timestamp: Unix timestamp (seconds)

        Returns:
            List of position dicts
        """
        with self.lock:
            history = self.history.get(robot_id, [])
            return [p for p in history if p['timestamp'] >= timestamp]

    def get_all_positions(self) -> Dict[int, Dict]:
        """Get current positions for all robots"""
        with self.lock:
            return dict(self.positions)

    def get_all_current_positions(self) -> List[Dict]:
        """Get list of current positions for all robots"""
        with self.lock:
            return list(self.positions.values())

    def get_trajectory(self, robot_id: int, limit: Optional[int] = None) -> List[Tuple[float, float]]:
        """
        Get trajectory (X, Y coordinates) for a robot

        Args:
            robot_id: Robot ID
            limit: Maximum number of points (None = all)

        Returns:
            List of (x, y) tuples
        """
        history = self.get_position_history(robot_id, limit)
        return [(p['x'], p['y']) for p in history]

    def calculate_distance_traveled(self, robot_id: int) -> float:
        """
        Calculate total distance traveled by robot based on position history

        Args:
            robot_id: Robot ID

        Returns:
            Distance in meters
        """
        trajectory = self.get_trajectory(robot_id)

        if len(trajectory) < 2:
            return 0.0

        total_distance = 0.0
        for i in range(1, len(trajectory)):
            x1, y1 = trajectory[i - 1]
            x2, y2 = trajectory[i]

            # Euclidean distance
            dx = x2 - x1
            dy = y2 - y1
            distance = (dx**2 + dy**2) ** 0.5
            total_distance += distance

        return total_distance

    def clear_history(self, robot_id: int):
        """Clear position history for a robot"""
        with self.lock:
            if robot_id in self.history:
                self.history[robot_id] = []

    def clear_all(self):
        """Clear all positions and history"""
        with self.lock:
            self.positions.clear()
            self.history.clear()

    def export_trajectory_as_json(self, robot_id: int) -> str:
        """
        Export trajectory as JSON for download/sharing

        Args:
            robot_id: Robot ID

        Returns:
            JSON string
        """
        trajectory_data = {
            'robot_id': robot_id,
            'exported_at': datetime.now().isoformat(),
            'points': self.get_position_history(robot_id),
            'total_distance': self.calculate_distance_traveled(robot_id)
        }

        return json.dumps(trajectory_data, indent=2)

    def export_trajectory_as_csv(self, robot_id: int) -> str:
        """
        Export trajectory as CSV for analysis

        Args:
            robot_id: Robot ID

        Returns:
            CSV string
        """
        history = self.get_position_history(robot_id)

        if not history:
            return "robot_id,x,y,theta,timestamp,datetime\n"

        lines = ["robot_id,x,y,theta,timestamp,datetime"]
        for point in history:
            line = f"{point['robot_id']},{point['x']},{point['y']},{point['theta']},{point['timestamp']},{point['datetime']}"
            lines.append(line)

        return '\n'.join(lines)


# Global position tracker instance
position_tracker = PositionTracker()
