/**
 * Violations page JavaScript
 */

let currentViolationId = null;

document.addEventListener('DOMContentLoaded', function() {
    loadRobots();
    loadViolations();
    loadStats();
    loadSummary();
    
    // Refresh data every 30 seconds
    setInterval(() => {
        loadViolations();
        loadStats();
        loadSummary();
    }, 30000);
    
    // Listen for real-time violation alerts
    if (window.socket) {
        window.socket.on('violation_alert', function(data) {
            console.log('New violation alert:', data);
            showViolationAlert(data);
            loadViolations();
            loadStats();
        });
    }
    
    // Acknowledge button
    document.getElementById('btn-acknowledge-violation').addEventListener('click', acknowledgeViolation);

    const summaryBtn = document.getElementById('btn-refresh-summary');
    if (summaryBtn) summaryBtn.addEventListener('click', loadSummary);

    const summaryGroup = document.getElementById('summary-group-by');
    if (summaryGroup) summaryGroup.addEventListener('change', loadSummary);
});

function loadRobots() {
    appUtils.apiCall('/api/robots').then(response => {
        if (response.success) {
            const select = document.getElementById('filter-robot');
            select.innerHTML = '<option value="">All Robots</option>';
            
            response.robots.forEach(robot => {
                const option = document.createElement('option');
                option.value = robot.id;
                option.textContent = robot.name;
                select.appendChild(option);
            });
        }
    });
}

function loadViolations() {
    const robotId = document.getElementById('filter-robot').value;
    const type = document.getElementById('filter-type').value;
    const severity = document.getElementById('filter-severity').value;
    const status = document.getElementById('filter-status').value;
    const startDate = document.getElementById('filter-start-date').value;
    const endDate = document.getElementById('filter-end-date').value;
    
    let url = '/api/violations?';
    if (robotId) url += `robot_id=${robotId}&`;
    if (type) url += `type=${type}&`;
    if (severity) url += `severity=${severity}&`;
    if (status) url += `status=${status}&`;
    if (startDate) url += `start_date=${startDate}&`;
    if (endDate) url += `end_date=${endDate}&`;
    
    appUtils.apiCall(url).then(response => {
        if (response.success) {
            renderViolationsTable(response.violations);
        }
    });
}

function loadSummary() {
    const robotId = document.getElementById('filter-robot').value;
    const type = document.getElementById('filter-type').value;
    const severity = document.getElementById('filter-severity').value;
    const status = document.getElementById('filter-status').value;
    const startDate = document.getElementById('filter-start-date').value;
    const endDate = document.getElementById('filter-end-date').value;
    const groupBy = document.getElementById('summary-group-by').value;

    let url = `/api/violations/summary?group_by=${groupBy}&`;
    if (robotId) url += `robot_id=${robotId}&`;
    if (type) url += `type=${type}&`;
    if (severity) url += `severity=${severity}&`;
    if (status) url += `status=${status}&`;
    if (startDate) url += `start_date=${startDate}&`;
    if (endDate) url += `end_date=${endDate}&`;

    appUtils.apiCall(url).then(response => {
        if (response.success) {
            renderSummaryTable(response.summary);
        }
    });
}

function loadStats() {
    const robotId = document.getElementById('filter-robot').value;
    const statsUrl = robotId ? `/api/violations/stats?robot_id=${robotId}` : '/api/violations/stats';
    appUtils.apiCall(statsUrl).then(response => {
        if (response.success) {
            const stats = response.stats;
            document.getElementById('total-violations').textContent = stats.total;

            document.getElementById('today-violations').textContent = stats.today_total || 0;
            document.getElementById('needs-action-violations').textContent = stats.pending_high || 0;
            document.getElementById('pending-violations').textContent = stats.pending_total || 0;
        }
    });
}

function renderViolationsTable(violations) {
    const tbody = document.getElementById('violations-table-body');
    
    if (violations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">No violations found</td></tr>';
        return;
    }
    
    tbody.innerHTML = '';
    
    violations.forEach(violation => {
        const tr = document.createElement('tr');
        
        const severityBadge = getSeverityBadge(violation.severity);
        const statusBadge = violation.acknowledged ? 
            '<span class="badge bg-success">Acknowledged</span>' :
            '<span class="badge bg-warning">Pending</span>';
        
        tr.innerHTML = `
            <td>${violation.id}</td>
            <td>${violation.robot_name || 'Unknown'}</td>
            <td>${violation.location}</td>
            <td>${new Date(violation.timestamp).toLocaleString()}</td>
            <td>${formatViolationType(violation.violation_type)}</td>
            <td>${severityBadge}</td>
            <td>${statusBadge}</td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="viewViolation(${violation.id})">
                    <i class="bi bi-eye"></i> View
                </button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}

function renderSummaryTable(summary) {
    const tbody = document.getElementById('violations-summary-body');
    if (!tbody) return;

    if (!summary || summary.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">No summary data</td></tr>';
        return;
    }

    tbody.innerHTML = '';
    summary.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.period}</td>
            <td>${row.total}</td>
            <td>${row.high_count || 0}</td>
            <td>${row.medium_count || 0}</td>
            <td>${row.low_count || 0}</td>
            <td>${row.acknowledged_count || 0}</td>
        `;
        tbody.appendChild(tr);
    });
}

function getSeverityBadge(severity) {
    const badges = {
        'low': '<span class="badge bg-info">Low</span>',
        'medium': '<span class="badge bg-warning">Medium</span>',
        'high': '<span class="badge bg-danger">High</span>'
    };
    return badges[severity] || '<span class="badge bg-secondary">Unknown</span>';
}

