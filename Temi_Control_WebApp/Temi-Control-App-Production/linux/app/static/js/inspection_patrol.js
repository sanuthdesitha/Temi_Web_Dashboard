/**
 * YOLO Inspection Patrol - Frontend Logic
 * Handles route creation, patrol control, and real-time status updates
 */

document.addEventListener('DOMContentLoaded', function() {
    const socket = window.socket || io();

    let currentRobotId = null;
    let currentSessionId = null;
    let selectedRouteId = null;
    let availableWaypoints = [];

    // Initialize
    loadRobots();
    loadRoutes();
    loadSessions();

    // Event Listeners - Route Builder
    document.getElementById('inspection-robot-select').addEventListener('change', function(e) {
        currentRobotId = parseInt(e.target.value) || null;
        availableWaypoints = [];
        document.getElementById('waypoint-list').innerHTML = '';
    });

    document.getElementById('fetch-waypoints-btn').addEventListener('click', fetchWaypoints);
    document.getElementById('save-route-btn').addEventListener('click', saveRoute);

    // Event Listeners - Patrol Control
    document.getElementById('inspection-route-select').addEventListener('change', function(e) {
        selectedRouteId = parseInt(e.target.value) || null;
    });

    document.getElementById('start-inspection-btn').addEventListener('click', startInspection);
    document.getElementById('stop-inspection-btn').addEventListener('click', stopInspection);

    // Socket.IO Event Listeners
    socket.on('yolo_inspection_status', updateInspectionStatus);
    socket.on('yolo_inspection_waypoint_result', handleWaypointResult);
    socket.on('yolo_inspection_complete', handleInspectionComplete);
    socket.on('yolo_inspection_error', handleInspectionError);
    socket.on('yolo_summary', updateCurrentViolations);

    // Load Functions
    async function loadRobots() {
        try {
            const response = await fetch('/api/robots');
            const data = await response.json();

            if (data.success) {
                const select = document.getElementById('inspection-robot-select');
                select.innerHTML = '<option value="">Select robot...</option>';

                data.robots.forEach(robot => {
                    const option = document.createElement('option');
                    option.value = robot.id;
                    option.textContent = robot.name;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to load robots:', error);
            showToast('Failed to load robots', 'danger');
        }
    }

    async function loadRoutes() {
        try {
            const response = await fetch('/api/yolo-inspection-routes');
            const data = await response.json();

            if (data.success) {
                const select = document.getElementById('inspection-route-select');
                select.innerHTML = '<option value="">Select route...</option>';

                data.routes.forEach(route => {
                    const option = document.createElement('option');
                    option.value = route.id;
                    option.textContent = `${route.name} (${route.waypoint_count || 0} waypoints)`;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to load routes:', error);
            showToast('Failed to load routes', 'danger');
        }
    }

    async function loadSessions() {
        try {
            const response = await fetch('/api/yolo-inspection-sessions?limit=20');
            const data = await response.json();

            if (data.success) {
                renderSessionsTable(data.sessions);
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
        }
    }

    // Route Builder Functions
    async function fetchWaypoints() {
        if (!currentRobotId) {
            showToast('Please select a robot first', 'warning');
            return;
        }

        const btn = document.getElementById('fetch-waypoints-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Fetching...';

        try {
            // Send MQTT command to fetch waypoints
            const response = await fetch('/api/command/waypoints', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({robot_id: currentRobotId})
            });

            const data = await response.json();

            if (data.success) {
                showToast('Waypoint request sent. Please wait...', 'info');

                // Wait for waypoints to be received (poll robot data)
                setTimeout(async () => {
                    const robotResponse = await fetch(`/api/robots/${currentRobotId}`);
                    const robotData = await robotResponse.json();

                    if (robotData.success && robotData.robot.waypoints) {
                        availableWaypoints = robotData.robot.waypoints;
                        renderWaypointBuilder(availableWaypoints);
                        showToast('Waypoints fetched successfully', 'success');
                    } else {
                        showToast('No waypoints found. Make sure robot has saved locations.', 'warning');
                    }

                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-download"></i> Fetch Waypoints from Robot';
                }, 3000);
            } else {
                throw new Error(data.error || 'Failed to fetch waypoints');
            }
        } catch (error) {
            console.error('Fetch waypoints error:', error);
            showToast(error.message, 'danger');
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-download"></i> Fetch Waypoints from Robot';
        }
    }

    function renderWaypointBuilder(waypoints) {
        const container = document.getElementById('waypoint-list');
        container.innerHTML = '';

        if (waypoints.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No waypoints available. Fetch waypoints from robot first.</div>';
            return;
        }

        waypoints.forEach((wpName, index) => {
            const card = document.createElement('div');
            card.className = 'card mb-2';
            card.dataset.waypoint = wpName;
            card.innerHTML = `
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col-md-3">
                            <div class="form-check">
                                <input class="form-check-input waypoint-checkbox" type="checkbox" value="${wpName}" id="wp-${index}" checked>
                                <label class="form-check-label" for="wp-${index}">
                                    <strong>${wpName}</strong>
                                </label>
                            </div>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label small mb-0">Order:</label>
                            <input type="number" class="form-control form-control-sm waypoint-order" value="${index + 1}" min="1">
                        </div>
                        <div class="col-md-5">
                            <label class="form-label small mb-0">Inspection Duration: <span class="duration-value">30</span>s</label>
                            <input type="range" class="form-range waypoint-duration"
                                   data-waypoint="${wpName}"
                                   min="10" max="120" step="5" value="30"
                                   oninput="this.parentElement.querySelector('.duration-value').textContent=this.value">
                        </div>
                        <div class="col-md-2 text-end">
                            <button class="btn btn-sm btn-outline-danger remove-waypoint" data-waypoint="${wpName}">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

        // Add remove button listeners
        container.querySelectorAll('.remove-waypoint').forEach(btn => {
            btn.addEventListener('click', function() {
                this.closest('.card').remove();
            });
        });
    }

    async function saveRoute() {
        const name = document.getElementById('route-name').value.trim();

        if (!name) {
            showToast('Please enter a route name', 'warning');
            return;
        }

        if (!currentRobotId) {
            showToast('Please select a robot', 'warning');
            return;
        }

        // Collect selected waypoints with durations and order
        const waypoints = [];
        document.querySelectorAll('#waypoint-list .card').forEach(card => {
            const checkbox = card.querySelector('.waypoint-checkbox');
            if (checkbox && checkbox.checked) {
                const wpName = checkbox.value;
                const duration = parseInt(card.querySelector('.waypoint-duration').value);
                const order = parseInt(card.querySelector('.waypoint-order').value);

                waypoints.push({
                    waypoint_name: wpName,
                    checking_duration: duration,
                    sequence_order: order
                });
            }
        });

        if (waypoints.length === 0) {
            showToast('Please select at least one waypoint', 'warning');
            return;
        }

        // Sort by order
        waypoints.sort((a, b) => a.sequence_order - b.sequence_order);

        try {
            const response = await fetch('/api/yolo-inspection-routes', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: name,
                    robot_id: currentRobotId,
                    waypoints: waypoints,
                    loop_count: 1
                })
            });

            const data = await response.json();

            if (data.success) {
                showToast('Inspection route saved successfully', 'success');
                document.getElementById('route-name').value = '';
                document.getElementById('waypoint-list').innerHTML = '';
                availableWaypoints = [];
                loadRoutes();
            } else {
                throw new Error(data.error || 'Failed to save route');
            }
        } catch (error) {
            console.error('Save route error:', error);
            showToast(error.message, 'danger');
        }
    }

    // Patrol Control Functions
    async function startInspection() {
        if (!selectedRouteId) {
            showToast('Please select an inspection route', 'warning');
            return;
        }

        const btn = document.getElementById('start-inspection-btn');
        btn.disabled = true;

        try {
            const response = await fetch('/api/yolo-inspection-patrols/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({route_id: selectedRouteId})
            });

            const data = await response.json();

            if (data.success) {
                showToast('Inspection patrol started', 'success');
                enableControlButtons(true);
                updateStateBadge('starting', 'info');
            } else {
                throw new Error(data.error || 'Failed to start inspection');
            }
        } catch (error) {
            console.error('Start inspection error:', error);
            showToast(error.message, 'danger');
            btn.disabled = false;
        }
    }

    async function stopInspection() {
        if (!currentRobotId) {
            showToast('No active inspection patrol', 'warning');
            return;
        }

        if (!confirm('Are you sure you want to stop the inspection patrol?')) {
            return;
        }

        try {
            const response = await fetch(`/api/yolo-inspection-patrols/${currentRobotId}/stop`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
                showToast('Inspection patrol stopped', 'info');
                enableControlButtons(false);
                updateStateBadge('stopped', 'secondary');
                loadSessions();
            } else {
                throw new Error(data.error || 'Failed to stop inspection');
            }
        } catch (error) {
            console.error('Stop inspection error:', error);
            showToast(error.message, 'danger');
        }
    }

    // Socket.IO Event Handlers
    function updateInspectionStatus(data) {
        console.log('Inspection status update:', data);

        // Update current robot ID and session ID
        currentRobotId = data.robot_id;
        currentSessionId = data.session_id;

        // Update state badge
        updateStateBadge(data.state);

        // Update pipeline status
        if (data.pipeline_status) {
            updatePipelineBadge(data.pipeline_status);
        }

        // Update current waypoint
        const waypointText = data.current_waypoint_index !== undefined && data.total_waypoints
            ? `Waypoint ${data.current_waypoint_index + 1} of ${data.total_waypoints}`
            : '-';
        document.getElementById('current-waypoint').textContent = waypointText;

        // Update progress
        if (data.current_waypoint_index !== undefined && data.total_waypoints) {
            const progress = Math.round((data.current_waypoint_index / data.total_waypoints) * 100);
            document.getElementById('progress').textContent = `${progress}%`;
        } else {
            document.getElementById('progress').textContent = '-';
        }
    }

    function handleWaypointResult(data) {
        console.log('Waypoint result:', data);

        const message = data.violations > 0
            ? `${data.waypoint_name}: ${data.violations} violations detected (${data.people} people)`
            : `${data.waypoint_name}: No violations detected`;

        showToast(message, data.violations > 0 ? 'warning' : 'success');
    }

    function handleInspectionComplete(data) {
        console.log('Inspection complete:', data);

        showToast(`Inspection complete! Session ID: ${data.session_id}`, 'info');
        enableControlButtons(false);
        updateStateBadge('completed', 'success');
        loadSessions();
    }

    function handleInspectionError(data) {
        console.error('Inspection error:', data);
        showToast(`Inspection error: ${data.error}`, 'danger');
        enableControlButtons(false);
        updateStateBadge('error', 'danger');
    }

    function updateCurrentViolations(data) {
        // Update real-time violation counts during inspection
        if (data.total_violations !== undefined) {
            document.getElementById('violations-current').textContent = data.total_violations;
        }
        if (data.total_people !== undefined) {
            document.getElementById('people-current').textContent = data.total_people;
        }
    }

    // Sessions Table Functions
    function renderSessionsTable(sessions) {
        const tbody = document.getElementById('sessions-tbody');
        tbody.innerHTML = '';

        if (sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No inspection sessions found</td></tr>';
            return;
        }

        sessions.forEach(session => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${session.id}</td>
                <td>${session.route_name || 'N/A'}</td>
                <td>${formatDateTime(session.started_at)}</td>
                <td>${session.ended_at ? formatDateTime(session.ended_at) : '-'}</td>
                <td>${session.total_waypoints_inspected || 0}</td>
                <td>
                    <span class="badge ${session.total_violations_found > 0 ? 'bg-danger' : 'bg-success'}">
                        ${session.total_violations_found || 0}
                    </span>
                </td>
                <td><span class="badge bg-${getStatusBadgeColor(session.status)}">${session.status}</span></td>
                <td>
                    <button class="btn btn-sm btn-info" onclick="viewSessionDetails(${session.id})">
                        <i class="bi bi-eye"></i> Details
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    window.viewSessionDetails = async function(sessionId) {
        try {
            const response = await fetch(`/api/yolo-waypoint-inspections/${sessionId}`);
            const data = await response.json();

            if (data.success) {
                renderWaypointDetails(data.inspections);

                const modal = new bootstrap.Modal(document.getElementById('sessionDetailsModal'));
                modal.show();
            } else {
                throw new Error(data.error || 'Failed to load session details');
            }
        } catch (error) {
            console.error('Load session details error:', error);
            showToast(error.message, 'danger');
        }
    };

    function renderWaypointDetails(inspections) {
        const tbody = document.getElementById('waypoint-details-tbody');
        tbody.innerHTML = '';

        if (inspections.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No waypoint inspections found</td></tr>';
            return;
        }

        inspections.forEach(inspection => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${inspection.waypoint_name}</td>
                <td>
                    <span class="badge ${inspection.violations_detected > 0 ? 'bg-danger' : 'bg-success'}">
                        ${inspection.violations_detected || 0}
                    </span>
                </td>
                <td>${inspection.people_detected || 0}</td>
                <td>${inspection.duration_seconds || 0}s</td>
                <td>
                    <span class="badge bg-${inspection.result === 'no_violation' ? 'success' : 'warning'}">
                        ${inspection.result || 'unknown'}
                    </span>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    // UI Helper Functions
    function enableControlButtons(isRunning) {
        document.getElementById('start-inspection-btn').disabled = isRunning;
        document.getElementById('stop-inspection-btn').disabled = !isRunning;
    }

    function updateStateBadge(state, colorClass = null) {
        const badge = document.getElementById('state-badge');
        badge.textContent = formatStateName(state);

        if (colorClass) {
            badge.className = `badge bg-${colorClass}`;
        } else {
            badge.className = `badge bg-${getStateBadgeColor(state)}`;
        }
    }

    function updatePipelineBadge(status) {
        const badge = document.getElementById('pipeline-badge');
        badge.textContent = status;
        badge.className = `badge bg-${status === 'running' ? 'success' : status === 'stopped' ? 'danger' : 'warning'}`;
    }

    function formatStateName(state) {
        return state.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    function getStateBadgeColor(state) {
        const colorMap = {
            'idle': 'secondary',
            'checking_pipeline': 'info',
            'starting_pipeline': 'info',
            'running': 'primary',
            'moving_to_waypoint': 'info',
            'inspecting': 'warning',
            'waypoint_complete': 'success',
            'completed': 'success',
            'stopped': 'secondary',
            'error': 'danger'
        };
        return colorMap[state] || 'secondary';
    }

    function getStatusBadgeColor(status) {
        const colorMap = {
            'running': 'primary',
            'completed': 'success',
            'stopped': 'secondary',
            'error': 'danger'
        };
        return colorMap[status] || 'secondary';
    }

    function formatDateTime(timestamp) {
        if (!timestamp) return '-';
        const date = new Date(timestamp);
        return date.toLocaleString();
    }

    function showToast(message, type = 'info') {
        // Use existing toast system if available
        if (typeof toastr !== 'undefined') {
            toastr[type](message);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
            alert(message);
        }
    }
});
