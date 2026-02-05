"""
Violation Debouncer Module - Phase 5
Implements intelligent violation filtering and debouncing to reduce false positives
Uses a rolling window with statistical analysis
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque
import statistics
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = 'temi_control.db'


class ViolationDebouncer:
    """
    Intelligent violation debouncer with configurable thresholds.
    Uses rolling window analysis and outlier detection to filter false positives.
    """

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        # In-memory cache for violation state (patrol_id -> deque of violation timestamps)
        self.violation_history: Dict[int, deque] = {}
        # Configuration parameters (can be overridden per patrol)
        self.config = {
            'debounce_window_seconds': 10,  # Rolling window size
            'violation_threshold': 3,  # Minimum violations in window to trigger
            'smoothing_factor': 0.3,  # EMA smoothing for confidence scores
            'outlier_threshold': 3.0,  # Standard deviation threshold for outlier detection
            'min_confidence_score': 0.5,  # Minimum confidence to count violation
        }

    def set_config(self, **kwargs):
        """Update debouncer configuration"""
        self.config.update(kwargs)
        logger.info(f"Violation debouncer config updated: {self.config}")

    def initialize_patrol(self, patrol_id: int):
        """Initialize debouncer state for a new patrol"""
        if patrol_id not in self.violation_history:
            self.violation_history[patrol_id] = deque()
            logger.info(f"Initialized violation debouncer for patrol {patrol_id}")

    def finalize_patrol(self, patrol_id: int):
        """Clean up debouncer state for completed patrol"""
        if patrol_id in self.violation_history:
            del self.violation_history[patrol_id]
            logger.info(f"Finalized violation debouncer for patrol {patrol_id}")

    def add_violation_observation(
        self,
        patrol_id: int,
        waypoint_index: int,
        violation_type: str,
        confidence_score: float = 1.0,
        timestamp: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Add a violation observation and determine if it should be reported.

        Returns:
            Tuple[bool, Optional[str]]: (should_report, debounce_reason)
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.initialize_patrol(patrol_id)

        # Filter out low-confidence observations
        if confidence_score < self.config['min_confidence_score']:
            return False, f"Low confidence: {confidence_score:.2f}"

        # Add to history
        observation = {
            'timestamp': timestamp,
            'confidence': confidence_score,
            'type': violation_type,
            'waypoint': waypoint_index,
        }
        self.violation_history[patrol_id].append(observation)

        # Clean old observations outside window
        window_start = datetime.now() - timedelta(
            seconds=self.config['debounce_window_seconds']
        )
        while (
            self.violation_history[patrol_id]
            and self.violation_history[patrol_id][0]['timestamp'] < window_start
        ):
            self.violation_history[patrol_id].popleft()

        # Analyze violations in window
        window_violations = list(self.violation_history[patrol_id])
        if len(window_violations) == 0:
            return False, "No violations in window"

        # Check for outliers (single isolated spike)
        if len(window_violations) == 1:
            return False, "Single observation, need confirmation"

        # Calculate confidence distribution
        confidences = [v['confidence'] for v in window_violations]
        mean_confidence = statistics.mean(confidences)

        if len(confidences) > 1:
            stdev = statistics.stdev(confidences)
            # Check if current observation is an outlier
            if stdev > 0:
                z_score = (confidence_score - mean_confidence) / stdev
                if abs(z_score) > self.config['outlier_threshold']:
                    return False, f"Outlier detected (z-score: {z_score:.2f})"
        else:
            stdev = 0

        # Count violations in window
        violation_count = len(window_violations)
        threshold = self.config['violation_threshold']

        if violation_count >= threshold:
            # Calculate quality metrics
            confidence_avg = statistics.mean(confidences)
            same_type_count = sum(1 for v in window_violations if v['type'] == violation_type)

            # Log to database
            self._log_debounce_decision(
                patrol_id=patrol_id,
                waypoint_index=waypoint_index,
                violation_count=violation_count,
                mean_confidence=confidence_avg,
                decision='REPORTED',
            )

            logger.info(
                f"Violation debounced for patrol {patrol_id}, waypoint {waypoint_index}: "
                f"{same_type_count}/{violation_count} {violation_type} violations "
                f"(avg confidence: {confidence_avg:.2f})"
            )
            return True, None

        return False, f"Insufficient violations in window ({violation_count}/{threshold})"

    def get_violation_stats(self, patrol_id: int, waypoint_index: int) -> Dict:
        """Get violation statistics for a waypoint"""
        self.initialize_patrol(patrol_id)

        window_violations = list(self.violation_history[patrol_id])
        if not window_violations:
            return {
                'violation_count': 0,
                'mean_confidence': 0.0,
                'std_deviation': 0.0,
                'violation_types': [],
            }

        confidences = [v['confidence'] for v in window_violations]
        violation_types = [v['type'] for v in window_violations]

        mean_conf = statistics.mean(confidences)
        std_dev = statistics.stdev(confidences) if len(confidences) > 1 else 0.0

        return {
            'violation_count': len(window_violations),
            'mean_confidence': mean_conf,
            'std_deviation': std_dev,
            'violation_types': list(set(violation_types)),
            'observation_count': len(window_violations),
        }

    def calculate_confidence_trend(self, patrol_id: int) -> float:
        """
        Calculate EMA (Exponential Moving Average) of confidence scores
        across all violations in current window.
        """
        self.initialize_patrol(patrol_id)

        window_violations = list(self.violation_history[patrol_id])
        if not window_violations:
            return 0.0

        # Simple EMA calculation
        ema = 0.0
        alpha = self.config['smoothing_factor']

        for violation in window_violations:
            ema = (alpha * violation['confidence']) + ((1 - alpha) * ema)

        return ema

    def _log_debounce_decision(
        self,
        patrol_id: int,
        waypoint_index: int,
        violation_count: int,
        mean_confidence: float,
        decision: str,
    ):
        """Log debounce decision to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE violation_debounce_state
                SET violation_count = ?,
                    debounce_triggered = ?,
                    violation_window_end = CURRENT_TIMESTAMP
                WHERE patrol_id = ? AND waypoint_index = ?
            ''', (
                violation_count,
                1 if decision == 'REPORTED' else 0,
                patrol_id,
                waypoint_index,
            ))

            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO violation_debounce_state
                    (patrol_id, waypoint_index, violation_count, violation_window_start,
                     violation_window_end, debounce_triggered)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
                ''', (
                    patrol_id,
                    waypoint_index,
                    violation_count,
                    1 if decision == 'REPORTED' else 0,
                ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging debounce decision: {str(e)}")

    def get_patrol_violation_summary(self, patrol_id: int) -> Dict:
        """Get summary statistics for entire patrol"""
        self.initialize_patrol(patrol_id)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    COUNT(*) as total_observations,
                    SUM(CASE WHEN debounce_triggered = 1 THEN 1 ELSE 0 END) as triggered_count,
                    AVG(violation_count) as avg_violations_per_waypoint
                FROM violation_debounce_state
                WHERE patrol_id = ?
            ''', (patrol_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    'total_observations': row[0] or 0,
                    'triggered_count': row[1] or 0,
                    'avg_violations_per_waypoint': row[2] or 0.0,
                    'effectiveness': (row[1] or 0) / (row[0] or 1) if row[0] else 0.0,
                }
            return {
                'total_observations': 0,
                'triggered_count': 0,
                'avg_violations_per_waypoint': 0.0,
                'effectiveness': 0.0,
            }
        except Exception as e:
            logger.error(f"Error fetching patrol summary: {str(e)}")
            return {}

    def reset_violation_history(self, patrol_id: Optional[int] = None):
        """Reset violation history for patrol or all patrols"""
        if patrol_id:
            if patrol_id in self.violation_history:
                self.violation_history[patrol_id].clear()
                logger.info(f"Reset violation history for patrol {patrol_id}")
        else:
            self.violation_history.clear()
            logger.info("Reset all violation history")


# Global instance
_debouncer_instance: Optional[ViolationDebouncer] = None


def get_debouncer() -> ViolationDebouncer:
    """Get or create global debouncer instance"""
    global _debouncer_instance
    if _debouncer_instance is None:
        _debouncer_instance = ViolationDebouncer()
    return _debouncer_instance


def initialize_debouncer(**config) -> ViolationDebouncer:
    """Initialize debouncer with configuration"""
    debouncer = get_debouncer()
    debouncer.set_config(**config)
    return debouncer
