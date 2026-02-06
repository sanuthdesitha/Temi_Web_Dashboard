/**
 * Routes page JavaScript
 */

let currentWaypoints = [];
let currentRouteWaypoints = [];
let availableWaypoints = [];
let selectedRobotId = null;
let currentPatrolRobotId = null;
let editRouteId = null;

document.addEventListener('DOMContentLoaded', function() {
    loadRoutes();
    setupEventHandlers();
    setupRouteModalHandlers();
});

function setupEventHandlers() {
    // Fetch waypoints button
    document.getElementById('btn-fetch-waypoints').addEventListener('click', fetchRobotWaypoints);
    
    // Add waypoint button
    document.getElementById('btn-add-waypoint').addEventListener('click', addWaypointToRoute);
    
    // Save route button
    document.getElementById('btn-save-route').addEventListener('click', saveRoute);
    
    // Save waypoint config button
    document.getElementById('btn-save-waypoint-config').addEventListener('click', saveWaypointConfig);
    
    // Display type change
    document.getElementById('display-type').addEventListener('change', function() {
        const contentGroup = document.getElementById('display-content-group');
        const webviewDelayGroup = document.getElementById('webview-close-delay-group');
        contentGroup.style.display = this.value ? 'block' : 'none';
        if (webviewDelayGroup) {
            webviewDelayGroup.style.display = this.value === 'webview' ? 'block' : 'none';
        }
    });

    // TTS preset change
    document.getElementById('tts-preset').addEventListener('change', function() {
        if (this.value) {
            document.getElementById('tts-message').value = this.value;
        }
    });

    // Violation action change
    document.getElementById('violation-action').addEventListener('change', function() {
        const contentGroup = document.getElementById('violation-action-content-group');
        const ttsGroup = document.getElementById('violation-tts-group');
        const action = this.value;
        contentGroup.style.display = (action === 'webview' || action === 'video') ? 'block' : 'none';
        ttsGroup.style.display = action === 'tts' ? 'block' : 'none';
    });
    
    // Event delegation for dynamic buttons
    document.getElementById('routes-table-body').addEventListener('click', function(e) {
        const target = e.target.closest('button');
        if (!target) return;
        
        if (target.classList.contains('btn-start-patrol')) {
            const routeId = parseInt(target.dataset.routeId);
            const robotId = parseInt(target.dataset.robotId);
            startPatrol(routeId, robotId);
        } else if (target.classList.contains('btn-view-route')) {
            const routeId = parseInt(target.dataset.routeId);
            viewRoute(routeId);
        } else if (target.classList.contains('btn-edit-route')) {
            const routeId = parseInt(target.dataset.routeId);
            editRoute(routeId);
        } else if (target.classList.contains('btn-delete-route')) {
            const routeId = parseInt(target.dataset.routeId);
            deleteRoute(routeId);
        }
    });
}

function setupRouteModalHandlers() {
    const modalEl = document.getElementById('addRouteModal');
    if (!modalEl) return;

    modalEl.addEventListener('hidden.bs.modal', function() {
        resetRouteModal();
    });
}

function resetRouteModal() {
    editRouteId = null;
    currentRouteWaypoints = [];
    availableWaypoints = [];
    selectedRobotId = null;

    document.getElementById('route-name').value = '';
    document.getElementById('route-loop-count').value = '1';

    const robotSelect = document.getElementById('route-robot');
    robotSelect.value = '';
    robotSelect.disabled = false;

    const returnSelect = document.getElementById('return-location');
    if (returnSelect) {
        returnSelect.innerHTML = '<option value="">Home Base (default)</option>';
        returnSelect.value = '';
    }

    document.querySelector('#addRouteModal .modal-title').textContent = 'Create New Route';
    document.getElementById('btn-save-route').textContent = 'Create Route';
    renderWaypointsBuilder();
}

function loadRoutes() {
    appUtils.apiCall('/api/routes').then(response => {
        if (response.success) {
            // Routes are already in the table from server render
            // This could be used for dynamic updates
        }
    });
}

