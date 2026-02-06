/**
 * Detection sessions page JS
 */

document.addEventListener('DOMContentLoaded', function() {
    loadDetectionSessions();
    bindDetectionEvents();
});

let detectionChart = null;

function bindDetectionEvents() {
    const refreshBtn = document.getElementById('refreshDetectionBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', loadDetectionSessions);

    const startBtn = document.getElementById('startDetectionBtn');
    if (startBtn) startBtn.addEventListener('click', startDetection);

    const stopBtn = document.getElementById('stopDetectionBtn');
    if (stopBtn) stopBtn.addEventListener('click', stopDetection);

    const exportBtn = document.getElementById('exportDetectionCsvBtn');
    if (exportBtn) exportBtn.addEventListener('click', exportDetectionSessions);

    const robotSelect = document.getElementById('detectionRobotSelect');
    if (robotSelect) robotSelect.addEventListener('change', updateDetectionStatus);
}

function loadDetectionSessions() {
    appUtils.apiCall('/api/detection/sessions').then(res => {
        if (res.success) {
            renderDetectionSessions(res.sessions || []);
            updateDetectionChart(res.sessions || []);
        } else {
            appUtils.showToast('Failed to load detection sessions', 'danger');
        }
    });
}

function renderDetectionSessions(sessions) {
    const tbody = document.getElementById('detectionSessionsBody');
    if (!tbody) return;

    if (!sessions.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No sessions found</td></tr>';
        return;
    }

    tbody.innerHTML = sessions.map(s => `
        <tr>
            <td>${escapeHtml(s.robot_name || s.robot_id)}</td>
            <td>${escapeHtml(s.route_name || '')}</td>
            <td><span class="badge ${s.status === 'active' ? 'bg-success' : 'bg-secondary'}">${escapeHtml(s.status)}</span></td>
            <td>${escapeHtml(s.started_at || '')}</td>
            <td>${escapeHtml(s.ended_at || '--')}</td>
            <td>${s.violations_count || 0}</td>
        </tr>
    `).join('');
}

function updateDetectionChart(sessions) {
    const canvas = document.getElementById('detectionSessionsChart');
    if (!canvas || typeof Chart === 'undefined') return;

    const grouped = {};
    sessions.forEach(s => {
        const date = (s.started_at || '').slice(0, 10);
        if (!date) return;
        if (!grouped[date]) grouped[date] = { count: 0, violations: 0 };
        grouped[date].count += 1;
        grouped[date].violations += (s.violations_count || 0);
    });

    const labels = Object.keys(grouped).sort();
    const counts = labels.map(l => grouped[l].count);
    const violations = labels.map(l => grouped[l].violations);

    if (detectionChart) detectionChart.destroy();
    detectionChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Sessions',
                    data: counts,
                    backgroundColor: 'rgba(13,110,253,0.6)'
                },
                {
                    label: 'Violations',
                    data: violations,
                    backgroundColor: 'rgba(220,53,69,0.6)'
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                x: { stacked: false },
                y: { beginAtZero: true }
            }
        }
    });
}

function startDetection() {
    const robotId = parseInt(document.getElementById('detectionRobotSelect').value, 10);
    const routeId = document.getElementById('detectionRouteSelect').value;
    if (!robotId) {
        appUtils.showToast('Select a robot first', 'warning');
        return;
    }

    appUtils.apiCall('/api/detection/start', 'POST', {
        robot_id: robotId,
        route_id: routeId ? parseInt(routeId, 10) : null
    }).then(res => {
        if (res.success) {
            appUtils.showToast('Detection started', 'success');
            updateDetectionStatus();
            loadDetectionSessions();
        } else {
            appUtils.showToast(res.error || 'Failed to start detection', 'danger');
        }
    });
}

function stopDetection() {
    const robotId = parseInt(document.getElementById('detectionRobotSelect').value, 10);
    if (!robotId) {
        appUtils.showToast('Select a robot first', 'warning');
        return;
    }

    appUtils.apiCall('/api/detection/stop', 'POST', { robot_id: robotId }).then(res => {
        if (res.success) {
            appUtils.showToast('Detection stopped', 'success');
            updateDetectionStatus();
            loadDetectionSessions();
        } else {
            appUtils.showToast(res.error || 'Failed to stop detection', 'danger');
        }
    });
}

function updateDetectionStatus() {
    const robotId = parseInt(document.getElementById('detectionRobotSelect').value, 10);
    const statusEl = document.getElementById('detectionStatusText');
    if (!robotId || !statusEl) {
        if (statusEl) statusEl.textContent = 'Status: --';
        return;
    }

    appUtils.apiCall(`/api/detection/status/${robotId}`).then(res => {
        if (res.success) {
            statusEl.textContent = res.active ? 'Status: Active' : 'Status: Inactive';
        }
    });
}

function exportDetectionSessions() {
    const link = document.createElement('a');
    link.href = '/api/detection/sessions/export';
    link.download = `detection_sessions_${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
