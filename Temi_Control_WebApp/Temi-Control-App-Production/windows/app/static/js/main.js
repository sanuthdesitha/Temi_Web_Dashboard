/**
 * Main JavaScript file for Temi Control Application
 * Handles WebSocket connection and global functionality
 */

// Initialize Socket.IO connection (guard if CDN failed)
const socket = window.io ? io() : null;
if (socket) {
    window.socket = socket;
}

// Global state
const appState = {
    robots: {},
    connected: false,
    patrol: {
        activeRobotId: null,
        activeRouteId: null,
        minimized: false
    },
    yolo: {
        total_violations: 0,
        total_people: 0,
        viewports: { front: 0, right: 0, back: 0, left: 0 }
    }
};

function normalizeStreamUrl(url) {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    return `http://${url}`;
}

function ensureStreamPath(url) {
    try {
        const parsed = new URL(url);
        if (parsed.pathname === '/' || parsed.pathname === '') {
            parsed.pathname = '/stream';
            return parsed.toString();
        }
        return url;
    } catch (e) {
        if (url.endsWith('/')) return `${url}stream`;
        return url;
    }
}

function loadStreamUrl() {
    const img = document.getElementById('patrolStreamImg');
    if (!img) return;

    apiCall('/api/settings')
        .then(response => {
            if (!response.success || !response.settings) return;
            const url = ensureStreamPath(
                normalizeStreamUrl(response.settings.yolo_stream_url || 'http://192.168.18.135:8080')
            );
            if (url) {
                const proxyUrl = `/api/stream?url=${encodeURIComponent(url)}`;
                const separator = proxyUrl.includes('?') ? '&' : '?';
                img.src = `${proxyUrl}${separator}t=${Date.now()}`;
            }
        })
        .catch(() => {});
}

function updatePatrolPanelVisibility() {
    const panel = document.getElementById('global-patrol-panel');
    if (!panel) return;
    if (window.location.pathname === '/patrol-control') {
        panel.style.display = 'none';
        return;
    }
    panel.style.display = appState.patrol.activeRobotId ? 'block' : 'none';
}

function updatePatrolPanelRobotInfo() {
    const robotId = appState.patrol.activeRobotId;
    if (!robotId) return;

    apiCall(`/api/robots/${robotId}`).then(response => {
        if (response.success) {
            const robot = response.robot;
            const nameEl = document.getElementById('patrol-robot-name');
            if (nameEl) nameEl.textContent = robot.name || robot.serial_number || robotId;
            const batteryEl = document.getElementById('patrol-battery');
            if (batteryEl) {
                const batteryLevel = robot.battery_level;
                if (batteryLevel === null || batteryLevel === undefined) {
                    batteryEl.textContent = '--';
                } else if (batteryLevel === 0 && !robot.last_seen) {
                    batteryEl.textContent = '--';
                } else {
                    batteryEl.textContent = `${batteryLevel}%`;
                }
            }
            const locationEl = document.getElementById('patrol-location');
            if (locationEl) locationEl.textContent = robot.current_location || 'Unknown';
        }
    });

    const routeId = appState.patrol.activeRouteId;
    if (routeId) {
        apiCall(`/api/routes/${routeId}`).then(response => {
            if (response.success) {
                const route = response.route;
                const routeEl = document.getElementById('patrol-route-name');
                if (routeEl) routeEl.textContent = route.name || routeId;
            }
        });
    }
}

function updatePatrolPanelState(data) {
    const stateEl = document.getElementById('patrol-state');
    if (stateEl) stateEl.textContent = data.state || '-';

    const progressEl = document.getElementById('patrol-progress');
    if (progressEl) {
        progressEl.textContent = `${data.current_waypoint_index}/${data.total_waypoints}`;
    }

    const loopEl = document.getElementById('patrol-loop');
    if (loopEl) {
        const loopText = data.is_infinite_loop ? `${data.current_loop} of ?` :
            `${data.current_loop} of ${data.total_loops}`;
        loopEl.textContent = loopText;
    }

    if (data.battery_level !== undefined) {
        const batteryEl = document.getElementById('patrol-battery');
        if (batteryEl) batteryEl.textContent = `${data.battery_level}%`;
    }

    if (data.state === 'paused') {
        setPatrolPaused(true);
    } else if (data.state === 'running') {
        setPatrolPaused(false);
    } else if (data.state === 'idle' || data.state === 'stopped') {
        appState.patrol.activeRobotId = null;
        appState.patrol.activeRouteId = null;
        localStorage.removeItem('active_patrol_robot_id');
        localStorage.removeItem('active_patrol_route_id');
        updatePatrolPanelVisibility();
    }
}