function fetchRobotWaypoints() {
    const robotId = document.getElementById('route-robot').value;
    if (!robotId) {
        appUtils.showToast('Please select a robot first', 'warning');
        return;
    }
    
    selectedRobotId = parseInt(robotId);
    
    appUtils.showLoading(true);
    appUtils.apiCall(`/api/robots/${robotId}`).then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            const robot = response.robot;
            availableWaypoints = robot.waypoints || [];
            
            if (availableWaypoints.length === 0) {
                appUtils.showToast('No waypoints available. Make sure robot is connected.', 'warning');
                return;
            }
            
            appUtils.showToast(`Loaded ${availableWaypoints.length} waypoints`, 'success');
            currentRouteWaypoints = [];
            updateReturnLocationOptions();
            renderWaypointsBuilder();
        } else {
            appUtils.showToast('Failed to fetch waypoints', 'danger');
        }
    });
}

function updateReturnLocationOptions(selected = '') {
    const select = document.getElementById('return-location');
    if (!select) return;

    select.innerHTML = '<option value="">Home Base (default)</option>';
    availableWaypoints.forEach(wp => {
        const option = document.createElement('option');
        option.value = wp;
        option.textContent = wp;
        select.appendChild(option);
    });

    if (selected && !availableWaypoints.includes(selected)) {
        const option = document.createElement('option');
        option.value = selected;
        option.textContent = `${selected} (custom)`;
        select.appendChild(option);
    }

    if (selected) {
        select.value = selected;
    }
}

function renderWaypointsBuilder() {
    const builder = document.getElementById('waypoints-builder');
    
    if (availableWaypoints.length === 0) {
        builder.innerHTML = '<div class=\"alert alert-warning\">No waypoints available. Fetch waypoints from robot first.</div>';
        return;
    }
    
    builder.innerHTML = '';
    
    if (currentRouteWaypoints.length === 0) {
        builder.innerHTML = '<div class=\"alert alert-info\">No waypoints added yet. Click \"Add Waypoint\" below.</div>';
    } else {
        currentRouteWaypoints.forEach((waypoint, index) => {
            const waypointDiv = document.createElement('div');
            waypointDiv.className = 'waypoint-item mb-2';
            waypointDiv.innerHTML = `
                <div class=\"d-flex justify-content-between align-items-center\">
                    <div>
                        <span class=\"badge bg-primary\">${index + 1}</span>
                        <strong class=\"ms-2\">${waypoint.waypoint_name}</strong>
                        ${waypoint.display_type ? `<span class=\"badge bg-info ms-2\">${waypoint.display_type}</span>` : ''}
                        ${waypoint.tts_message ? '<span class=\"badge bg-success ms-1\">TTS</span>' : ''}
                        ${waypoint.detection_enabled ? '<span class=\"badge bg-warning ms-1\">Detect</span>' : ''}
                    </div>
                    <div class=\"btn-group\" role=\"group\">
                        <button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" onclick=\"moveWaypointUp(${index})\"><i class=\"bi bi-arrow-up\"></i></button>
                        <button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" onclick=\"moveWaypointDown(${index})\"><i class=\"bi bi-arrow-down\"></i></button>
                        <button type=\"button\" class=\"btn btn-sm btn-outline-primary\" onclick=\"configureWaypoint(${index})\"><i class=\"bi bi-gear\"></i></button>
                        <button type=\"button\" class=\"btn btn-sm btn-outline-danger\" onclick=\"removeWaypoint(${index})\"><i class=\"bi bi-trash\"></i></button>
                    </div>
                </div>
            `;
            builder.appendChild(waypointDiv);
        });
    }
}

function addWaypointToRoute() {
    if (availableWaypoints.length === 0) {
        appUtils.showToast('Please fetch waypoints from robot first', 'warning');
        return;
    }
    
    // Show selection dialog
    const select = document.createElement('select');
    select.className = 'form-select';
    select.innerHTML = '<option value=\"\">Select waypoint...</option>';
    availableWaypoints.forEach(wp => {
        select.innerHTML += `<option value=\"${wp}\">${wp}</option>`;
    });
    
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class=\"modal-dialog\">
            <div class=\"modal-content\">
                <div class=\"modal-header\">
                    <h5 class=\"modal-title\">Select Waypoint</h5>
                    <button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"modal\"></button>
                </div>
                <div class=\"modal-body\">
                    ${select.outerHTML}
                </div>
                <div class=\"modal-footer\">
                    <button type=\"button\" class=\"btn btn-secondary\" data-bs-dismiss=\"modal\">Cancel</button>
                    <button type=\"button\" class=\"btn btn-primary\" id=\"btn-confirm-waypoint\">Add</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.querySelector('#btn-confirm-waypoint').addEventListener('click', function() {
        const selectedWaypoint = modal.querySelector('select').value;
            if (selectedWaypoint) {
            currentRouteWaypoints.push(createDefaultWaypoint(selectedWaypoint));
            renderWaypointsBuilder();
            bsModal.hide();
        }
    });
    
    modal.addEventListener('hidden.bs.modal', function() {
        modal.remove();
    });
}

