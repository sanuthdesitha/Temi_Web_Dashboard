/**
 * Robots page JavaScript
 */

let currentRobotForEdit = null;

document.addEventListener('DOMContentLoaded', function() {
    loadRobots();
    setupEventHandlers();
    
    // Refresh robots data every 3 seconds
    setInterval(loadRobots, 3000);
});

function setupEventHandlers() {
    // Add robot button
    document.getElementById('btn-save-robot').addEventListener('click', saveRobot);
    
    // Update robot button
    document.getElementById('btn-update-robot').addEventListener('click', updateRobot);
    
    // Event delegation for dynamic buttons
    document.getElementById('robots-table-body').addEventListener('click', function(e) {
        const target = e.target.closest('button');
        if (!target) return;
        
        const robotId = parseInt(target.dataset.robotId);
        
        if (target.classList.contains('btn-connect')) {
            connectRobot(robotId);
        } else if (target.classList.contains('btn-disconnect')) {
            disconnectRobot(robotId);
        } else if (target.classList.contains('btn-edit')) {
            editRobot(robotId);
        } else if (target.classList.contains('btn-delete')) {
            deleteRobot(robotId);
        } else if (target.classList.contains('btn-view-waypoints')) {
            viewWaypoints(robotId);
        }
    });
}

function loadRobots() {
    appUtils.apiCall('/api/robots').then(response => {
        if (response.success) {
            updateRobotsTable(response.robots);
        }
    });
}

function updateRobotsTable(robots) {
    const tbody = document.getElementById('robots-table-body');
    
    robots.forEach(robot => {
        let row = tbody.querySelector(`tr[data-robot-id="${robot.id}"]`);
        
        if (row) {
            // Update existing row
            const statusBadge = row.querySelector('.connection-badge');
            if (statusBadge) {
                statusBadge.textContent = robot.mqtt_connected ? 'Connected' : 'Disconnected';
                statusBadge.classList.remove('bg-success', 'bg-danger', 'connected', 'disconnected');
                if (robot.mqtt_connected) {
                    statusBadge.classList.add('bg-success', 'connected');
                } else {
                    statusBadge.classList.add('bg-danger', 'disconnected');
                }
            }
            
            const batterySpan = row.querySelector('.battery-level');
            if (batterySpan) {
                batterySpan.textContent = `${robot.battery_level}%`;
            }

            const chargingBadge = row.querySelector('.charging-status');
            if (chargingBadge) {
                chargingBadge.textContent = robot.is_charging ? 'Charging' : 'Idle';
                chargingBadge.classList.toggle('bg-warning', !!robot.is_charging);
                chargingBadge.classList.toggle('bg-secondary', !robot.is_charging);
            }
            
            const locationSpan = row.querySelector('.current-location');
            if (locationSpan) {
                locationSpan.textContent = robot.current_location || 'Unknown';
            }
        }
    });
}

function saveRobot() {
    const name = document.getElementById('robot-name').value.trim();
    const serial = document.getElementById('robot-serial').value.trim();
    
    if (!name || !serial) {
        appUtils.showToast('Please fill in required fields', 'danger');
        return;
    }
    
    const data = {
        name: name,
        serial_number: serial,
        mqtt_broker_url: document.getElementById('mqtt-broker').value.trim(),
        mqtt_port: document.getElementById('mqtt-port').value,
        mqtt_username: document.getElementById('mqtt-username').value.trim(),
        mqtt_password: document.getElementById('mqtt-password').value.trim(),
        use_tls: document.getElementById('mqtt-tls').checked
    };
    
    appUtils.showLoading(true);
    appUtils.apiCall('/api/robots', 'POST', data).then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            appUtils.showToast('Robot added successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addRobotModal')).hide();
            document.getElementById('add-robot-form').reset();
            loadRobots();
            location.reload(); // Refresh to update table
        } else {
            appUtils.showToast('Failed to add robot: ' + response.error, 'danger');
        }
    });
}

function connectRobot(robotId) {
    appUtils.showLoading(true);
    appUtils.apiCall(`/api/robots/${robotId}/connect`, 'POST').then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            appUtils.showToast('Robot connecting...', 'success');
            loadRobots();
        } else {
            appUtils.showToast('Failed to connect: ' + response.error, 'danger');
        }
    });
}

function disconnectRobot(robotId) {
    appUtils.showLoading(true);
    appUtils.apiCall(`/api/robots/${robotId}/disconnect`, 'POST').then(response => {
        appUtils.showLoading(false);

        if (response.success) {
            appUtils.showToast('Robot disconnected', 'info');
            loadRobots();
        } else {
            appUtils.showToast('Failed to disconnect: ' + response.error, 'danger');
        }
    });
}

function editRobot(robotId) {
    appUtils.apiCall(`/api/robots/${robotId}`).then(response => {
        if (response.success) {
            const robot = response.robot;
            currentRobotForEdit = robotId;
            
            document.getElementById('edit-robot-id').value = robot.id;
            document.getElementById('edit-robot-name').value = robot.name;
            document.getElementById('edit-mqtt-broker').value = robot.mqtt_broker_url || '';
            document.getElementById('edit-mqtt-port').value = robot.mqtt_port || '';
            document.getElementById('edit-mqtt-username').value = robot.mqtt_username || '';
            document.getElementById('edit-mqtt-password').value = '';
            document.getElementById('edit-mqtt-tls').checked = robot.use_tls;
            
            new bootstrap.Modal(document.getElementById('editRobotModal')).show();
        }
    });
}

function updateRobot() {
    const robotId = currentRobotForEdit;
    
    const data = {
        name: document.getElementById('edit-robot-name').value.trim(),
        mqtt_broker_url: document.getElementById('edit-mqtt-broker').value.trim(),
        mqtt_port: document.getElementById('edit-mqtt-port').value,
        mqtt_username: document.getElementById('edit-mqtt-username').value.trim(),
        mqtt_password: document.getElementById('edit-mqtt-password').value.trim(),
        use_tls: document.getElementById('edit-mqtt-tls').checked
    };
    
    appUtils.showLoading(true);
    appUtils.apiCall(`/api/robots/${robotId}`, 'PUT', data).then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            appUtils.showToast('Robot updated successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('editRobotModal')).hide();
            loadRobots();
        } else {
            appUtils.showToast('Failed to update robot', 'danger');
        }
    });
}

function deleteRobot(robotId) {
    if (!confirm('Are you sure you want to delete this robot?')) {
        return;
    }
    
    appUtils.showLoading(true);
    appUtils.apiCall(`/api/robots/${robotId}`, 'DELETE').then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            appUtils.showToast('Robot deleted successfully', 'success');
            location.reload(); // Refresh page
        } else {
            appUtils.showToast('Failed to delete robot', 'danger');
        }
    });
}

function viewWaypoints(robotId) {
    appUtils.apiCall(`/api/robots/${robotId}`).then(response => {
        if (response.success) {
            const robot = response.robot;
            const waypoints = robot.waypoints || [];
            
            const waypointsList = document.getElementById('waypoints-list');
            waypointsList.innerHTML = '';
            
            if (waypoints.length === 0) {
                waypointsList.innerHTML = '<div class="alert alert-info">No waypoints available. Robot needs to be connected and send status.</div>';
            } else {
                waypoints.forEach(waypoint => {
                    const item = document.createElement('div');
                    item.className = 'list-group-item';
                    item.innerHTML = `<i class="bi bi-geo-alt"></i> ${waypoint}`;
                    waypointsList.appendChild(item);
                });
            }
            
            new bootstrap.Modal(document.getElementById('waypointsModal')).show();
        }
    });
}
