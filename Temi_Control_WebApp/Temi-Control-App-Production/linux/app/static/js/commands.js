/**
 * Commands page JavaScript
 */

let selectedRobotId = null;
let selectedRobotSerial = null;
let temiCommands = null;
let commandHistory = [];
const COMMAND_HISTORY_KEY = 'temi_command_history';

document.addEventListener('DOMContentLoaded', function() {
    setupEventHandlers();
    checkRobotStatus();
    setInterval(checkRobotStatus, 5000);
    loadCommandHistory();
});

function setupEventHandlers() {
    // Robot selection
    document.getElementById('selectedRobotId').addEventListener('change', function() {
        selectedRobotId = this.value ? parseInt(this.value) : null;

        // Fetch robot serial number for SDK commands
        if (selectedRobotId) {
            appUtils.apiCall(`/api/robots/${selectedRobotId}`).then(response => {
                if (response.success) {
                    selectedRobotSerial = response.robot.serial_number;
                    temiCommands = new TemiSDKCommands(selectedRobotSerial);
                    console.log(`[Commands] Initialized TemiSDKCommands for robot ${selectedRobotSerial}`);
                }
            });
        } else {
            selectedRobotSerial = null;
            temiCommands = null;
        }

        updateRobotStatus();
    });

    // TTS Command
    document.getElementById('sendTtsBtn').addEventListener('click', sendTtsCommand);
    document.querySelectorAll('.quick-tts').forEach(btn => {
        btn.addEventListener('click', function() {
            document.getElementById('ttsUtterance').value = this.dataset.text;
        });
    });

    // WebView Command
    document.getElementById('sendWebviewBtn').addEventListener('click', sendWebviewCommand);
    document.getElementById('closeWebviewBtn').addEventListener('click', sendWebviewCloseCommand);
    document.querySelectorAll('.quick-webview').forEach(btn => {
        btn.addEventListener('click', function() {
            document.getElementById('webviewUrl').value = this.dataset.path;
        });
    });

    // Video Command
    document.getElementById('sendVideoBtn').addEventListener('click', sendVideoCommand);
    document.querySelectorAll('.quick-video').forEach(btn => {
        btn.addEventListener('click', function() {
            document.getElementById('videoUrl').value = this.dataset.path;
        });
    });

    // Movement Commands
    document.getElementById('sendGotoBtn').addEventListener('click', sendGotoCommand);
    document.getElementById('sendHomeBtn').addEventListener('click', sendHomeCommand);
    document.getElementById('sendStopBtn').addEventListener('click', sendStopCommand);

    // Rotation Commands
    document.getElementById('sendRotationBtn').addEventListener('click', sendRotationCommand);
    document.querySelectorAll('.quick-rotation').forEach(btn => {
        btn.addEventListener('click', function() {
            document.getElementById('rotationAngle').value = this.dataset.angle;
        });
    });

    // Tilt Commands
    document.getElementById('sendTiltBtn').addEventListener('click', sendTiltCommand);
    document.querySelectorAll('.quick-tilt').forEach(btn => {
        btn.addEventListener('click', function() {
            document.getElementById('tiltAngle').value = this.dataset.angle;
        });
    });

    // Advanced Commands
    document.getElementById('sendRepositionBtn').addEventListener('click', sendRepositionCommand);
    document.getElementById('sendStatusBtn').addEventListener('click', sendStatusCommand);
    document.getElementById('sendWaypointsBtn').addEventListener('click', sendWaypointsCommand);
    document.getElementById('sendBatteryBtn').addEventListener('click', sendBatteryCommand);
    document.getElementById('sendCustomMqttBtn').addEventListener('click', sendCustomMqttCommand);

    // Position Tester Commands
    document.getElementById('requestPositionBtn').addEventListener('click', requestPosition);
    document.getElementById('viewPositionMapBtn').addEventListener('click', viewPositionMap);
    document.getElementById('exportPositionBtn').addEventListener('click', exportPosition);

    // Socket.IO listeners for real-time position updates
    if (socket) {
        socket.on('position_update', function(data) {
            if (data.robot_id === (selectedRobotId ? parseInt(selectedRobotId) : null)) {
                updatePositionDisplay(data.position);
            }
        });
    }

    // WASD keyboard control
    setupWasdControls();
}

function checkRobotStatus() {
    if (selectedRobotId) {
        appUtils.apiCall(`/api/robots/${selectedRobotId}`).then(response => {
            if (response.success) {
                const robot = response.robot;
                const statusBadge = document.getElementById('robotStatus');
                if (robot.mqtt_connected) {
                    statusBadge.textContent = `Connected - Battery: ${robot.battery_level}%`;
                    statusBadge.className = 'badge bg-success';
                } else {
                    statusBadge.textContent = 'Disconnected';
                    statusBadge.className = 'badge bg-danger';
                }
            }
        });
    }
}