function createDefaultWaypoint(name) {
    return {
        waypoint_name: name,
        display_type: '',
        display_content: '',
        tts_message: '',
        dwell_time: 5,
        detection_enabled: 1,
        detection_timeout: 30,
        no_violation_seconds: 5,
        violation_action: 'tts',
        violation_tts_message: 'Please follow safety protocols and wear proper PPE.',
        violation_display_type: '',
        violation_display_content: '',
        webview_close_delay: 0
    };
}

function normalizeWaypoint(waypoint) {
    return {
        waypoint_name: waypoint.waypoint_name,
        display_type: waypoint.display_type || '',
        display_content: waypoint.display_content || '',
        tts_message: waypoint.tts_message || '',
        dwell_time: waypoint.dwell_time || 5,
        detection_enabled: waypoint.detection_enabled ? 1 : 0,
        detection_timeout: waypoint.detection_timeout || 30,
        no_violation_seconds: waypoint.no_violation_seconds || 5,
        violation_action: waypoint.violation_action || 'tts',
        violation_tts_message: waypoint.violation_tts_message || 'Please follow safety protocols and wear proper PPE.',
        violation_display_type: waypoint.violation_display_type || '',
        violation_display_content: waypoint.violation_display_content || '',
        webview_close_delay: waypoint.webview_close_delay || 0
    };
}

function removeWaypoint(index) {
    currentRouteWaypoints.splice(index, 1);
    renderWaypointsBuilder();
}

function moveWaypointUp(index) {
    if (index > 0) {
        [currentRouteWaypoints[index], currentRouteWaypoints[index - 1]] = 
        [currentRouteWaypoints[index - 1], currentRouteWaypoints[index]];
        renderWaypointsBuilder();
    }
}

function moveWaypointDown(index) {
    if (index < currentRouteWaypoints.length - 1) {
        [currentRouteWaypoints[index], currentRouteWaypoints[index + 1]] = 
        [currentRouteWaypoints[index + 1], currentRouteWaypoints[index]];
        renderWaypointsBuilder();
    }
}