function updatePatrolPanelYolo(data) {
    if (!data) return;
    appState.yolo.total_violations = data.total_violations || 0;
    appState.yolo.total_people = data.total_people || 0;
    appState.yolo.viewports = data.viewports || appState.yolo.viewports;

    const violationsEl = document.getElementById('patrol-violations');
    if (violationsEl) violationsEl.textContent = appState.yolo.total_violations;
    const peopleEl = document.getElementById('patrol-people');
    if (peopleEl) peopleEl.textContent = appState.yolo.total_people;

    const frontEl = document.getElementById('patrol-front');
    const rightEl = document.getElementById('patrol-right');
    const backEl = document.getElementById('patrol-back');
    const leftEl = document.getElementById('patrol-left');
    if (frontEl) frontEl.textContent = appState.yolo.viewports.front || 0;
    if (rightEl) rightEl.textContent = appState.yolo.viewports.right || 0;
    if (backEl) backEl.textContent = appState.yolo.viewports.back || 0;
    if (leftEl) leftEl.textContent = appState.yolo.viewports.left || 0;
}

// Socket.IO event handlers
if (socket) {
    socket.on('connect', function() {
        console.log('Connected to server');
        appState.connected = true;
        showToast('Connected to server', 'success');
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        appState.connected = false;
        showToast('Disconnected from server', 'warning');
    });

    socket.on('robot_connected', function(data) {
        console.log('Robot connected:', data);
        updateRobotConnectionStatus(data.robot_id, true);
        addActivityLog(`Robot ${data.serial_number} connected`, 'info');
    });

    socket.on('robot_disconnected', function(data) {
        console.log('Robot disconnected:', data);
        updateRobotConnectionStatus(data.robot_id, false);
        addActivityLog(`Robot ${data.serial_number} disconnected`, 'warning');
    });

    socket.on('robot_status', function(data) {
        console.log('Robot status:', data);
        updateRobotStatus(data);
        if (data.robot_id === appState.patrol.activeRobotId) {
            const batteryEl = document.getElementById('patrol-battery');
            if (batteryEl && data.battery !== undefined) {
                batteryEl.textContent = `${data.battery}%`;
            }
        }
    });

    socket.on('battery_update', function(data) {
        console.log('Battery update:', data);
        updateRobotBattery(data.robot_id, data.battery, data.is_charging);
        if (data.robot_id === appState.patrol.activeRobotId) {
            const batteryEl = document.getElementById('patrol-battery');
            if (batteryEl) batteryEl.textContent = `${data.battery}%`;
        }
    });

    socket.on('low_battery_alert', function(data) {
        console.log('Low battery alert:', data);
        showToast(`Low battery alert: Robot ${data.robot_id} at ${data.battery}%`, 'danger');
    });

    socket.on('waypoint_event', function(data) {
        console.log('Waypoint event:', data);
        addActivityLog(`Robot ${data.robot_id}: ${data.event_type} ${data.location} (${data.status})`, 'info');
        if (data.robot_id === appState.patrol.activeRobotId && data.location) {
            const locationEl = document.getElementById('patrol-location');
            if (locationEl) locationEl.textContent = data.location;
        }
    });

    socket.on('patrol_status_update', function(data) {
        console.log('Patrol status update:', data);
        updatePatrolStatus(data);
        if (!appState.patrol.activeRobotId) {
            appState.patrol.activeRobotId = data.robot_id;
        }
        if (appState.patrol.activeRobotId) {
            localStorage.setItem('active_patrol_robot_id', String(appState.patrol.activeRobotId));
        }
        updatePatrolPanelVisibility();
        updatePatrolPanelState(data);
    });

    socket.on('patrol_waypoint_reached', function(data) {
        console.log('Patrol waypoint reached:', data);
        addActivityLog(`Robot ${data.robot_id} reached waypoint: ${data.waypoint.waypoint_name}`, 'info');
    });

    socket.on('patrol_complete', function(data) {
        console.log('Patrol complete:', data);
        showToast(`Patrol completed for robot ${data.robot_id}`, 'success');
        addActivityLog(`Robot ${data.robot_id}: Patrol completed`, 'info');
        if (data.robot_id === appState.patrol.activeRobotId) {
            appState.patrol.activeRobotId = null;
            appState.patrol.activeRouteId = null;
            localStorage.removeItem('active_patrol_robot_id');
            localStorage.removeItem('active_patrol_route_id');
            updatePatrolPanelVisibility();
        }
    });

    socket.on('patrol_error', function(data) {
        console.log('Patrol error:', data);
        showToast(`Patrol error: ${data.error}`, 'danger');
        addActivityLog(`Robot ${data.robot_id}: Patrol error - ${data.error}`, 'error');
    });

    socket.on('violation_alert', function(data) {
        const rawLocation = data.location;
        const location = typeof rawLocation === 'object'
            ? (rawLocation.name || JSON.stringify(rawLocation))
            : (rawLocation || 'Unknown');
        const vtype = data.violation_type || 'Violation';
        showToast(`Violation at ${location}: ${vtype}`, 'danger');
        addActivityLog(`Violation: ${vtype} at ${location}`, 'warning');
    });

    socket.on('yolo_shutdown_prompt', function(data) {
        const timeout = (data && data.timeout) ? parseInt(data.timeout, 10) : 30;
        showToast(`YOLO will stop in ${timeout}s unless restarted`, 'warning');
        if (window._yoloShutdownTimer) {
            clearTimeout(window._yoloShutdownTimer);
        }
        window._yoloShutdownTimer = setTimeout(() => {
            appUtils.apiCall('/api/yolo/stop', 'POST', {}).then(() => {
                showToast('YOLO pipeline stopped', 'info');
            });
        }, Math.max(5, timeout) * 1000);
    });

    socket.on('yolo_summary', updatePatrolPanelYolo);
    socket.on('yolo_counts', updatePatrolPanelYolo);
} else {
    console.warn('Socket.IO not available; realtime updates disabled');
}

