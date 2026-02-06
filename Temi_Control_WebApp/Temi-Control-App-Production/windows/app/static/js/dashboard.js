/**
 * Dashboard page JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Load initial data
    loadDashboardData();
    initPositionPreview();

    // Setup real-time Socket.IO listeners
    if (window.socket) {
        socket.on('battery_update', function(data) {
            console.log('[Dashboard] Battery update:', data);
            updateDashboardStatsFromApi();
        });

        socket.on('robot_status', function(data) {
            console.log('[Dashboard] Robot status:', data);
            updateDashboardStatsFromApi();
        });

        socket.on('waypoint_event', function(data) {
            console.log('[Dashboard] Waypoint event:', data);
            updateDashboardStatsFromApi();
        });

        socket.on('robot_connected', function(data) {
            console.log('[Dashboard] Robot connected:', data);
            updateDashboardStatsFromApi();
        });

        socket.on('robot_disconnected', function(data) {
            console.log('[Dashboard] Robot disconnected:', data);
            updateDashboardStatsFromApi();
        });

        socket.on('position_update', function(data) {
            if (data && data.position) {
                updatePositionPreviewFromSocket(data);
            }
        });

        socket.on('yolo_summary', function(data) {
            const countEl = document.getElementById('active-violations');
            if (countEl) {
                countEl.textContent = data.total_violations || 0;
            }
        });

        socket.on('patrol_count_update', function(data) {
            const el = document.getElementById('active-patrols');
            if (el && data && typeof data.count !== 'undefined') {
                el.textContent = data.count;
            }
        });
    }

    verifySocketConnection();

    // Fallback polling every 8 seconds
    setInterval(loadDashboardData, 8000);

    // Setup event handlers
    setupEventHandlers();

    initPositionPreviewControls();
});

function verifySocketConnection() {
    if (window.socket) {
        console.log('[Dashboard] Socket.IO Status:');
        console.log('  - Connected:', window.socket.connected);
        console.log('  - Socket ID:', window.socket.id);
        console.log('  - Namespace:', window.socket.nsp);

        if (!window.socket.connected) {
            console.warn('[Dashboard] Socket.IO NOT connected!');
            console.warn('[Dashboard] Updates will be slow (polling only)');
        } else {
            console.log('[Dashboard] Real-time updates enabled');
        }
    } else {
        console.error('[Dashboard] Socket.IO not loaded!');
    }
}

function setupEventHandlers() {
function initPositionPreviewControls() {
    const toggle = document.getElementById('dashboardPositionToggle');
    const select = document.getElementById('dashboardPositionRobot');

    if (toggle) {
        const saved = localStorage.getItem('dashboard_position_enabled');
        if (saved !== null) toggle.checked = saved === 'true';
        toggle.addEventListener('change', () => {
            localStorage.setItem('dashboard_position_enabled', toggle.checked ? 'true' : 'false');
            if (!toggle.checked) {
                clearPositionPreview();
            } else {
                schedulePositionPreviewLoad(true);
            }
        });
    }

    if (select) {
        const savedRobot = localStorage.getItem('dashboard_position_robot');
        if (savedRobot) select.value = savedRobot;
        select.addEventListener('change', () => {
            localStorage.setItem('dashboard_position_robot', select.value || '');
            schedulePositionPreviewLoad(true);
        });
    }
}


    // WebView button click
    document.addEventListener('click', function(e) {
        if (e.target.closest('.btn-webview')) {
            const btn = e.target.closest('.btn-webview');
            const robotId = btn.dataset.robotId;
            showWebViewModal(robotId);
        }

        // Quick path buttons
        if (e.target.closest('.quick-path')) {
            const btn = e.target.closest('.quick-path');
            const path = btn.dataset.path;
            document.getElementById('webviewUrl').value = path;
        }
    });

    // Send WebView button
    const sendBtn = document.getElementById('sendWebviewBtn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendWebViewCommand);
    }
}

function loadDashboardData() {
    // Load robots data
    appUtils.apiCall('/api/robots').then(response => {
        if (response.success) {
            updateDashboardStats(response.robots);
        }
    });

    appUtils.apiCall('/api/patrol/active-count').then(response => {
        if (response.success) {
            const el = document.getElementById('active-patrols');
            if (el) el.textContent = response.count;
        }
    });

    // Load recent activity
    appUtils.apiCall('/api/logs?limit=10').then(response => {
        if (response.success) {
            updateRecentActivity(response.logs);
        }
    });

    schedulePositionPreviewLoad();
}

function updateDashboardStatsFromApi() {
    loadDashboardData();
}

function updateDashboardStats(robots) {
    const totalRobots = robots.length;
    const connectedRobots = robots.filter(r => r.mqtt_connected).length;
    const lowBatteryRobots = robots.filter(r => r.battery_level <= 10).length;

    document.getElementById('total-robots').textContent = totalRobots;
    document.getElementById('connected-robots').textContent = connectedRobots;
    document.getElementById('low-battery-robots').textContent = lowBatteryRobots;

    // Update robot cards
    robots.forEach(robot => {
        appUtils.updateRobotConnectionStatus(robot.id, robot.mqtt_connected);
        appUtils.updateRobotBattery(robot.id, robot.battery_level, robot.is_charging);

        // Update location
        const robotCard = document.querySelector(`[data-robot-id="${robot.id}"]`);
        if (robotCard) {
            const locationSpan = robotCard.querySelector('.current-location');
            if (locationSpan) {
                locationSpan.textContent = robot.current_location || 'Unknown';
            }
        }
    });
}

function updateRecentActivity(logs) {
    const activityLog = document.getElementById('recent-activity');
    if (!activityLog) return;

    activityLog.innerHTML = '';

    logs.forEach(log => {
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${log.level}`;
        logEntry.innerHTML = `
            <small class="text-muted">${log.created_at}</small>
            <span class="badge bg-${getLevelBadgeClass(log.level)} ms-2">${log.level}</span>
            <span class="ms-2">${log.message}</span>
        `;
        activityLog.appendChild(logEntry);
    });
}

function getLevelBadgeClass(level) {
    const classes = {
        'info': 'info',
        'warning': 'warning',
        'error': 'danger'
    };
    return classes[level] || 'secondary';
}

function showWebViewModal(robotId) {
    // Set robot ID in hidden field
    document.getElementById('webviewRobotId').value = robotId;

    // Clear the form
    document.getElementById('webviewUrl').value = '';

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('webviewModal'));
    modal.show();
}

function sendWebViewCommand() {
    const robotId = document.getElementById('webviewRobotId').value;
    const url = document.getElementById('webviewUrl').value.trim();

    if (!url) {
        appUtils.showToast('Please enter a file path or URL', 'warning');
        return;
    }

    // Send the command
    appUtils.apiCall('/api/command/webview', 'POST', {
        robot_id: parseInt(robotId),
        url: url
    }).then(response => {
        if (response.success) {
            appUtils.showToast(`WebView command sent: ${response.url}`, 'success');
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('webviewModal'));
            modal.hide();
        } else {
            appUtils.showToast('Failed to send WebView command: ' + (response.error || 'Unknown error'), 'danger');
        }
    }).catch(error => {
        appUtils.showToast('Error sending WebView command: ' + error.message, 'danger');
    });
}

let dashboardTracker = null;
let lastPositionPreviewLoad = 0;
let positionPreviewTimer = null;
const POSITION_PREVIEW_MIN_INTERVAL_MS = 10000;
const POSITION_PREVIEW_MAX_ITEMS = 5;

function initPositionPreview() {
    if (typeof initPositionTracker === 'function') {
        dashboardTracker = initPositionTracker('dashboardPositionCanvas');
    }
}

function schedulePositionPreviewLoad(force = false) {
    const now = Date.now();
    if (!force && (now - lastPositionPreviewLoad) < POSITION_PREVIEW_MIN_INTERVAL_MS) {
        if (!positionPreviewTimer) {
            const delay = POSITION_PREVIEW_MIN_INTERVAL_MS - (now - lastPositionPreviewLoad);
            positionPreviewTimer = setTimeout(() => {
                positionPreviewTimer = null;
                loadPositionPreview();
            }, delay);
        }
        return;
    }
    loadPositionPreview();
}

function loadPositionPreview() {
    const list = document.getElementById('dashboardPositionList');
    const toggle = document.getElementById('dashboardPositionToggle');
    if (!list) return;

    if (toggle && !toggle.checked) {
        clearPositionPreview();
        return;
    }

    const select = document.getElementById('dashboardPositionRobot');
    const robotId = select && select.value ? parseInt(select.value, 10) : null;

    if (robotId) {
        appUtils.apiCall(`/api/position/current/${robotId}`).then(res => {
            if (res.success && res.position) {
                lastPositionPreviewLoad = Date.now();
                renderPositionPreview([Object.assign({robot_id: robotId}, res.position)]);
            } else {
                renderPositionPreview([]);
            }
        });
        return;
    }

    appUtils.apiCall('/api/position/all').then(res => {
        if (res.success) {
            lastPositionPreviewLoad = Date.now();
            renderPositionPreview(res.positions || []);
        }
    });
}

function clearPositionPreview() {
    const list = document.getElementById('dashboardPositionList');
    if (list) list.innerHTML = '<div class="text-muted">Position preview disabled</div>';
    if (dashboardTracker && typeof dashboardTracker.clear === 'function') {
        dashboardTracker.clear();
    }
}

function renderPositionPreview(positions) {
    const list = document.getElementById('dashboardPositionList');
    if (!list) return;

    if (!positions.length) {
        list.innerHTML = '<div class="text-muted">No position data yet</div>';
        return;
    }

    const subset = positions.slice(0, POSITION_PREVIEW_MAX_ITEMS);
    list.innerHTML = subset.map(p => `
        <div class="list-group-item d-flex justify-content-between align-items-center">
            <span>Robot ${p.robot_id}</span>
            <span class="text-muted">X ${Number(p.x || 0).toFixed(2)} | Y ${Number(p.y || 0).toFixed(2)} | theta ${Number(p.theta || 0).toFixed(1)}</span>
        </div>
    `).join('');

    if (dashboardTracker) {
        subset.forEach(p => {
            const tsMs = normalizeTimestamp(p.timestamp);
            dashboardTracker.updatePosition(
                p.robot_id,
                Number(p.x || 0),
                Number(p.y || 0),
                Number(p.theta || 0),
                tsMs
            );
        });
    }

    if (positions.length > POSITION_PREVIEW_MAX_ITEMS) {
        const more = document.createElement('div');
        more.className = 'list-group-item text-muted';
        more.textContent = `+ ${positions.length - POSITION_PREVIEW_MAX_ITEMS} more...`;
        list.appendChild(more);
    }
}

function updatePositionPreviewFromSocket(data) {
    if (!data || !data.position) return;
    const list = document.getElementById('dashboardPositionList');
    if (!list) return;

    const toggle = document.getElementById('dashboardPositionToggle');
    if (toggle && !toggle.checked) return;

    const select = document.getElementById('dashboardPositionRobot');
    if (select && select.value) {
        const selectedId = parseInt(select.value, 10);
        if (data.robot_id !== selectedId) return;
    }

    if (dashboardTracker) {
        const tsMs = normalizeTimestamp(data.position.timestamp);
        dashboardTracker.updatePosition(
            data.robot_id,
            Number(data.position.x || 0),
            Number(data.position.y || 0),
            Number(data.position.theta || 0),
            tsMs
        );
    }

    // Refresh list view periodically (throttled)
    schedulePositionPreviewLoad();
}

function normalizeTimestamp(value) {
    if (!value) return Date.now();
    const n = Number(value);
    return n > 1e12 ? n : n * 1000;
}

// ============================================================================
// MQTT Connection Status Functions
// ============================================================================

function loadMqttStatus() {
    // Load and display MQTT connection status
    appUtils.apiCall('/api/mqtt/status').then(response => {
        if (response.success) {
            updateMqttStatusDisplay(response.status);
        }
    }).catch(error => {
        console.error('Error loading MQTT status:', error);
        updateMqttStatusError('Failed to load MQTT status');
    });
}

function updateMqttStatusDisplay(status) {
    // Update cloud broker status
    const cloudBroker = status.cloud_broker;
    const cloudIcon = document.getElementById('cloudBrokerIcon');
    const cloudStatus = document.getElementById('cloudBrokerStatus');
    const cloudInfo = document.getElementById('cloudBrokerInfo');

    if (cloudBroker && cloudBroker.connected) {
        cloudIcon.className = 'badge bg-success';
        cloudIcon.innerHTML = '<i class="bi bi-check-circle-fill"></i> Connected';
        cloudStatus.textContent = 'Connected';
        cloudStatus.className = 'text-success';
        cloudInfo.innerHTML = `${cloudBroker.broker}:${cloudBroker.port}`;
    } else {
        cloudIcon.className = 'badge bg-danger';
        cloudIcon.innerHTML = '<i class="bi bi-x-circle-fill"></i> Disconnected';
        cloudStatus.textContent = 'Disconnected';
        cloudStatus.className = 'text-danger';
        cloudInfo.innerHTML = cloudBroker.broker ? `${cloudBroker.broker}:${cloudBroker.port}` : 'Not configured';
    }

    // Update robot MQTT status
    const robotList = document.getElementById('robotMqttList');
    if (robotList && status.robots && Object.keys(status.robots).length > 0) {
        robotList.innerHTML = '';

        Object.values(status.robots).forEach(robot => {
            const badgeClass = robot.connected ? 'bg-success' : 'bg-danger';
            const statusIcon = robot.connected ? 'check-circle-fill' : 'x-circle-fill';
            const statusText = robot.connected ? 'Connected' : 'Disconnected';

            const item = document.createElement('div');
            item.className = 'list-group-item d-flex justify-content-between align-items-center';
            item.innerHTML = `
                <span>
                    <strong>${robot.name}</strong>
                    <small class="text-muted d-block">${robot.broker}</small>
                </span>
                <span class="badge ${badgeClass}">
                    <i class="bi bi-${statusIcon}"></i> ${statusText}
                </span>
            `;
            robotList.appendChild(item);
        });
    } else {
        robotList.innerHTML = '<div class="text-muted">No robots configured</div>';
    }
}

function updateMqttStatusError(errorMsg) {
    const cloudIcon = document.getElementById('cloudBrokerIcon');
    const cloudStatus = document.getElementById('cloudBrokerStatus');
    const cloudInfo = document.getElementById('cloudBrokerInfo');

    cloudIcon.className = 'badge bg-warning';
    cloudIcon.innerHTML = '<i class="bi bi-exclamation-circle-fill"></i>';
    cloudStatus.textContent = 'Error checking status';
    cloudStatus.className = 'text-warning';
    cloudInfo.textContent = errorMsg;
}

function testMqttConnection() {
    const btn = document.getElementById('testMqttBtn');
    if (!btn) return;

    // Show loading state
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Testing...';
    btn.disabled = true;

    appUtils.apiCall('/api/mqtt/test', 'POST', {}).then(response => {
        if (response.success) {
            toastr.success('✅ ' + response.message, 'MQTT Connection Test');
            loadMqttStatus(); // Refresh status
        } else {
            toastr.error('❌ ' + (response.error || 'Connection test failed'), 'MQTT Connection Test');
        }
    }).catch(error => {
        console.error('MQTT test error:', error);
        toastr.error('❌ Error testing MQTT connection', 'MQTT Connection Test');
    }).finally(() => {
        // Restore button state
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    });
}

// Setup MQTT status handlers on page load
document.addEventListener('DOMContentLoaded', function() {
    // Load MQTT status on page load
    loadMqttStatus();

    // Refresh MQTT status every 15 seconds
    setInterval(loadMqttStatus, 15000);

    // Setup test button
    const testBtn = document.getElementById('testMqttBtn');
    if (testBtn) {
        testBtn.addEventListener('click', testMqttConnection);
    }
}, { once: true });