function configureWaypoint(index) {
    const waypoint = currentRouteWaypoints[index];
    
    document.getElementById('waypoint-index').value = index;
    document.getElementById('waypoint-name-display').textContent = waypoint.waypoint_name;
    document.getElementById('display-type').value = waypoint.display_type || '';
    document.getElementById('display-content').value = waypoint.display_content || '';
    const webviewCloseDelayEl = document.getElementById('webview-close-delay');
    if (webviewCloseDelayEl) {
        webviewCloseDelayEl.value = waypoint.webview_close_delay || 0;
    }
    document.getElementById('tts-message').value = waypoint.tts_message || '';
    document.getElementById('dwell-time').value = waypoint.dwell_time || 5;
    document.getElementById('detection-enabled').checked = !!waypoint.detection_enabled;
    document.getElementById('detection-timeout').value = waypoint.detection_timeout || 30;
    document.getElementById('no-violation-seconds').value = waypoint.no_violation_seconds || 5;
    document.getElementById('violation-action').value = waypoint.violation_action || 'tts';
    document.getElementById('violation-tts-message').value = waypoint.violation_tts_message || 'Please follow safety protocols and wear proper PPE.';
    document.getElementById('violation-display-content').value = waypoint.violation_display_content || '';
    
    // Show/hide display content field
    const contentGroup = document.getElementById('display-content-group');
    contentGroup.style.display = waypoint.display_type ? 'block' : 'none';
    const webviewDelayGroup = document.getElementById('webview-close-delay-group');
    if (webviewDelayGroup) {
        webviewDelayGroup.style.display = waypoint.display_type === 'webview' ? 'block' : 'none';
    }

    const actionGroup = document.getElementById('violation-action-content-group');
    const ttsGroup = document.getElementById('violation-tts-group');
    const action = document.getElementById('violation-action').value;
    actionGroup.style.display = (action === 'webview' || action === 'video') ? 'block' : 'none';
    ttsGroup.style.display = action === 'tts' ? 'block' : 'none';
    
    new bootstrap.Modal(document.getElementById('waypointConfigModal')).show();
}

function saveWaypointConfig() {
    const index = parseInt(document.getElementById('waypoint-index').value);
    const waypoint = currentRouteWaypoints[index];
    
    waypoint.display_type = document.getElementById('display-type').value;
    waypoint.display_content = document.getElementById('display-content').value.trim();
    if (document.getElementById('webview-close-delay')) {
        waypoint.webview_close_delay = parseInt(document.getElementById('webview-close-delay').value, 10) || 0;
    }
    waypoint.tts_message = document.getElementById('tts-message').value.trim();
    waypoint.dwell_time = parseInt(document.getElementById('dwell-time').value) || 5;
    waypoint.detection_enabled = document.getElementById('detection-enabled').checked ? 1 : 0;
    waypoint.detection_timeout = parseInt(document.getElementById('detection-timeout').value, 10) || 30;
    waypoint.no_violation_seconds = parseInt(document.getElementById('no-violation-seconds').value, 10) || 5;
    waypoint.violation_action = document.getElementById('violation-action').value;
    waypoint.violation_tts_message = document.getElementById('violation-tts-message').value;
    waypoint.violation_display_content = document.getElementById('violation-display-content').value.trim();
    waypoint.violation_display_type = (waypoint.violation_action === 'webview' || waypoint.violation_action === 'video')
        ? waypoint.violation_action
        : '';
    
    renderWaypointsBuilder();
    bootstrap.Modal.getInstance(document.getElementById('waypointConfigModal')).hide();
    appUtils.showToast('Waypoint configuration saved', 'success');
}

function saveRoute() {
    const name = document.getElementById('route-name').value.trim();
    const robotId = selectedRobotId;
    const loopCount = parseInt(document.getElementById('route-loop-count').value);
    const returnLocation = document.getElementById('return-location').value || '';
    
    if (!name) {
        appUtils.showToast('Please enter a route name', 'warning');
        return;
    }
    
    if (!robotId) {
        appUtils.showToast('Please select a robot', 'warning');
        return;
    }
    
    if (currentRouteWaypoints.length < 2) {
        appUtils.showToast('Route must have at least 2 waypoints', 'warning');
        return;
    }

    const validationError = validateWaypoints(currentRouteWaypoints);
    if (validationError) {
        appUtils.showToast(validationError, 'danger');
        return;
    }
    
    const data = {
        name: name,
        robot_id: robotId,
        waypoints: currentRouteWaypoints,
        loop_count: loopCount,
        return_location: returnLocation
    };
    
    appUtils.showLoading(true);
    const isEdit = !!editRouteId;
    const url = isEdit ? `/api/routes/${editRouteId}` : '/api/routes';
    const method = isEdit ? 'PUT' : 'POST';

    appUtils.apiCall(url, method, data).then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            const loopText = loopCount <= 0 ? 'infinite loops' : `${loopCount} loop(s)`;
            const actionText = isEdit ? 'updated' : 'created';
            appUtils.showToast(`Route ${actionText} successfully (${loopText})`, 'success');
            bootstrap.Modal.getInstance(document.getElementById('addRouteModal')).hide();
            location.reload(); // Refresh page
        } else {
            const actionText = isEdit ? 'update' : 'create';
            appUtils.showToast(`Failed to ${actionText} route: ${response.error}`, 'danger');
        }
    });
}