// Helper functions
function updateRobotConnectionStatus(robotId, connected) {
    const robotCard = document.querySelector(`[data-robot-id="${robotId}"]`);
    if (robotCard) {
        const statusBadge = robotCard.querySelector('.connection-status, .connection-badge');
        if (statusBadge) {
            statusBadge.textContent = connected ? 'Connected' : 'Disconnected';
            statusBadge.classList.remove('bg-success', 'bg-danger', 'connected', 'disconnected');
            if (connected) {
                statusBadge.classList.add('bg-success', 'connected');
            } else {
                statusBadge.classList.add('bg-danger', 'disconnected');
            }
        }
    }
}

function updateRobotStatus(data) {
    const robotCard = document.querySelector(`[data-robot-id="${data.robot_id}"]`);
    if (robotCard) {
        // Update waypoints if provided
        if (data.waypoints) {
            // Store waypoints in data attribute
            robotCard.dataset.waypoints = JSON.stringify(data.waypoints);
        }
        
        // Update battery if provided
        if (data.battery !== undefined) {
            updateRobotBattery(data.robot_id, data.battery, !!data.is_charging);
        }
    }
}

function updateRobotBattery(robotId, batteryLevel, isCharging) {
    const robotCard = document.querySelector(`[data-robot-id="${robotId}"]`);
    if (robotCard) {
        const batteryLevelSpan = robotCard.querySelector('.battery-level');
        const batteryBar = robotCard.querySelector('.battery-bar');
        const chargingBadge = robotCard.querySelector('.charging-status');
        
        if (batteryLevelSpan) {
            batteryLevelSpan.textContent = `${batteryLevel}%`;
            if (isCharging) {
                batteryLevelSpan.innerHTML += ' <i class="bi bi-lightning-charge"></i>';
            }
        }

        if (chargingBadge) {
            chargingBadge.textContent = isCharging ? 'Charging' : 'Idle';
            chargingBadge.classList.toggle('bg-warning', isCharging);
            chargingBadge.classList.toggle('bg-secondary', !isCharging);
        }
        
        if (batteryBar) {
            batteryBar.style.width = `${batteryLevel}%`;
            batteryBar.classList.remove('battery-high', 'battery-medium', 'battery-low', 
                                       'bg-success', 'bg-warning', 'bg-danger');
            
            if (batteryLevel > 50) {
                batteryBar.classList.add('battery-high', 'bg-success');
            } else if (batteryLevel > 20) {
                batteryBar.classList.add('battery-medium', 'bg-warning');
            } else {
                batteryBar.classList.add('battery-low', 'bg-danger');
            }
        }
    }
}

