document.addEventListener('DOMContentLoaded', function() {
    const socket = window.socket || (window.io ? io() : null);

    // Clear stale patrol state from localStorage on page load
    // This prevents the panel from appearing stuck if server was restarted
    localStorage.removeItem('active_patrol_robot_id');
    localStorage.removeItem('active_patrol_route_id');

    const state = {
        robotId: null,
        routeId: null
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

    function loadStream() {
        const img = document.getElementById('patrolFullStreamImg');
        if (!img) return;

        appUtils.apiCall('/api/settings').then(response => {
            if (!response.success || !response.settings) return;
            const url = ensureStreamPath(
                normalizeStreamUrl(response.settings.yolo_stream_url || 'http://192.168.18.135:8080')
            );
            const proxyUrl = `/api/stream?url=${encodeURIComponent(url)}`;
            const separator = proxyUrl.includes('?') ? '&' : '?';
            img.src = `${proxyUrl}${separator}t=${Date.now()}`;
        });
    }

    function setPaused(paused) {
        const pauseBtn = document.getElementById('patrol-full-pause');
        const resumeBtn = document.getElementById('patrol-full-resume');
        if (pauseBtn) pauseBtn.style.display = paused ? 'none' : 'inline-block';
        if (resumeBtn) resumeBtn.style.display = paused ? 'inline-block' : 'none';
    }

    function resetUI() {
        // Reset all UI elements to default state on page load
        document.getElementById('patrol-full-robot').textContent = '-';
        document.getElementById('patrol-full-route').textContent = '-';
        document.getElementById('patrol-full-state').textContent = '-';
        document.getElementById('patrol-full-loop').textContent = '-';
        document.getElementById('patrol-full-progress').textContent = '-';
        document.getElementById('patrol-full-battery').textContent = '-';
        document.getElementById('patrol-full-location').textContent = '-';
        document.getElementById('patrol-full-violations').textContent = '0';
        document.getElementById('patrol-full-people').textContent = '0';
        document.getElementById('patrol-full-front').textContent = '0';
        document.getElementById('patrol-full-right').textContent = '0';
        document.getElementById('patrol-full-back').textContent = '0';
        document.getElementById('patrol-full-left').textContent = '0';

        // Reset pause/resume buttons
        setPaused(false);

        // Enable all control buttons
        const buttons = ['patrol-full-pause', 'patrol-full-resume', 'patrol-full-stop', 'patrol-full-emergency', 'patrol-full-home'];
        buttons.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) btn.disabled = false;
        });
    }

    function updateStatus(status) {
        if (!status) return;
        document.getElementById('patrol-full-state').textContent = status.state || '-';
        document.getElementById('patrol-full-progress').textContent =
            `${status.current_waypoint_index}/${status.total_waypoints}`;
        const loopText = status.is_infinite_loop ? `${status.current_loop} of ?` :
            `${status.current_loop} of ${status.total_loops}`;
        document.getElementById('patrol-full-loop').textContent = loopText;
        if (status.battery_level !== undefined) {
            document.getElementById('patrol-full-battery').textContent = `${status.battery_level}%`;
        }
        if (status.state === 'paused') setPaused(true);
        if (status.state === 'running') setPaused(false);
    }

    function updateYolo(data) {
        if (!data) return;
        document.getElementById('patrol-full-violations').textContent = data.total_violations || 0;
        document.getElementById('patrol-full-people').textContent = data.total_people || 0;
        const vp = data.viewports || {};
        document.getElementById('patrol-full-front').textContent = vp.front || 0;
        document.getElementById('patrol-full-right').textContent = vp.right || 0;
        document.getElementById('patrol-full-back').textContent = vp.back || 0;
        document.getElementById('patrol-full-left').textContent = vp.left || 0;
    }

    function renderPatrolSummary(summary) {
        if (!summary) return;
        const routeEl = document.getElementById('patrolSummaryRoute');
        const robotEl = document.getElementById('patrolSummaryRobot');
        const startEl = document.getElementById('patrolSummaryStart');
        const endEl = document.getElementById('patrolSummaryEnd');
        const violationsEl = document.getElementById('patrolSummaryViolations');
        const peopleEl = document.getElementById('patrolSummaryPeople');
        const bodyEl = document.getElementById('patrolSummaryBody');

        if (routeEl) routeEl.textContent = summary.route_name || summary.route_id || '-';
        if (robotEl) robotEl.textContent = summary.robot_id || '-';
        if (startEl) startEl.textContent = summary.started_at || '-';
        if (endEl) endEl.textContent = summary.ended_at || '-';
        if (violationsEl) violationsEl.textContent = summary.total_violations || 0;
        if (peopleEl) peopleEl.textContent = summary.total_people || 0;

        if (bodyEl) {
            const rows = (summary.waypoints || []).map(wp => `
                <tr>
                    <td>${escapeHtml(wp.waypoint_name || wp.name || '')}</td>
                    <td>${wp.total_violations || 0}</td>
                    <td>${wp.total_people || 0}</td>
                </tr>
            `).join('');
            bodyEl.innerHTML = rows || '<tr><td colspan="3" class="text-center text-muted">No waypoint summary available</td></tr>';
        }

        const modalEl = document.getElementById('patrolSummaryModal');
        if (modalEl && window.bootstrap) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }
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

    function loadRobotRouteInfo() {
        if (state.robotId) {
            appUtils.apiCall(`/api/robots/${state.robotId}`).then(response => {
                if (response.success) {
                    const robot = response.robot;
                    document.getElementById('patrol-full-robot').textContent = robot.name || robot.serial_number || state.robotId;
                    const batteryEl = document.getElementById('patrol-full-battery');
                    const batteryLevel = robot.battery_level;
                    if (batteryLevel === null || batteryLevel === undefined) {
                        batteryEl.textContent = '--';
                    } else if (batteryLevel === 0 && !robot.last_seen) {
                        batteryEl.textContent = '--';
                    } else {
                        batteryEl.textContent = `${batteryLevel}%`;
                    }
                    document.getElementById('patrol-full-location').textContent = robot.current_location || 'Unknown';
                }
            });
        }
        if (state.routeId) {
            appUtils.apiCall(`/api/routes/${state.routeId}`).then(response => {
                if (response.success) {
                    document.getElementById('patrol-full-route').textContent = response.route.name || state.routeId;
                }
            });
        }
    }

    function loadRoutes() {
        const select = document.getElementById('patrolRouteSelect');
        if (!select) return;
        appUtils.apiCall('/api/routes').then(response => {
            if (!response.success) return;
            select.innerHTML = '<option value="">Select route...</option>';
            (response.routes || []).forEach(route => {
                const opt = document.createElement('option');
                opt.value = route.id;
                opt.textContent = `${route.name} (${route.robot_name || 'Robot'})`;
                opt.dataset.robotId = route.robot_id;
                select.appendChild(opt);
            });
        });
    }

    function bindControls() {
        const startBtn = document.getElementById('patrolStartBtn');
        if (startBtn) {
            startBtn.addEventListener('click', () => {
                const select = document.getElementById('patrolRouteSelect');
                const routeId = select ? parseInt(select.value, 10) : null;
                if (!routeId) {
                    appUtils.showToast('Select a route first', 'warning');
                    return;
                }
                const robotId = parseInt(select.options[select.selectedIndex].dataset.robotId, 10);
                if (!robotId) {
                    appUtils.showToast('Route has no robot assigned', 'warning');
                    return;
                }
                appUtils.apiCall('/api/patrol/start', 'POST', { robot_id: robotId, route_id: routeId })
                    .then(res => {
                        if (res.success) {
                            appUtils.showToast('Patrol started', 'success');
                            state.robotId = robotId;
                            state.routeId = routeId;
                            localStorage.setItem('active_patrol_robot_id', String(robotId));
                            localStorage.setItem('active_patrol_route_id', String(routeId));
                            loadRobotRouteInfo();
                        } else {
                            appUtils.showToast(res.error || 'Failed to start patrol', 'danger');
                        }
                    });
            });
        }
        document.getElementById('patrol-full-pause').addEventListener('click', () => {
            if (!state.robotId) return;
            const btn = document.getElementById('patrol-full-pause');
            btn.disabled = true;
            appUtils.apiCall('/api/patrol/pause', 'POST', { robot_id: state.robotId })
                .then(res => {
                    if (res.success) {
                        setPaused(true);
                        appUtils.showToast('Patrol paused', 'info');
                    } else {
                        appUtils.showToast(res.error || 'Failed to pause patrol', 'danger');
                    }
                })
                .catch(err => {
                    appUtils.showToast('Error pausing patrol', 'danger');
                })
                .finally(() => {
                    btn.disabled = false;
                });
        });
        document.getElementById('patrol-full-resume').addEventListener('click', () => {
            if (!state.robotId) return;
            const btn = document.getElementById('patrol-full-resume');
            btn.disabled = true;
            appUtils.apiCall('/api/patrol/resume', 'POST', { robot_id: state.robotId })
                .then(res => {
                    if (res.success) {
                        setPaused(false);
                        appUtils.showToast('Patrol resumed', 'info');
                    } else {
                        appUtils.showToast(res.error || 'Failed to resume patrol', 'danger');
                    }
                })
                .catch(err => {
                    appUtils.showToast('Error resuming patrol', 'danger');
                })
                .finally(() => {
                    btn.disabled = false;
                });
        });
        document.getElementById('patrol-full-stop').addEventListener('click', () => {
            if (!state.robotId) return;
            if (!confirm('Stop the current patrol?')) return;

            const stopBtn = document.getElementById('patrol-full-stop');
            const homeBtn = document.getElementById('patrol-full-home');
            stopBtn.disabled = true;
            if (homeBtn) homeBtn.disabled = true;

            appUtils.apiCall('/api/patrol/stop', 'POST', { robot_id: state.robotId })
                .then(res => {
                    if (res.success) {
                        updateStatus({ state: 'stopped', current_waypoint_index: 0, total_waypoints: 0, current_loop: 0, total_loops: 0 });
                        appUtils.showToast('Patrol stopped', 'info');

                        // Show home base popup BEFORE clearing state
                        if (typeof getPatrolStopConfig === 'function' && typeof showPatrolStopPrompt === 'function') {
                            getPatrolStopConfig().then(config => {
                                if (config.alwaysSendHome) {
                                    appUtils.apiCall('/api/patrol/stop_home_decision', 'POST', { robot_id: state.robotId, action: 'send' })
                                        .then(() => {
                                            appUtils.showToast('Robot sent to home base', 'success');
                                        });
                                } else {
                                    showPatrolStopPrompt(state.robotId, config.timeout);
                                }
                            }).finally(() => {
                                // Clear state after popup is handled or timeout
                                setTimeout(() => {
                                    state.robotId = null;
                                    state.routeId = null;
                                    localStorage.removeItem('active_patrol_robot_id');
                                    localStorage.removeItem('active_patrol_route_id');
                                }, 1000);
                            });
                        } else if (typeof showPatrolStopPrompt === 'function') {
                            showPatrolStopPrompt(state.robotId);
                            // Clear state after popup
                            setTimeout(() => {
                                state.robotId = null;
                                state.routeId = null;
                                localStorage.removeItem('active_patrol_robot_id');
                                localStorage.removeItem('active_patrol_route_id');
                            }, 1000);
                        } else {
                            // No popup function, clear state immediately
                            state.robotId = null;
                            state.routeId = null;
                            localStorage.removeItem('active_patrol_robot_id');
                            localStorage.removeItem('active_patrol_route_id');
                        }
                    } else {
                        appUtils.showToast(res.error || 'Failed to stop patrol', 'danger');
                    }
                })
                .catch(err => {
                    appUtils.showToast('Error stopping patrol', 'danger');
                })
                .finally(() => {
                    stopBtn.disabled = false;
                    if (homeBtn) homeBtn.disabled = false;
                });
        });
        document.getElementById('patrol-full-emergency').addEventListener('click', () => {
            if (!state.robotId) return;
            if (!confirm('Emergency stop robot movement?')) return;
            appUtils.apiCall('/api/command/stop', 'POST', { robot_id: state.robotId });
        });
        document.getElementById('patrol-full-home').addEventListener('click', () => {
            if (!state.robotId) return;
            if (!confirm('Send robot to home base?')) return;
            appUtils.apiCall('/api/command/home', 'POST', { robot_id: state.robotId });
        });
        document.getElementById('patrol-full-speed').addEventListener('input', function() {
            if (!state.robotId) return;
            const speed = parseFloat(this.value);
            appUtils.apiCall('/api/patrol/speed', 'POST', { robot_id: state.robotId, speed });
        });
    }

    if (socket) {
        socket.on('patrol_status_update', function(data) {
            if (!state.robotId) {
                state.robotId = data.robot_id;
                localStorage.setItem('active_patrol_robot_id', String(state.robotId));
            }
            updateStatus(data);
            if (data.state === 'stopped' || data.state === 'idle') {
                state.robotId = null;
                state.routeId = null;
                localStorage.removeItem('active_patrol_robot_id');
                localStorage.removeItem('active_patrol_route_id');
            }
        });
        socket.on('patrol_complete', function(data) {
            if (data.robot_id === state.robotId) {
                state.robotId = null;
                state.routeId = null;
                localStorage.removeItem('active_patrol_robot_id');
                localStorage.removeItem('active_patrol_route_id');
                updateStatus({ state: 'stopped', current_waypoint_index: 0, total_waypoints: 0, current_loop: 0, total_loops: 0 });
            }
        });
        socket.on('patrol_summary', function(data) {
            renderPatrolSummary(data);
        });
        socket.on('battery_update', function(data) {
            if (data.robot_id === state.robotId) {
                document.getElementById('patrol-full-battery').textContent = `${data.battery}%`;
            }
        });
        socket.on('waypoint_event', function(data) {
            if (data.robot_id === state.robotId && data.location) {
                document.getElementById('patrol-full-location').textContent = data.location;
            }
        });
        socket.on('yolo_summary', updateYolo);
        socket.on('yolo_counts', updateYolo);
    }

    // Reset UI to default state on page load
    resetUI();

    bindControls();
    loadRoutes();
    loadRobotRouteInfo();
    loadStream();

    if (state.robotId) {
        appUtils.apiCall(`/api/patrol/status/${state.robotId}`).then(response => {
            if (response.success && response.status) updateStatus(response.status);
        });

        // Handle YOLO shutdown prompt
        socket.on('yolo_shutdown_prompt', function(data) {
            const modal = new bootstrap.Modal(document.getElementById('yoloShutdownModal'));
            modal.show();

            let countdown = data.timeout || 30;
            const countdownEl = document.getElementById('yoloShutdownCountdown');
            const interval = setInterval(() => {
                countdown--;
                if (countdownEl) countdownEl.textContent = countdown;
                if (countdown <= 0) {
                    clearInterval(interval);
                    terminateYoloPipeline();
                    modal.hide();
                }
            }, 1000);

            const btnTerminate = document.getElementById('btnTerminateYolo');
            if (btnTerminate) {
                btnTerminate.onclick = () => {
                    clearInterval(interval);
                    terminateYoloPipeline();
                    modal.hide();
                };
            }
        });
    }

    // Terminate YOLO pipeline
    function terminateYoloPipeline() {
        appUtils.apiCall('/api/yolo/shutdown', 'POST')
            .then(response => {
                if (response.success) {
                    appUtils.showToast('YOLO pipeline terminated', 'success');
                } else {
                    appUtils.showToast('Failed to terminate YOLO pipeline', 'danger');
                }
            })
            .catch(error => {
                appUtils.showToast('Error terminating YOLO: ' + error.message, 'danger');
            });
    }
});
