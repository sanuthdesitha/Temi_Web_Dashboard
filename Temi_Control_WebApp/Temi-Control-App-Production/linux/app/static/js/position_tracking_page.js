/**
 * Position tracking page logic
 */

let selectedRobotId = null;
let currentPosition = null;
let startTime = null;
let tracker = null;

document.addEventListener('DOMContentLoaded', function() {
    const robotSelect = document.getElementById('selectedRobotId');
    const urlParams = new URLSearchParams(window.location.search);
    const initialRobotId = urlParams.get('robot_id');

    tracker = initPositionTracker('positionCanvas');

    if (initialRobotId) {
        robotSelect.value = initialRobotId;
        selectedRobotId = parseInt(initialRobotId, 10);
        loadPositionData();
    }

    robotSelect.addEventListener('change', function() {
        selectedRobotId = this.value ? parseInt(this.value, 10) : null;
        if (selectedRobotId) {
            loadPositionData();
        }
    });

    document.getElementById('requestPositionBtn').addEventListener('click', requestPosition);
    document.getElementById('refreshPositionBtn').addEventListener('click', loadPositionData);
    document.getElementById('exportJsonBtn').addEventListener('click', () => exportPosition('json'));
    document.getElementById('exportCsvBtn').addEventListener('click', () => exportPosition('csv'));
    document.getElementById('clearHistoryBtn').addEventListener('click', clearHistory);
    document.getElementById('uploadMapBtn').addEventListener('click', uploadMapImage);
    document.getElementById('requestMapBtn').addEventListener('click', requestMapImage);

    if (window.socket) {
        socket.on('position_update', function(data) {
            if (data.robot_id === selectedRobotId && data.position) {
                updatePositionDisplay(data.position);
                const tsMs = normalizeTimestamp(data.position.timestamp);
                tracker.updatePosition(data.robot_id, data.position.x, data.position.y, data.position.theta, tsMs);
            }
        });
        socket.on('robot_status', function(data) {
            if (data.robot_id === selectedRobotId && data.waypoint_positions) {
                tracker.setWaypoints(data.robot_id, data.waypoint_positions);
            }
        });
        socket.on('map_image_updated', function(data) {
            if (data.robot_id === selectedRobotId && data.url && tracker) {
                tracker.setBackgroundImage(`${data.url}?t=${Date.now()}`);
                appUtils.showToast('Map image updated from Temi', 'success');
            }
        });
    }
});

function normalizeTimestamp(value) {
    if (!value) return Date.now();
    const n = Number(value);
    return n > 1e12 ? n : n * 1000;
}

function loadPositionData() {
    if (!selectedRobotId) return;

    appUtils.apiCall(`/api/position/current/${selectedRobotId}`).then(response => {
        if (response.success && response.position) {
            currentPosition = response.position;
            startTime = response.position.timestamp;
            updatePositionDisplay(response.position);
            tracker.updatePosition(selectedRobotId, response.position.x, response.position.y, response.position.theta, normalizeTimestamp(response.position.timestamp));
        }
    });

    appUtils.apiCall(`/api/position/trajectory/${selectedRobotId}`).then(response => {
        if (response.success) {
            document.getElementById('totalDistance').textContent = response.distance_traveled.toFixed(2) + ' m';
            document.getElementById('pointCount').textContent = response.point_count + ' points';

            if (startTime && response.point_count > 0) {
                const lastPoint = response.trajectory[response.trajectory.length - 1];
                const duration = lastPoint.timestamp - startTime;
                document.getElementById('activeDuration').textContent = duration.toFixed(0) + ' seconds';
            }

            response.trajectory.forEach(point => {
                tracker.updatePosition(selectedRobotId, point.x, point.y, point.theta, normalizeTimestamp(point.timestamp));
            });

            updateHistoryTable(response.trajectory);
        }
    });

    appUtils.apiCall(`/api/robots/${selectedRobotId}`).then(response => {
        if (response.success && response.robot) {
            const mapUrl = response.robot.map_image_url;
            if (tracker && mapUrl) {
                tracker.setBackgroundImage(mapUrl);
            }
            if (tracker && response.robot.waypoint_positions) {
                tracker.setWaypoints(selectedRobotId, response.robot.waypoint_positions);
            }
        }
    });

    appUtils.apiCall('/api/settings').then(response => {
        if (response.success && response.settings && tracker) {
            const scale = parseFloat(response.settings.map_scale_pixels_per_meter || 50);
            const originX = parseFloat(response.settings.map_origin_x || 0);
            const originY = parseFloat(response.settings.map_origin_y || 0);
            if (!Number.isNaN(scale)) {
                tracker.setManualCalibration(scale, originX, originY);
            }
        }
    });
}