function updatePatrolStatus(data) {
    const robotCard = document.querySelector(`[data-robot-id="${data.robot_id}"]`);
    if (robotCard) {
        const statusBadge = robotCard.querySelector('.patrol-status');
        if (statusBadge) {
            statusBadge.textContent = data.state.charAt(0).toUpperCase() + data.state.slice(1);
            statusBadge.classList.remove('bg-success', 'bg-warning', 'bg-secondary', 'bg-danger',
                                        'running', 'paused', 'idle', 'stopped');
            
            if (data.state === 'running') {
                statusBadge.classList.add('bg-success', 'running');
            } else if (data.state === 'paused') {
                statusBadge.classList.add('bg-warning', 'paused');
            } else if (data.state === 'idle' || data.state === 'stopped') {
                statusBadge.classList.add('bg-secondary', data.state);
            } else if (data.state === 'error' || data.state === 'low_battery') {
                statusBadge.classList.add('bg-danger');
            }
        }
    }
}

function addActivityLog(message, level = 'info') {
    const activityLog = document.getElementById('recent-activity');
    if (activityLog) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${level} fade-in`;
        logEntry.innerHTML = `
            <small class="text-muted">${timestamp}</small>
            <span class="badge bg-${getLevelBadgeClass(level)} ms-2">${level}</span>
            <span class="ms-2">${message}</span>
        `;
        
        activityLog.insertBefore(logEntry, activityLog.firstChild);
        
        // Keep only last 50 entries
        while (activityLog.children.length > 50) {
            activityLog.removeChild(activityLog.lastChild);
        }
    }
}

function getLevelBadgeClass(level) {
    const classes = {
        'info': 'info',
        'warning': 'warning',
        'error': 'danger',
        'success': 'success'
    };
    return classes[level] || 'secondary';
}

function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Show toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 3000
    });
    bsToast.show();
    
    // Remove toast after hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

function showLoading(show = true) {
    let overlay = document.getElementById('loading-overlay');
    
    if (show) {
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'loading-overlay';
            overlay.className = 'spinner-overlay';
            overlay.innerHTML = '<div class="spinner-border text-light" style="width: 3rem; height: 3rem;" role="status"><span class="visually-hidden">Loading...</span></div>';
            document.body.appendChild(overlay);
        }
    } else {
        if (overlay) {
            overlay.remove();
        }
    }
}

function apiCall(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    return fetch(url, options)
        .then(response => response.json())
        .catch(error => {
            console.error('API call error:', error);
            showToast('Network error', 'danger');
            throw error;
        });
}

// Global event handlers
document.addEventListener('DOMContentLoaded', function() {
    // Home button handler
    document.querySelectorAll('.btn-goto-home').forEach(btn => {
        btn.addEventListener('click', function() {
            const robotId = this.dataset.robotId;
            if (confirm('Send robot to home base?')) {
                apiCall('/api/command/home', 'POST', { robot_id: parseInt(robotId) })
                    .then(response => {
                        if (response.success) {
                            showToast('Command sent: Go to home base', 'success');
                        } else {
                            showToast('Failed to send command', 'danger');
                        }
                    });
            }
        });
    });
    
    // Stop button handler
    document.querySelectorAll('.btn-stop').forEach(btn => {
        btn.addEventListener('click', function() {
            const robotId = this.dataset.robotId;
            if (confirm('Stop robot movement?')) {
                apiCall('/api/command/stop', 'POST', { robot_id: parseInt(robotId) })
                    .then(response => {
                        if (response.success) {
                            showToast('Command sent: Stop movement', 'success');
                        } else {
                            showToast('Failed to send command', 'danger');
                        }
                    });
            }
        });
    });

    initPatrolPanel();
});

let patrolStopTimer = null;
let patrolStopCountdownTimer = null;

function showPatrolStopPrompt(robotId, timeoutSeconds = 15) {
    const modalEl = document.getElementById('patrolStopModal');
    if (!modalEl || !window.bootstrap) {
        // Fallback: auto send home after timeout
        setTimeout(() => {
            apiCall('/api/patrol/stop_home_decision', 'POST', { robot_id: robotId, action: 'send' })
                .catch(() => {});
        }, timeoutSeconds * 1000);
        return;
    }

    const countdownEl = document.getElementById('patrolStopCountdown');
    const yesBtn = document.getElementById('patrolStopYes');
    const noBtn = document.getElementById('patrolStopNo');

    // Create fresh modal instance
    let modal = null;
    try {
        modal = new bootstrap.Modal(modalEl);
    } catch (e) {
        console.error('Error creating modal:', e);
        return;
    }

    let remaining = timeoutSeconds;
    if (countdownEl) countdownEl.textContent = remaining;

    let modalClosed = false;

    const cleanupTimers = () => {
        if (patrolStopTimer) {
            clearTimeout(patrolStopTimer);
        }
        if (patrolStopCountdownTimer) {
            clearInterval(patrolStopCountdownTimer);
        }
        patrolStopTimer = null;
        patrolStopCountdownTimer = null;
    };

    const closeModal = () => {
        if (modalClosed) return;
        modalClosed = true;
        try {
            cleanupTimers();
            if (modal) modal.hide();
            // Remove click handlers to prevent duplicate triggers
            if (yesBtn) yesBtn.onclick = null;
            if (noBtn) noBtn.onclick = null;
        } catch (e) {
            console.error('Error closing modal:', e);
        }
    };

    const autoSendHome = () => {
        apiCall('/api/patrol/stop_home_decision', 'POST', { robot_id: robotId, action: 'send' })
            .then(() => showToast('🏠 Robot sent to home base automatically', 'info'))
            .catch((err) => {
                console.error('Auto-send home failed:', err);
                showToast('Failed to auto-send to home base', 'danger');
            });
    };

    // Remove old handlers if any
    if (yesBtn) yesBtn.onclick = null;
    if (noBtn) noBtn.onclick = null;

    // Add new handlers
    if (yesBtn) {
        yesBtn.onclick = () => {
            cleanupTimers();
            apiCall('/api/patrol/stop_home_decision', 'POST', { robot_id: robotId, action: 'send' })
                .then(res => {
                    if (res.success) {
                        showToast('✅ Robot sent to home base', 'success');
                    } else {
                        showToast('❌ Failed to send home command', 'danger');
                    }
                })
                .catch(err => {
                    console.error('Send home error:', err);
                    showToast('❌ Error sending to home base', 'danger');
                })
                .finally(() => {
                    closeModal();
                });
        };
    }

    if (noBtn) {
        noBtn.onclick = () => {
            cleanupTimers();
            apiCall('/api/patrol/stop_home_decision', 'POST', { robot_id: robotId, action: 'cancel' })
                .catch((err) => {
                    console.error('Cancel home decision error:', err);
                })
                .finally(() => {
                    closeModal();
                    showToast('Patrol stop confirmed', 'info');
                });
        };
    }

    // Show modal
    try {
        modal.show();
    } catch (e) {
        console.error('Error showing modal:', e);
        return;
    }

    // Countdown timer
    patrolStopCountdownTimer = setInterval(() => {
        remaining -= 1;
        if (countdownEl) {
            countdownEl.textContent = Math.max(0, remaining);
        }
        if (remaining <= 0) {
            cleanupTimers();
        }
    }, 1000);

    // Auto-send timeout
    patrolStopTimer = setTimeout(() => {
        closeModal();
        autoSendHome();
    }, timeoutSeconds * 1000);
}

function getPatrolStopConfig() {
    return appUtils.apiCall('/api/settings')
        .then(res => {
            if (res.success && res.settings) {
                const raw = res.settings.patrol_stop_home_timeout_seconds;
                const value = parseInt(raw, 10);
                const always = String(res.settings.patrol_stop_always_send_home || '').toLowerCase() === 'true';
                return {
                    timeout: (!Number.isNaN(value) && value >= 5) ? value : 15,
                    alwaysSendHome: always
                };
            }
            return { timeout: 15, alwaysSendHome: false };
        })
        .catch(() => ({ timeout: 15, alwaysSendHome: false }));
}

function initPatrolPanel() {
    const panel = document.getElementById('global-patrol-panel');
    if (!panel) return;

    const toggleBtn = document.getElementById('patrol-panel-toggle');
    const body = document.getElementById('patrol-panel-body');
    if (toggleBtn && body) {
        toggleBtn.addEventListener('click', () => {
            appState.patrol.minimized = !appState.patrol.minimized;
            body.style.display = appState.patrol.minimized ? 'none' : 'block';
            toggleBtn.innerHTML = appState.patrol.minimized ?
                '<i class="bi bi-chevron-up"></i>' :
                '<i class="bi bi-chevron-down"></i>';
        });
    }

    const pauseBtn = document.getElementById('patrol-pause-btn');
    const resumeBtn = document.getElementById('patrol-resume-btn');
    const stopBtn = document.getElementById('patrol-stop-btn');
    const emergencyBtn = document.getElementById('patrol-emergency-stop-btn');
    const homeBtn = document.getElementById('patrol-home-btn');
    const speedSlider = document.getElementById('patrol-speed-global');

    if (pauseBtn) {
        pauseBtn.addEventListener('click', () => {
            if (!appState.patrol.activeRobotId) return;
            apiCall('/api/patrol/pause', 'POST', { robot_id: appState.patrol.activeRobotId })
                .then(res => {
                    if (res.success) setPatrolPaused(true);
                });
        });
    }

    if (resumeBtn) {
        resumeBtn.addEventListener('click', () => {
            if (!appState.patrol.activeRobotId) return;
            apiCall('/api/patrol/resume', 'POST', { robot_id: appState.patrol.activeRobotId })
                .then(res => {
                    if (res.success) setPatrolPaused(false);
                });
        });
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            if (!appState.patrol.activeRobotId) return;
            if (!confirm('Stop the current patrol?')) return;
            apiCall('/api/patrol/stop', 'POST', { robot_id: appState.patrol.activeRobotId })
                .then(res => {
                    if (res.success) {
                        getPatrolStopConfig().then(config => {
                            if (config.alwaysSendHome) {
                                apiCall('/api/patrol/stop_home_decision', 'POST', { robot_id: appState.patrol.activeRobotId, action: 'send' })
                                    .then(() => showToast('Command sent: Go to home base', 'success'))
                                    .catch(() => {});
                            } else {
                                showPatrolStopPrompt(appState.patrol.activeRobotId, config.timeout);
                            }
                        });
                        appState.patrol.activeRobotId = null;
                        appState.patrol.activeRouteId = null;
                        localStorage.removeItem('active_patrol_robot_id');
                        localStorage.removeItem('active_patrol_route_id');
                        updatePatrolPanelVisibility();
                    }
                });
        });
    }

    if (emergencyBtn) {
        emergencyBtn.addEventListener('click', () => {
            if (!appState.patrol.activeRobotId) return;
            if (!confirm('Emergency stop robot movement?')) return;
            apiCall('/api/command/stop', 'POST', { robot_id: appState.patrol.activeRobotId })
                .then(res => {
                    if (res.success) showToast('Emergency stop sent', 'success');
                });
        });
    }

    if (homeBtn) {
        homeBtn.addEventListener('click', () => {
            if (!appState.patrol.activeRobotId) return;
            if (!confirm('Send robot to home base?')) return;
            apiCall('/api/command/home', 'POST', { robot_id: appState.patrol.activeRobotId })
                .then(res => {
                    if (res.success) showToast('Command sent: Go to home base', 'success');
                });
        });
    }

    if (speedSlider) {
        speedSlider.addEventListener('input', function() {
            const speed = parseFloat(this.value);
            if (!appState.patrol.activeRobotId) return;
            apiCall('/api/patrol/speed', 'POST', { robot_id: appState.patrol.activeRobotId, speed });
        });
    }

    appState.patrol.activeRobotId = parseInt(localStorage.getItem('active_patrol_robot_id') || '', 10) || null;
    appState.patrol.activeRouteId = parseInt(localStorage.getItem('active_patrol_route_id') || '', 10) || null;
    updatePatrolPanelVisibility();
    updatePatrolPanelRobotInfo();
    loadStreamUrl();

    if (appState.patrol.activeRobotId) {
        apiCall(`/api/patrol/status/${appState.patrol.activeRobotId}`).then(response => {
            if (response.success && response.status) {
                updatePatrolPanelState(response.status);
            }
        });
    }
}

function setPatrolPaused(paused) {
    const pauseBtn = document.getElementById('patrol-pause-btn');
    const resumeBtn = document.getElementById('patrol-resume-btn');
    if (pauseBtn) pauseBtn.style.display = paused ? 'none' : 'block';
    if (resumeBtn) resumeBtn.style.display = paused ? 'block' : 'none';
}

window.patrolUI = {
    activate(robotId, routeId) {
        appState.patrol.activeRobotId = robotId;
        appState.patrol.activeRouteId = routeId || null;
        updatePatrolPanelVisibility();
        updatePatrolPanelRobotInfo();
        loadStreamUrl();
    },
    deactivate() {
        appState.patrol.activeRobotId = null;
        appState.patrol.activeRouteId = null;
        updatePatrolPanelVisibility();
    },
    setPaused(paused) {
        setPatrolPaused(paused);
    }
};

// Export functions for use in other scripts
window.appUtils = {
    showToast,
    showLoading,
    apiCall,
    updateRobotConnectionStatus,
    updateRobotBattery,
    updatePatrolStatus,
    addActivityLog
};