function validateWaypoints(waypoints) {
    const seen = new Set();
    for (const wp of waypoints) {
        const name = String(wp.waypoint_name || '').trim();
        if (!name) return 'Waypoint name is required';
        if (seen.has(name)) return `Duplicate waypoint: ${name}`;
        seen.add(name);

        if (availableWaypoints && availableWaypoints.length) {
            if (!availableWaypoints.includes(name)) {
                return `Waypoint "${name}" not found on robot`;
            }
        }

        const dwell = parseInt(wp.dwell_time, 10);
        if (Number.isNaN(dwell) || dwell < 0) return `Invalid dwell time for ${name}`;

        if (wp.tts_message && String(wp.tts_message).length > 200) {
            return `TTS message too long for ${name} (max 200 chars)`;
        }

        if (wp.display_type && !wp.display_content) {
            return `Display content required for ${name}`;
        }

        const detectionTimeout = parseInt(wp.detection_timeout, 10);
        if (wp.detection_enabled && (Number.isNaN(detectionTimeout) || detectionTimeout < 5)) {
            return `Detection timeout invalid for ${name}`;
        }
    }
    return '';
}

function viewRoute(routeId) {
    appUtils.apiCall(`/api/routes/${routeId}`).then(response => {
        if (response.success) {
            const route = response.route;
            
            document.getElementById('view-route-title').textContent = route.name;
            
            const detailsDiv = document.getElementById('route-details');
            const returnLocation = route.return_location || 'Home Base';
            const loopCountText = route.loop_count <= 0 ? 'Infinite' : route.loop_count;
            detailsDiv.innerHTML = `
                <p><strong>Robot:</strong> ${route.robot_name}</p>
                <p><strong>Total Waypoints:</strong> ${route.waypoints.length}</p>
                <p><strong>Loop Count:</strong> ${loopCountText}</p>
                <p><strong>Return Location:</strong> ${returnLocation}</p>
                <hr>
                <h6>Waypoints:</h6>
                <ol class=\"list-group list-group-numbered\">
                    ${route.waypoints.map(wp => `
                        <li class=\"list-group-item\">
                            <strong>${wp.waypoint_name}</strong>
                            <br><small>
                                ${wp.display_type ? `Display: ${wp.display_type} | ` : ''}
                                ${wp.tts_message ? `TTS: "${wp.tts_message}" | ` : ''}
                                Dwell: ${wp.dwell_time}s
                            </small>
                        </li>
                    `).join('')}
                </ol>
            `;
            
            new bootstrap.Modal(document.getElementById('viewRouteModal')).show();
        }
    });
}

function editRoute(routeId) {
    appUtils.showLoading(true);
    appUtils.apiCall(`/api/routes/${routeId}`).then(response => {
        if (!response.success) {
            appUtils.showLoading(false);
            appUtils.showToast('Failed to load route details', 'danger');
            return;
        }

        const route = response.route;
        editRouteId = routeId;
        selectedRobotId = route.robot_id;
        currentRouteWaypoints = (route.waypoints || []).map(normalizeWaypoint);

        document.getElementById('route-name').value = route.name || '';
        document.getElementById('route-loop-count').value = route.loop_count ?? 1;
        document.getElementById('return-location').value = route.return_location || '';

        const robotSelect = document.getElementById('route-robot');
        robotSelect.value = route.robot_id;
        robotSelect.disabled = true;

        document.querySelector('#addRouteModal .modal-title').textContent = 'Edit Route';
        document.getElementById('btn-save-route').textContent = 'Update Route';

        appUtils.apiCall(`/api/robots/${route.robot_id}`).then(robotResponse => {
            appUtils.showLoading(false);
            if (robotResponse.success) {
                availableWaypoints = robotResponse.robot.waypoints || [];
            } else {
                availableWaypoints = [];
            }
            updateReturnLocationOptions(route.return_location || '');
            renderWaypointsBuilder();
            new bootstrap.Modal(document.getElementById('addRouteModal')).show();
        });
    });
}