function updateRobotStatus() {
    const statusBadge = document.getElementById('robotStatus');
    if (selectedRobotId) {
        statusBadge.textContent = 'Checking connection...';
        statusBadge.className = 'badge bg-warning';
        checkRobotStatus();
    } else {
        statusBadge.textContent = 'No robot selected';
        statusBadge.className = 'badge bg-secondary';
    }
}

function addCommandToHistory(command, status, details = '') {
    const timestamp = new Date().toLocaleTimeString();
    commandHistory.unshift({ command, status, details, timestamp });

    // Keep only last 50 entries
    if (commandHistory.length > 50) {
        commandHistory = commandHistory.slice(0, 50);
    }

    saveCommandHistory();
    renderCommandHistory();
}

function renderCommandHistory() {
    const historyDiv = document.getElementById('commandHistory');
    if (!historyDiv) return;

    if (commandHistory.length === 0) {
        historyDiv.innerHTML = '<p class="text-muted">No commands sent yet</p>';
        return;
    }

    historyDiv.innerHTML = '';
    commandHistory.forEach(entry => {
        const entryDiv = document.createElement('div');
        entryDiv.className = `command-entry mb-2 p-2 border-start border-3 ${entry.status === 'success' ? 'border-success' : 'border-danger'} bg-light`;
        entryDiv.innerHTML = `
            <div class="d-flex justify-content-between">
                <strong>${entry.command}</strong>
                <small class="text-muted">${entry.timestamp}</small>
            </div>
            ${entry.details ? `<small class="text-muted">${entry.details}</small>` : ''}
            <span class="badge ${entry.status === 'success' ? 'bg-success' : 'bg-danger'} ms-2">${entry.status}</span>
        `;
        historyDiv.appendChild(entryDiv);
    });
}

function saveCommandHistory() {
    try {
        sessionStorage.setItem(COMMAND_HISTORY_KEY, JSON.stringify(commandHistory));
    } catch (e) {
        console.warn('Failed to persist command history', e);
    }
}

function loadCommandHistory() {
    try {
        const raw = sessionStorage.getItem(COMMAND_HISTORY_KEY);
        commandHistory = raw ? JSON.parse(raw) : [];
    } catch (e) {
        commandHistory = [];
    }
    renderCommandHistory();
}

// TTS Command
function sendTtsCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    const utterance = document.getElementById('ttsUtterance').value.trim();
    if (!utterance) {
        appUtils.showToast('Please enter text to speak', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/tts', 'POST', {
        robot_id: selectedRobotId,
        utterance: utterance
    }).then(response => {
        if (response.success) {
            appUtils.showToast('TTS command sent successfully', 'success');
            addCommandToHistory('TTS', 'success', `"${utterance.substring(0, 50)}..."`);
        } else {
            appUtils.showToast('Failed to send TTS command: ' + response.error, 'danger');
            addCommandToHistory('TTS', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('TTS', 'failed', error.message);
    });
}

// WebView Command
function sendWebviewCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    const url = document.getElementById('webviewUrl').value.trim();
    if (!url) {
        appUtils.showToast('Please enter a file path or URL', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/webview', 'POST', {
        robot_id: selectedRobotId,
        url: url
    }).then(response => {
        if (response.success) {
            appUtils.showToast('WebView command sent successfully', 'success');
            addCommandToHistory('WebView', 'success', response.url);
        } else {
            appUtils.showToast('Failed to send WebView command: ' + response.error, 'danger');
            addCommandToHistory('WebView', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('WebView', 'failed', error.message);
    });
}

// WebView Close Command
function sendWebviewCloseCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/webviewclose', 'POST', {
        robot_id: selectedRobotId
    }).then(response => {
        if (response.success) {
            appUtils.showToast('WebView close command sent successfully', 'success');
            addCommandToHistory('WebView Close', 'success');
        } else {
            appUtils.showToast('Failed to close WebView: ' + response.error, 'danger');
            addCommandToHistory('WebView Close', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('WebView Close', 'failed', error.message);
    });
}

// Video Command
function sendVideoCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    const url = document.getElementById('videoUrl').value.trim();
    if (!url) {
        appUtils.showToast('Please enter a file path or URL', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/video', 'POST', {
        robot_id: selectedRobotId,
        url: url
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Video command sent successfully', 'success');
            addCommandToHistory('Video', 'success', response.url);
        } else {
            appUtils.showToast('Failed to send Video command: ' + response.error, 'danger');
            addCommandToHistory('Video', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('Video', 'failed', error.message);
    });
}

// Movement Commands
function sendGotoCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    const location = document.getElementById('gotoLocation').value.trim();
    if (!location) {
        appUtils.showToast('Please enter a waypoint name', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/goto', 'POST', {
        robot_id: selectedRobotId,
        location: location
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Go To command sent successfully', 'success');
            addCommandToHistory('Go To Waypoint', 'success', location);
        } else {
            appUtils.showToast('Failed to send Go To command: ' + response.error, 'danger');
            addCommandToHistory('Go To Waypoint', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('Go To Waypoint', 'failed', error.message);
    });
}

function sendHomeCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/home', 'POST', {
        robot_id: selectedRobotId
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Go To Home command sent successfully', 'success');
            addCommandToHistory('Go To Home', 'success');
        } else {
            appUtils.showToast('Failed to send Go To Home command: ' + response.error, 'danger');
            addCommandToHistory('Go To Home', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('Go To Home', 'failed', error.message);
    });
}

function sendStopCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/stop', 'POST', {
        robot_id: selectedRobotId
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Stop command sent successfully', 'success');
            addCommandToHistory('Stop Movement', 'success');
        } else {
            appUtils.showToast('Failed to send Stop command: ' + response.error, 'danger');
            addCommandToHistory('Stop Movement', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('Stop Movement', 'failed', error.message);
    });
}

// Rotation Command (requires MQTT manager implementation)
function sendRotationCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    const angle = parseInt(document.getElementById('rotationAngle').value, 10);
    if (Number.isNaN(angle)) {
        appUtils.showToast('Please enter a rotation angle', 'warning');
        return;
    }
    if (angle < -360 || angle > 360) {
        appUtils.showToast('Angle must be between -360 and 360', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/turn', 'POST', {
        robot_id: selectedRobotId,
        angle: angle
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Rotation command sent successfully', 'success');
            addCommandToHistory('Rotation', 'success', `${angle}°`);
        } else {
            appUtils.showToast('Failed to send rotation command: ' + response.error, 'danger');
            addCommandToHistory('Rotation', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('Rotation', 'failed', error.message);
    });
}

// Tilt Command
function sendTiltCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    const degrees = parseInt(document.getElementById('tiltAngle').value, 10);
    if (Number.isNaN(degrees)) {
        appUtils.showToast('Please enter a tilt angle', 'warning');
        return;
    }
    if (degrees < -25 || degrees > 60) {
        appUtils.showToast('Tilt must be between -25 and 60', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/tilt', 'POST', {
        robot_id: selectedRobotId,
        degrees: degrees
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Tilt command sent successfully', 'success');
            addCommandToHistory('Tilt', 'success', `${degrees}°`);
        } else {
            appUtils.showToast('Failed to send tilt command: ' + response.error, 'danger');
            addCommandToHistory('Tilt', 'failed', response.error);
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('Tilt', 'failed', error.message);
    });
}

