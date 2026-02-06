/**
 * Schedules page JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    loadSchedules();
    loadScheduleHistory();
    bindScheduleEvents();
});

let schedulesCache = [];

function bindScheduleEvents() {
    const refreshBtn = document.getElementById('refreshSchedulesBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', loadSchedules);

    const scheduleType = document.getElementById('scheduleType');
    if (scheduleType) scheduleType.addEventListener('change', updateScheduleTypeFields);
    updateScheduleTypeFields();

    const saveBtn = document.getElementById('saveScheduleBtn');
    if (saveBtn) saveBtn.addEventListener('click', saveSchedule);
}

function updateScheduleTypeFields() {
    const type = document.getElementById('scheduleType').value;
    document.getElementById('weeklyConfig').style.display = type === 'weekly' ? 'block' : 'none';
    document.getElementById('onceConfig').style.display = type === 'once' ? 'block' : 'none';
    document.getElementById('customConfig').style.display = type === 'custom' ? 'block' : 'none';
    document.getElementById('scheduleTime').closest('.mb-3').style.display = type === 'custom' ? 'none' : 'block';
}

function loadSchedules() {
    appUtils.apiCall('/api/schedules').then(res => {
        if (res.success) {
            schedulesCache = res.schedules || [];
            renderSchedules(schedulesCache);
        } else {
            appUtils.showToast('Failed to load schedules', 'danger');
        }
    });
}

function loadScheduleHistory() {
    appUtils.apiCall('/api/schedules/history?limit=50').then(res => {
        if (res.success) {
            renderScheduleHistory(res.runs || []);
        } else {
            appUtils.showToast('Failed to load schedule history', 'danger');
        }
    });
}

function renderSchedules(schedules) {
    const tbody = document.getElementById('schedulesTableBody');
    if (!tbody) return;

    if (!schedules.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No schedules yet</td></tr>';
        return;
    }

    tbody.innerHTML = schedules.map(s => {
        const enabledBadge = s.enabled ? '<span class="badge bg-success">Enabled</span>' : '<span class="badge bg-secondary">Disabled</span>';
        const config = formatScheduleConfig(s.schedule_type, s.schedule_config);
        const lastRun = formatDateTime(s.last_run_at);
        const nextRun = computeNextRun(s);
        return `
            <tr>
                <td>${escapeHtml(s.name)}</td>
                <td>${escapeHtml(s.route_name || '')}</td>
                <td>${escapeHtml(s.robot_name || '')}</td>
                <td>${escapeHtml(s.schedule_type)}</td>
                <td><small class="text-muted">${config}</small></td>
                <td><small class="text-muted">${lastRun}</small></td>
                <td><small class="text-muted">${nextRun}</small></td>
                <td>${enabledBadge}</td>
                <td class="text-end">
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-success" onclick="runScheduleNow(${s.id})">Run Now</button>
                        <button class="btn btn-outline-primary" onclick="toggleSchedule(${s.id}, ${s.enabled ? 0 : 1})">
                            ${s.enabled ? 'Disable' : 'Enable'}
                        </button>
                        <button class="btn btn-outline-danger" onclick="deleteSchedule(${s.id})">Delete</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function formatScheduleConfig(type, cfg) {
    try {
        const config = typeof cfg === 'string' ? JSON.parse(cfg) : cfg;
        if (type === 'daily') return `Daily @ ${config.time || '-'}`;
        if (type === 'weekly') return `Weekly ${Array.isArray(config.days) ? config.days.join(', ') : '-'} @ ${config.time || '-'}`;
        if (type === 'once') return `Once @ ${config.datetime || '-'}`;
        return JSON.stringify(config);
    } catch (e) {
        return String(cfg || '');
    }
}

function computeNextRun(schedule) {
    if (!schedule.enabled) return '-';
    const type = schedule.schedule_type;
    const cfg = schedule.schedule_config || {};
    const now = new Date();

    if (type === 'daily') {
        const time = cfg.time || '09:00';
        const [h, m] = time.split(':').map(v => parseInt(v, 10));
        if (Number.isNaN(h) || Number.isNaN(m)) return '-';
        const next = new Date(now);
        next.setHours(h, m, 0, 0);
        if (next <= now) next.setDate(next.getDate() + 1);
        return formatDateTime(next);
    }

    if (type === 'weekly') {
        const time = cfg.time || '09:00';
        const days = cfg.days || [];
        if (!Array.isArray(days) || days.length === 0) return '-';
        const [h, m] = time.split(':').map(v => parseInt(v, 10));
        if (Number.isNaN(h) || Number.isNaN(m)) return '-';
        const dayMap = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
        const dayNums = days.map(d => dayMap[String(d).slice(0,3).toLowerCase()]).filter(v => v !== undefined);
        if (!dayNums.length) return '-';
        let next = new Date(now);
        for (let i = 0; i < 7; i++) {
            const candidate = new Date(now);
            candidate.setDate(now.getDate() + i);
            candidate.setHours(h, m, 0, 0);
            if (dayNums.includes(candidate.getDay()) && candidate > now) {
                next = candidate;
                return formatDateTime(next);
            }
        }
        return '-';
    }

    if (type === 'once') {
        const dt = cfg.datetime;
        if (!dt) return '-';
        const parsed = new Date(dt);
        if (Number.isNaN(parsed.getTime())) return '-';
        return parsed >= now ? formatDateTime(parsed) : 'Completed';
    }

    return '-';
}

function formatDateTime(value) {
    if (!value) return '-';
    try {
        const dt = value instanceof Date ? value : new Date(value);
        if (Number.isNaN(dt.getTime())) return '-';
        return dt.toLocaleString();
    } catch (e) {
        return '-';
    }
}

function saveSchedule() {
    const name = document.getElementById('scheduleName').value.trim();
    const routeId = parseInt(document.getElementById('scheduleRoute').value, 10);
    const type = document.getElementById('scheduleType').value;
    const enabled = document.getElementById('scheduleEnabled').checked ? 1 : 0;

    if (!name || !routeId) {
        appUtils.showToast('Please provide schedule name and route', 'warning');
        return;
    }

    let scheduleConfig = {};
    if (type === 'daily') {
        const time = document.getElementById('scheduleTime').value;
        if (!time) {
            appUtils.showToast('Please select a time', 'warning');
            return;
        }
        scheduleConfig = { time };
    } else if (type === 'weekly') {
        const days = Array.from(document.querySelectorAll('.weekly-day:checked')).map(el => el.value);
        const time = document.getElementById('scheduleTime').value;
        if (!days.length) {
            appUtils.showToast('Select at least one day', 'warning');
            return;
        }
        if (!time) {
            appUtils.showToast('Please select a time', 'warning');
            return;
        }
        scheduleConfig = { days, time };
    } else if (type === 'once') {
        const date = document.getElementById('scheduleDate').value;
        const time = document.getElementById('scheduleTime').value;
        if (!date || !time) {
            appUtils.showToast('Please select date and time', 'warning');
            return;
        }
        scheduleConfig = { datetime: `${date}T${time}` };
    } else if (type === 'custom') {
        try {
            scheduleConfig = JSON.parse(document.getElementById('scheduleCustom').value || '{}');
        } catch (e) {
            appUtils.showToast('Custom JSON is invalid', 'danger');
            return;
        }
    }

    const conflict = findScheduleConflict(routeId, type, scheduleConfig);
    if (conflict) {
        appUtils.showToast(`Schedule conflict with "${conflict.name}"`, 'danger');
        return;
    }

    const payload = {
        name,
        route_id: routeId,
        schedule_type: type,
        schedule_config: scheduleConfig,
        enabled
    };

    appUtils.apiCall('/api/schedules', 'POST', payload).then(res => {
        if (res.success) {
            appUtils.showToast('Schedule saved', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('scheduleModal'));
            if (modal) modal.hide();
            loadSchedules();
            document.getElementById('scheduleForm').reset();
        } else {
            appUtils.showToast(res.error || 'Failed to save schedule', 'danger');
        }
    });
}

function findScheduleConflict(routeId, type, config) {
    return schedulesCache.find(s => {
        if (parseInt(s.route_id, 10) !== routeId) return false;
        if (s.schedule_type !== type) return false;
        const existing = s.schedule_config || {};
        if (type === 'daily') return existing.time === config.time;
        if (type === 'weekly') {
            const a = (existing.days || []).slice().sort().join(',');
            const b = (config.days || []).slice().sort().join(',');
            return a === b && existing.time === config.time;
        }
        if (type === 'once') return existing.datetime === config.datetime;
        return false;
    });
}

function toggleSchedule(id, enabled) {
    appUtils.apiCall(`/api/schedules/${id}`, 'PUT', { enabled }).then(res => {
        if (res.success) {
            loadSchedules();
        } else {
            appUtils.showToast(res.error || 'Failed to update schedule', 'danger');
        }
    });
}

function deleteSchedule(id) {
    if (!confirm('Delete this schedule?')) return;
    appUtils.apiCall(`/api/schedules/${id}`, 'DELETE').then(res => {
        if (res.success) {
            loadSchedules();
            loadScheduleHistory();
        } else {
            appUtils.showToast(res.error || 'Failed to delete schedule', 'danger');
        }
    });
}

function runScheduleNow(id) {
    if (!confirm('Run this schedule now?')) return;
    appUtils.apiCall(`/api/schedules/${id}/run`, 'POST', {}).then(res => {
        if (res.success) {
            appUtils.showToast('Schedule started', 'success');
            loadSchedules();
            loadScheduleHistory();
        } else {
            appUtils.showToast(res.error || 'Failed to run schedule', 'danger');
        }
    });
}

function renderScheduleHistory(runs) {
    const tbody = document.getElementById('scheduleHistoryBody');
    if (!tbody) return;
    if (!runs.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No runs yet</td></tr>';
        return;
    }
    tbody.innerHTML = runs.map(r => `
        <tr>
            <td>${escapeHtml(r.schedule_name || '')}</td>
            <td>${escapeHtml(r.route_name || '')}</td>
            <td>${escapeHtml(r.robot_name || '')}</td>
            <td><small>${formatDateTime(r.started_at)}</small></td>
            <td>${escapeHtml(r.status || '')}</td>
            <td><small class="text-muted">${escapeHtml(r.message || '')}</small></td>
        </tr>
    `).join('');
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