function formatViolationType(type) {
    const types = {
        'no_helmet': 'No Helmet',
        'no_vest': 'No Safety Vest',
        'no_gloves': 'No Gloves',
        'no_goggles': 'No Safety Goggles'
    };
    return types[type] || type;
}

function viewViolation(violationId) {
    appUtils.apiCall(`/api/violations?limit=1000`).then(response => {
        if (response.success) {
            const violation = response.violations.find(v => v.id === violationId);
            
            if (violation) {
                currentViolationId = violationId;
                
                const details = document.getElementById('violation-details');
                details.innerHTML = `
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>ID:</strong> ${violation.id}</p>
                            <p><strong>Robot:</strong> ${violation.robot_name || 'Unknown'}</p>
                            <p><strong>Location:</strong> ${violation.location}</p>
                            <p><strong>Timestamp:</strong> ${new Date(violation.timestamp).toLocaleString()}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>Type:</strong> ${formatViolationType(violation.violation_type)}</p>
                            <p><strong>Severity:</strong> ${getSeverityBadge(violation.severity)}</p>
                            <p><strong>Status:</strong> ${violation.acknowledged ? 
                                '<span class="badge bg-success">Acknowledged</span>' :
                                '<span class="badge bg-warning">Pending</span>'}</p>
                            ${violation.acknowledged ? 
                                `<p><strong>Acknowledged by:</strong> ${violation.acknowledged_by}<br>
                                 <strong>At:</strong> ${new Date(violation.acknowledged_at).toLocaleString()}</p>` : ''}
                        </div>
                    </div>
                    ${violation.image_path ? 
                        `<div class="row mt-3">
                            <div class="col-12">
                                <img src="${violation.image_path}" class="img-fluid" alt="Violation Image">
                            </div>
                        </div>` : ''}
                    ${violation.details ? 
                        `<div class="row mt-3">
                            <div class="col-12">
                                <strong>Details:</strong>
                                <p>${violation.details}</p>
                            </div>
                        </div>` : ''}
                `;
                
                // Show/hide acknowledge button
                const ackBtn = document.getElementById('btn-acknowledge-violation');
                ackBtn.style.display = violation.acknowledged ? 'none' : 'block';
                
                new bootstrap.Modal(document.getElementById('violationDetailModal')).show();
            }
        }
    });
}

function acknowledgeViolation() {
    if (!currentViolationId) return;
    
    appUtils.apiCall(`/api/violations/${currentViolationId}/acknowledge`, 'POST', {
        acknowledged_by: 'User'
    }).then(response => {
        if (response.success) {
            appUtils.showToast('Violation acknowledged', 'success');
            bootstrap.Modal.getInstance(document.getElementById('violationDetailModal')).hide();
            loadViolations();
            loadStats();
            loadSummary();
        } else {
            appUtils.showToast('Failed to acknowledge violation', 'danger');
        }
    });
}

function applyFilters() {
    loadViolations();
    loadStats();
    loadSummary();
}

function clearFilters() {
    document.getElementById('filter-robot').value = '';
    document.getElementById('filter-type').value = '';
    document.getElementById('filter-severity').value = '';
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-start-date').value = '';
    document.getElementById('filter-end-date').value = '';
    loadViolations();
    loadStats();
    loadSummary();
}

function exportViolations() {
    const robotId = document.getElementById('filter-robot').value;
    const type = document.getElementById('filter-type').value;
    const severity = document.getElementById('filter-severity').value;
    const status = document.getElementById('filter-status').value;
    const startDate = document.getElementById('filter-start-date').value;
    const endDate = document.getElementById('filter-end-date').value;
    let url = '/api/violations/export?';
    const params = [];
    if (robotId) params.push(`robot_id=${robotId}`);
    if (type) params.push(`type=${encodeURIComponent(type)}`);
    if (severity) params.push(`severity=${encodeURIComponent(severity)}`);
    if (status) params.push(`status=${encodeURIComponent(status)}`);
    if (startDate) params.push(`start_date=${encodeURIComponent(startDate)}`);
    if (endDate) params.push(`end_date=${encodeURIComponent(endDate)}`);
    url += params.join('&');
    
    window.location.href = url;
}

function showViolationAlert(data) {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = 'toast position-fixed top-0 end-0 m-3';
    toast.setAttribute('role', 'alert');
    toast.setAttribute('data-bs-autohide', 'false');
    toast.style.zIndex = '9999';
    
    toast.innerHTML = `
        <div class="toast-header bg-danger text-white">
            <i class="bi bi-shield-exclamation me-2"></i>
            <strong class="me-auto">New Violation Alert</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            <strong>${formatViolationType(data.violation_type)}</strong><br>
            Location: ${data.location}<br>
            Severity: ${data.severity.toUpperCase()}
        </div>
    `;
    
    document.body.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Play sound alert
    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZRQ0PVqzn77BdGAg+ltryxnMpBSh+zPLaizsIGGS57OihUBELTKXh8bllHAU2jdXzzn0vBSF1xe/glEILElyx6+2nVxYKQ5zd8sFuJAUufMny2Ys5CBZqvO3qoVASC0il4fK7aB4DNIzU8897MAYeb8Hv5JdFDBFYsOvvr10ZCT6X2/PFcicFKH3M8tmMOggYZbnr6qJREwtMpeHyu2geBDSM1PPPezAGHm/B7+SXRQwRWLDr769dGQk+l9vzxXInBSh9zPLZjDoIGGW56+qiURMLTKXh8rtoHgQ0jNTzz3swBh5vwe/kl0UMEViw6++vXRkJPpfb88VyJwUofc==');
    audio.play().catch(() => {}); // Ignore if audio fails
}