function deleteRoute(routeId) {
    if (!confirm('Are you sure you want to delete this route?')) {
        return;
    }
    
    appUtils.showLoading(true);
    appUtils.apiCall(`/api/routes/${routeId}`, 'DELETE').then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            appUtils.showToast('Route deleted successfully', 'success');
            location.reload(); // Refresh page
        } else {
            appUtils.showToast('Failed to delete route', 'danger');
        }
    });
}

function startPatrol(routeId, robotId) {
    if (!confirm('Start patrol with this route?')) {
        return;
    }
    
    appUtils.showLoading(true);
    appUtils.apiCall('/api/patrol/start', 'POST', {
        robot_id: robotId,
        route_id: routeId
    }).then(response => {
        appUtils.showLoading(false);
        
    if (response.success) {
        appUtils.showToast('Patrol started', 'success');
        currentPatrolRobotId = robotId;
        localStorage.setItem('active_patrol_robot_id', String(robotId));
        localStorage.setItem('active_patrol_route_id', String(routeId));
        if (window.patrolUI && typeof window.patrolUI.activate === 'function') {
            window.patrolUI.activate(robotId, routeId);
        }
    } else {
        appUtils.showToast('Failed to start patrol: ' + response.error, 'danger');
    }
    });
}

function pausePatrol() {
    if (!currentPatrolRobotId) return;
    
    appUtils.apiCall('/api/patrol/pause', 'POST', {
        robot_id: currentPatrolRobotId
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Patrol paused', 'info');
            if (window.patrolUI && typeof window.patrolUI.setPaused === 'function') {
                window.patrolUI.setPaused(true);
            }
        }
    });
}

function resumePatrol() {
    if (!currentPatrolRobotId) return;
    
    appUtils.apiCall('/api/patrol/resume', 'POST', {
        robot_id: currentPatrolRobotId
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Patrol resumed', 'info');
            if (window.patrolUI && typeof window.patrolUI.setPaused === 'function') {
                window.patrolUI.setPaused(false);
            }
        }
    });
}

function stopPatrol() {
    if (!currentPatrolRobotId) return;
    
    if (!confirm('Stop the current patrol?')) {
        return;
    }
    
    appUtils.apiCall('/api/patrol/stop', 'POST', {
        robot_id: currentPatrolRobotId
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Patrol stopped', 'info');
            if (typeof getPatrolStopConfig === 'function' && typeof showPatrolStopPrompt === 'function') {
                getPatrolStopConfig().then(config => {
                    if (config.alwaysSendHome) {
                        appUtils.apiCall('/api/command/home', 'POST', { robot_id: currentPatrolRobotId });
                    } else {
                        showPatrolStopPrompt(currentPatrolRobotId, config.timeout);
                    }
                });
            } else if (typeof showPatrolStopPrompt === 'function') {
                showPatrolStopPrompt(currentPatrolRobotId);
            }
            localStorage.removeItem('active_patrol_robot_id');
            localStorage.removeItem('active_patrol_route_id');
            if (window.patrolUI && typeof window.patrolUI.deactivate === 'function') {
                window.patrolUI.deactivate();
            }
        }
    });
}

function updatePatrolSpeed(speed) {
    if (currentPatrolRobotId) {
        appUtils.apiCall('/api/patrol/speed', 'POST', {
            robot_id: currentPatrolRobotId,
            speed: speed
        });
    }
}

window.routesPatrol = { pausePatrol, resumePatrol, stopPatrol, updatePatrolSpeed };