function updatePositionDisplay(position) {
    if (!position) return;
    document.getElementById('posX').textContent = position.x.toFixed(2);
    document.getElementById('posY').textContent = position.y.toFixed(2);
    document.getElementById('posTheta').textContent = position.theta.toFixed(1);
    const datetime = new Date(normalizeTimestamp(position.timestamp)).toLocaleString();
    document.getElementById('posTimestamp').textContent = datetime;
}

function updateHistoryTable(history) {
    const tbody = document.getElementById('historyTableBody');
    if (!history || history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-muted text-center">No position data</td></tr>';
        return;
    }

    const recentHistory = history.slice(-20).reverse();
    tbody.innerHTML = recentHistory.map(point => `
        <tr>
            <td><small>${new Date(normalizeTimestamp(point.timestamp)).toLocaleTimeString()}</small></td>
            <td><code>${point.x.toFixed(2)}</code></td>
            <td><code>${point.y.toFixed(2)}</code></td>
            <td><code>${point.theta.toFixed(1)}&deg;</code></td>
            <td>
                <button class="btn btn-sm btn-outline-secondary" onclick="goToPosition(${point.x}, ${point.y})">
                    <i class="bi bi-arrow-right"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

function requestPosition() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    appUtils.apiCall(`/api/position/request/${selectedRobotId}`, 'POST').then(response => {
        if (response.success) {
            appUtils.showToast('Position request sent', 'success');
            setTimeout(loadPositionData, 1000);
        } else {
            appUtils.showToast('Error: ' + response.error, 'danger');
        }
    });
}

function exportPosition(format) {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    const link = document.createElement('a');
    link.href = `/api/position/export/${selectedRobotId}/${format}`;
    link.download = `position_${selectedRobotId}.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function clearHistory() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    if (!confirm('Clear all position history for this robot?')) return;

    appUtils.apiCall(`/api/position/clear/${selectedRobotId}`, 'POST').then(response => {
        if (response.success) {
            appUtils.showToast('Position history cleared', 'success');
            location.reload();
        } else {
            appUtils.showToast('Error: ' + response.error, 'danger');
        }
    });
}

function uploadMapImage() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }
    const input = document.getElementById('mapUploadInput');
    if (!input || !input.files || !input.files.length) {
        appUtils.showToast('Please select an image file', 'warning');
        return;
    }
    const file = input.files[0];
    const formData = new FormData();
    formData.append('map_image', file);
    fetch(`/api/robots/${selectedRobotId}/upload-map`, {
        method: 'POST',
        body: formData
    }).then(r => r.json()).then(response => {
        if (response.success) {
            appUtils.showToast('Map uploaded', 'success');
            if (tracker && response.url) {
                tracker.setBackgroundImage(response.url);
            }
        } else {
            appUtils.showToast(response.error || 'Failed to upload map', 'danger');
        }
    }).catch(() => {
        appUtils.showToast('Failed to upload map', 'danger');
    });
}

function requestMapImage() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/map-image', 'POST', {
        robot_id: selectedRobotId,
        format: 'png',
        chunk_size: 120000
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Map image requested from Temi', 'info');
        } else {
            appUtils.showToast(response.error || 'Failed to request map image', 'danger');
        }
    }).catch(() => {
        appUtils.showToast('Failed to request map image', 'danger');
    });
}

function goToPosition(x, y) {
    console.log(`Navigate to position: X=${x}, Y=${y}`);
    appUtils.showToast('Navigation to this position not yet implemented', 'info');
}