// WASD Controls
function setupWasdControls() {
    const enableSwitch = document.getElementById('wasdControlEnabled');
    if (!enableSwitch) return;

    let wasdEnabled = false;
    let moveSpeed = 0.5;
    let turnSpeed = 0.5;
    let pressedKeys = new Set();
    let wasdInterval = null;
    let lastSentZero = true;

    const moveSpeedEl = document.getElementById('moveSpeed');
    const turnSpeedEl = document.getElementById('turnSpeed');
    const moveSpeedValue = document.getElementById('moveSpeedValue');
    const turnSpeedValue = document.getElementById('turnSpeedValue');

    enableSwitch.addEventListener('change', function() {
        wasdEnabled = this.checked;
        if (wasdEnabled && !selectedRobotId) {
            appUtils.showToast('Please select a robot first', 'warning');
            this.checked = false;
            wasdEnabled = false;
        }
        if (wasdEnabled) {
            startWASDLoop();
        } else {
            stopWASDLoop();
        }
    });

    if (moveSpeedEl) {
        moveSpeedEl.addEventListener('input', function() {
            moveSpeed = parseFloat(this.value);
            if (moveSpeedValue) moveSpeedValue.textContent = moveSpeed.toFixed(1);
        });
    }

    if (turnSpeedEl) {
        turnSpeedEl.addEventListener('input', function() {
            turnSpeed = parseFloat(this.value);
            if (turnSpeedValue) turnSpeedValue.textContent = turnSpeed.toFixed(1);
        });
    }

    document.addEventListener('keydown', function(e) {
        if (!wasdEnabled) return;

        const key = e.key.toLowerCase();
        if (['w', 'a', 's', 'd', 'q', 'e', ' '].includes(key)) {
            e.preventDefault();
        }

        if (!pressedKeys.has(key)) {
            pressedKeys.add(key);
            highlightKey(key, true);
        }
    });

    document.addEventListener('keyup', function(e) {
        if (!wasdEnabled) return;

        const key = e.key.toLowerCase();
        pressedKeys.delete(key);
        highlightKey(key, false);
    });

    function startWASDLoop() {
        if (wasdInterval) return;
        wasdInterval = setInterval(() => {
            if (!wasdEnabled || !selectedRobotId) return;
            sendJoystickCommand();
        }, 100);
    }

    function stopWASDLoop() {
        if (wasdInterval) {
            clearInterval(wasdInterval);
            wasdInterval = null;
        }
        lastSentZero = true;
    }

    function highlightKey(key, active) {
        const keyMap = {
            'w': '#key-w',
            'a': '#key-a',
            's': '#key-s',
            'd': '#key-d',
            'q': '#key-q',
            'e': '#key-e',
            ' ': '#key-space'
        };

        const selector = keyMap[key];
        if (selector) {
            const el = document.querySelector(selector);
            if (el) {
                if (active) {
                    el.classList.add('active');
                } else {
                    el.classList.remove('active');
                }
            }
        }
    }

    function sendJoystickCommand() {
        if (!selectedRobotId) return;

        let x = 0, y = 0, theta = 0;
        if (pressedKeys.has(' ')) {
            appUtils.apiCall('/api/command/stop', 'POST', { robot_id: selectedRobotId });
            return;
        }

        // Forward/Backward: x controls movement
        if (pressedKeys.has('w')) x += moveSpeed;      // Forward
        if (pressedKeys.has('s')) x -= moveSpeed;      // Backward

        // Turning: y controls left/right turning (A and D - switched)
        if (pressedKeys.has('d')) y -= turnSpeed;      // Turn left
        if (pressedKeys.has('a')) y += turnSpeed;      // Turn right

        // Rotation: theta controls rotation (Q and E)
        if (pressedKeys.has('q')) theta -= turnSpeed;  // Rotate left
        if (pressedKeys.has('e')) theta += turnSpeed;  // Rotate right

        const isZero = x === 0 && y === 0 && theta === 0;
        if (isZero && lastSentZero) return;
        lastSentZero = isZero;

        appUtils.apiCall('/api/command/joystick', 'POST', {
            robot_id: selectedRobotId,
            x: x,
            y: y,
            theta: theta
        });
    }
}

// Advanced Commands
function sendRepositionCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    appUtils.showToast('Reposition request sent - check logs for response', 'info');
    addCommandToHistory('Request Position', 'sent');
}

function sendStatusCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    if (!temiCommands) {
        appUtils.showToast('Initializing SDK commands...', 'warning');
        return;
    }

    appUtils.showToast('Requesting robot status from SDK...', 'info');

    // Request both battery and ready status
    Promise.all([
        temiCommands.getBattery().catch(e => ({ error: e.message })),
        temiCommands.isReady().catch(e => ({ error: e.message }))
    ]).then(([batteryResponse, readyResponse]) => {
        console.log('[Commands] Status responses:', { batteryResponse, readyResponse });

        const statusParts = [];
        if (batteryResponse && batteryResponse.success) {
            statusParts.push('Battery check sent');
        }
        if (readyResponse && readyResponse.success) {
            statusParts.push('Ready status sent');
        }

        if (statusParts.length > 0) {
            const statusMsg = statusParts.join(', ') + ' - check MQTT monitor for responses';
            appUtils.showToast(statusMsg, 'success');
            addCommandToHistory('Request Status (SDK)', 'success', statusMsg);
        } else {
            appUtils.showToast('Failed to request robot status', 'danger');
            addCommandToHistory('Request Status (SDK)', 'failed', 'No responses');
        }
    }).catch(error => {
        console.error('[Commands] Status error:', error);
        appUtils.showToast('Error requesting status: ' + error.message, 'danger');
        addCommandToHistory('Request Status (SDK)', 'failed', error.message);
    });
}

function sendWaypointsCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    appUtils.apiCall('/api/command/waypoints', 'POST', { robot_id: selectedRobotId }).then(response => {
        if (response.success) {
            appUtils.showToast('Waypoint request sent - check logs for response', 'info');
            addCommandToHistory('Request Waypoints', 'success', 'Requested');
        } else {
            appUtils.showToast('Failed to request waypoints', 'danger');
            addCommandToHistory('Request Waypoints', 'failed');
        }
    });
}

function sendBatteryCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    if (!temiCommands) {
        appUtils.showToast('Initializing SDK commands...', 'warning');
        return;
    }

    appUtils.showToast('Requesting battery info from robot...', 'info');

    temiCommands.getBattery().then(response => {
        console.log('[Commands] Battery response:', response);
        if (response && response.success) {
            const batteryInfo = response.topic
                ? `Battery level requested - check MQTT monitor for response`
                : `Battery info received`;
            appUtils.showToast(batteryInfo, 'success');
            addCommandToHistory('Request Battery (SDK)', 'success', batteryInfo);
        } else {
            appUtils.showToast('Failed to request battery info', 'danger');
            addCommandToHistory('Request Battery (SDK)', 'failed', response?.error || 'Unknown error');
        }
    }).catch(error => {
        console.error('[Commands] Battery error:', error);
        appUtils.showToast('Error requesting battery: ' + error.message, 'danger');
        addCommandToHistory('Request Battery (SDK)', 'failed', error.message);
    });
}

function sendCustomMqttCommand() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    const topic = document.getElementById('customTopic').value.trim();
    const payloadRaw = document.getElementById('customPayload').value.trim();

    if (!topic) {
        appUtils.showToast('Please enter a topic', 'warning');
        return;
    }

    let payload = {};
    if (payloadRaw) {
        try {
            payload = JSON.parse(payloadRaw);
        } catch (e) {
            appUtils.showToast('Payload must be valid JSON', 'danger');
            return;
        }
    }

    appUtils.apiCall('/api/command/custom', 'POST', {
        robot_id: selectedRobotId,
        topic,
        payload
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Custom MQTT sent', 'success');
            addCommandToHistory('Custom MQTT', 'success', topic);
        } else {
            appUtils.showToast('Failed to send custom MQTT: ' + response.error, 'danger');
            addCommandToHistory('Custom MQTT', 'failed', response.error || 'Failed');
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('Custom MQTT', 'failed', error.message);
    });
}

/**
 * Position Tester Functions
 */

function requestPosition() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    appUtils.apiCall(`/api/position/request/${selectedRobotId}`, 'POST').then(response => {
        if (response.success) {
            appUtils.showToast('Position request sent to robot', 'success');
            addCommandToHistory('Request Position', 'success');
        } else {
            appUtils.showToast('Failed to request position: ' + response.error, 'danger');
            addCommandToHistory('Request Position', 'failed');
        }
    }).catch(error => {
        appUtils.showToast('Error: ' + error.message, 'danger');
        addCommandToHistory('Request Position', 'failed');
    });
}

function viewPositionMap() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    // Navigate to position tracking page
    window.location.href = `/position-tracking?robot_id=${selectedRobotId}`;
}

function exportPosition() {
    if (!selectedRobotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }

    // Create a dropdown for format selection
    const formats = ['json', 'csv'];
    let html = '<div class="btn-group" role="group">';
    formats.forEach(format => {
        html += `<button type="button" class="btn btn-sm btn-outline-success export-format" data-format="${format}">${format.toUpperCase()}</button>`;
    });
    html += '</div>';

    // Show modal with format selection
    const modalBody = document.createElement('div');
    modalBody.innerHTML = `
        <p>Select export format:</p>
        ${html}
    `;

    // Simple approach: let them download JSON by default
    const downloadLink = document.createElement('a');
    downloadLink.href = `/api/position/export/${selectedRobotId}/json`;
    downloadLink.download = `position_${selectedRobotId}.json`;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);

    appUtils.showToast('Exporting position data...', 'info');
    addCommandToHistory('Export Position', 'success');
}

function updatePositionDisplay(position) {
    const infoDiv = document.getElementById('currentPositionInfo');
    if (position) {
        const ts = normalizeTimestamp(position.timestamp);
        const datetime = new Date(ts).toLocaleString();
        infoDiv.innerHTML = `
            <strong>Current Position:</strong><br/>
            X: <span class="badge bg-info">${Number(position.x || 0).toFixed(2)}m</span>
            Y: <span class="badge bg-info">${Number(position.y || 0).toFixed(2)}m</span>
            Theta: <span class="badge bg-info">${Number(position.theta || 0).toFixed(1)}&deg;</span>
            <br/><small class="text-muted">${datetime}</small>
        `;
    }
}

function normalizeTimestamp(value) {
    if (!value) return Date.now();
    const n = Number(value);
    return n > 1e12 ? n : n * 1000;
}
