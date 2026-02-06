/**
 * Logs page JavaScript
 */

let autoRefreshInterval = null;

document.addEventListener('DOMContentLoaded', function() {
    setupEventHandlers();
    startAutoRefresh();
});

function setupEventHandlers() {
    // Refresh button
    document.getElementById('btn-refresh-logs').addEventListener('click', loadLogs);
    
    // Clear logs button
    document.getElementById('btn-clear-logs').addEventListener('click', clearLogs);
    
    // Filter change handlers
    document.getElementById('filter-robot').addEventListener('change', filterLogs);
    document.getElementById('filter-level').addEventListener('change', filterLogs);
    document.getElementById('filter-search').addEventListener('input', filterLogs);
    
    // Auto-refresh toggle
    document.getElementById('auto-refresh').addEventListener('change', function() {
        if (this.checked) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    });
    
    // Live feed toggle
    document.getElementById('btn-toggle-live-feed').addEventListener('click', toggleLiveFeed);
    document.getElementById('btn-close-live-feed').addEventListener('click', closeLiveFeed);
}

function loadLogs() {
    const robotId = document.getElementById('filter-robot').value;
    const limit = 500;
    
    let url = `/api/logs?limit=${limit}`;
    if (robotId) {
        url += `&robot_id=${robotId}`;
    }
    
    appUtils.apiCall(url).then(response => {
        if (response.success) {
            updateLogsTable(response.logs);
            filterLogs();
        }
    });
}

function updateLogsTable(logs) {
    const tbody = document.getElementById('logs-table-body');
    tbody.innerHTML = '';
    
    logs.forEach(log => {
        const row = document.createElement('tr');
        row.className = `log-entry log-${log.level}`;
        row.dataset.robotId = log.robot_id || '';
        row.dataset.level = log.level;
        
        let levelBadge = '';
        if (log.level === 'info') {
            levelBadge = '<span class="badge bg-info">Info</span>';
        } else if (log.level === 'warning') {
            levelBadge = '<span class="badge bg-warning text-dark">Warning</span>';
        } else if (log.level === 'error') {
            levelBadge = '<span class="badge bg-danger">Error</span>';
        }
        
        row.innerHTML = `
            <td><small>${log.created_at}</small></td>
            <td>${levelBadge}</td>
            <td><small>${log.robot_name || 'System'}</small></td>
            <td>${log.message}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function filterLogs() {
    const robotId = document.getElementById('filter-robot').value;
    const level = document.getElementById('filter-level').value;
    const search = document.getElementById('filter-search').value.toLowerCase();
    
    const rows = document.querySelectorAll('#logs-table-body tr');
    
    rows.forEach(row => {
        let show = true;
        
        // Filter by robot
        if (robotId && row.dataset.robotId !== robotId) {
            show = false;
        }
        
        // Filter by level
        if (level && row.dataset.level !== level) {
            show = false;
        }
        
        // Filter by search
        if (search) {
            const text = row.textContent.toLowerCase();
            if (!text.includes(search)) {
                show = false;
            }
        }
        
        row.style.display = show ? '' : 'none';
    });
}

function clearLogs() {
    if (!confirm('Are you sure you want to clear all logs?')) {
        return;
    }
    
    const robotId = document.getElementById('filter-robot').value;
    const data = robotId ? { robot_id: parseInt(robotId) } : {};
    
    appUtils.showLoading(true);
    appUtils.apiCall('/api/logs/clear', 'POST', data).then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            appUtils.showToast('Logs cleared successfully', 'success');
            loadLogs();
        } else {
            appUtils.showToast('Failed to clear logs', 'danger');
        }
    });
}

function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(loadLogs, 5000);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

function toggleLiveFeed() {
    const panel = document.getElementById('live-log-panel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function closeLiveFeed() {
    document.getElementById('live-log-panel').style.display = 'none';
}

// Listen for WebSocket events to update live feed
socket.on('robot_connected', addLiveLogEntry);
socket.on('robot_disconnected', addLiveLogEntry);
socket.on('waypoint_event', addLiveLogEntry);
socket.on('battery_update', addLiveLogEntry);
socket.on('patrol_status_update', addLiveLogEntry);

function addLiveLogEntry(data) {
    const liveContent = document.getElementById('live-log-content');
    if (!liveContent) return;
    
    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.style.marginBottom = '5px';
    entry.textContent = `[${timestamp}] ${JSON.stringify(data).substring(0, 100)}...`;
    
    liveContent.insertBefore(entry, liveContent.firstChild);
    
    // Keep only last 50 entries
    while (liveContent.children.length > 50) {
        liveContent.removeChild(liveContent.lastChild);
    }
}