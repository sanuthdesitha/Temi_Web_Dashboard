// YOLO monitor page logic
(function() {
    const socket = window.socket || (window.io ? io() : null);

    const yoloEnabledSwitch = document.getElementById('yoloEnabledSwitch');
    const yoloStatusText = document.getElementById('yoloStatusText');
    const yoloEnabledBadge = document.getElementById('yoloEnabledBadge');
    const lastMessageBadge = document.getElementById('lastMessageBadge');
    const socketStatusBadge = document.getElementById('socketStatusBadge');

    let yoloEnabled = true;
    let yoloMessages = [];

    function setSocketBadge(connected) {
        if (!socketStatusBadge) return;
        socketStatusBadge.textContent = connected ? 'Socket: Connected' : 'Socket: Disconnected';
        socketStatusBadge.className = connected ? 'badge bg-success' : 'badge bg-danger';
    }

    function setYoloEnabledUI(enabled) {
        yoloEnabled = enabled;
        if (yoloEnabledSwitch) {
            yoloEnabledSwitch.checked = enabled;
        }
        if (yoloStatusText) {
            yoloStatusText.textContent = enabled ? 'Enabled' : 'Disabled';
            yoloStatusText.parentElement.classList.remove('text-danger', 'text-success');
            yoloStatusText.parentElement.classList.add(enabled ? 'text-success' : 'text-danger');
        }
        if (yoloEnabledBadge) {
            yoloEnabledBadge.classList.toggle('bg-info', enabled);
            yoloEnabledBadge.classList.toggle('bg-secondary', !enabled);
            yoloEnabledBadge.textContent = enabled ? 'YOLO Enabled' : 'YOLO Disabled';
        }
    }

    function updateViewport(name, count, max) {
        const value = document.getElementById(`${name}Violations`);
        const bar = document.getElementById(`${name}Progress`);
        if (value) value.textContent = count;
        if (bar) {
            const pct = max > 0 ? (count / max) * 100 : 0;
            bar.style.width = `${pct}%`;
        }
    }

    function updateYoloStatus(data) {
        const totalViolations = data.total_violations || 0;
        const totalPeople = data.total_people || 0;
        const viewports = data.viewports || {};

        const totalViolationsEl = document.getElementById('totalViolations');
        const totalPeopleEl = document.getElementById('totalPeople');
        if (totalViolationsEl) totalViolationsEl.textContent = totalViolations;
        if (totalPeopleEl) totalPeopleEl.textContent = totalPeople;

        const maxViolations = Math.max(
            viewports.front || 0,
            viewports.right || 0,
            viewports.back || 0,
            viewports.left || 0,
            1
        );

        updateViewport('front', viewports.front || 0, maxViolations);
        updateViewport('right', viewports.right || 0, maxViolations);
        updateViewport('back', viewports.back || 0, maxViolations);
        updateViewport('left', viewports.left || 0, maxViolations);

        if (data.last_message_time && lastMessageBadge) {
            const lastTime = new Date(data.last_message_time);
            const now = new Date();
            const diffSeconds = Math.floor((now - lastTime) / 1000);
            lastMessageBadge.textContent = `Last Message: ${diffSeconds}s ago`;
        }
    }

    function renderYoloMessages() {
        const container = document.getElementById('yoloMessageContainer');
        const countBadge = document.getElementById('yoloMessageCount');
        if (!container) return;

        if (yoloMessages.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted p-5">
                    <i class="bi bi-inbox" style="font-size: 3rem;"></i>
                    <p class="mt-3">No YOLO messages yet...</p>
                </div>
            `;
            if (countBadge) countBadge.textContent = 'Messages: 0';
            return;
        }

        let html = '';
        yoloMessages.forEach(msg => {
            const timestamp = new Date(msg.timestamp).toLocaleTimeString();
            const payloadStr = JSON.stringify(msg.payload, null, 2);
            html += `
                <div style="border-bottom: 1px solid #333; padding: 10px 15px;">
                    <div>
                        <span style="color: #858585; font-weight: bold;">${timestamp}</span>
                        <span class="badge bg-danger ms-2" style="font-size: 11px;">${msg.topic}</span>
                    </div>
                    <div style="color: #d4d4d4; background-color: #252526; padding: 8px; border-radius: 4px; margin-top: 5px; white-space: pre-wrap; word-wrap: break-word; max-height: 200px; overflow-y: auto;">${payloadStr}</div>
                </div>
            `;
        });

        container.innerHTML = html;
        if (countBadge) countBadge.textContent = `Messages: ${yoloMessages.length}`;
    }

    function loadYoloStatus() {
        fetch('/api/yolo/status')
            .then(r => r.json())
            .then(response => {
                if (response.success && response.yolo) {
                    setYoloEnabledUI(response.yolo.enabled);
                    if (!response.yolo.enabled) {
                        // Force enable by default if disabled
                        fetch('/api/yolo/enable', { method: 'POST' }).then(() => setYoloEnabledUI(true));
                    }
                    updateYoloStatus(response.yolo);
                }
            })
            .catch(() => {});
    }

    function loadYoloTopics() {
        fetch('/api/yolo/topics')
            .then(r => r.json())
            .then(response => {
                if (response.success && response.topics) {
                    const textarea = document.getElementById('yoloTopics');
                    if (textarea) textarea.value = response.topics.join('\n');
                }
            })
            .catch(() => {});
    }

    function loadYoloHistory() {
        fetch('/api/yolo/history?limit=50')
            .then(r => r.json())
            .then(response => {
                if (response.success && response.messages) {
                    yoloMessages = response.messages;
                    renderYoloMessages();
                }
            })
            .catch(() => {});
    }

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

    function addCacheBuster(url) {
        if (!url) return url;
        const separator = url.includes('?') ? '&' : '?';
        return `${url}${separator}t=${Date.now()}`;
    }

    function startStream(url) {
        const img = document.getElementById('yoloStreamImg');
        if (!img) return;
        const streamUrl = ensureStreamPath(normalizeStreamUrl(url));
        if (!streamUrl) return;
        const proxyUrl = `/api/stream?url=${encodeURIComponent(streamUrl)}`;
        img.src = addCacheBuster(proxyUrl);
        img.dataset.streamUrl = streamUrl;
    }

    function stopStream() {
        const img = document.getElementById('yoloStreamImg');
        if (!img) return;
        img.removeAttribute('src');
    }

    function loadStreamUrl() {
        const img = document.getElementById('yoloStreamImg');
        if (!img) return;

        fetch('/api/settings')
            .then(r => r.json())
            .then(response => {
                if (!response.success || !response.settings) return;
                const url = normalizeStreamUrl(
                    response.settings.yolo_stream_url || 'http://192.168.18.135:8080'
                );
                if (url) startStream(url);
            })
            .catch(() => {});
    }

    function saveTopics() {
        const textarea = document.getElementById('yoloTopics');
        const topics = (textarea ? textarea.value : '')
            .split('\n')
            .map(t => t.trim())
            .filter(Boolean);
        if (topics.length === 0) return;
        fetch('/api/yolo/topics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topics })
        })
            .then(r => r.json())
            .then(response => {
                if (response.success) {
                    alert('Topics saved and monitor reconnected');
                }
            });
    }

    function resetTopics() {
        const defaults = [
            'nokia/safety/violations/summary',
            'nokia/safety/violations/counts',
            'nokia/safety/violations/new'
        ];
        const textarea = document.getElementById('yoloTopics');
        if (textarea) textarea.value = defaults.join('\n');
    }

    // ==========================================
    // Pipeline Control via Cloud MQTT
    // ==========================================

    let pendingPipelineCommand = null;
    let pipelineState = 'unknown'; // unknown, running, paused, stopped

    function setPipelineStatusUI(state) {
        pipelineState = state;
        const badge = document.getElementById('pipelineStatusBadge');
        if (!badge) return;

        const stateMap = {
            'running':  { text: 'Pipeline: Running',  cls: 'bg-success' },
            'paused':   { text: 'Pipeline: Paused',   cls: 'bg-warning text-dark' },
            'stopped':  { text: 'Pipeline: Stopped',  cls: 'bg-danger' },
            'unknown':  { text: 'Pipeline: Unknown',  cls: 'bg-secondary' }
        };

        const info = stateMap[state] || stateMap['unknown'];
        badge.textContent = info.text;
        badge.className = 'badge ' + info.cls;
    }

    function showPipelineResult(message, isSuccess) {
        const container = document.getElementById('pipelineCommandResult');
        const alertEl = document.getElementById('pipelineCommandAlert');
        const msg = document.getElementById('pipelineCommandMessage');
        if (!container || !alertEl || !msg) return;

        msg.textContent = message;
        alertEl.className = 'alert py-1 px-2 mb-0 ' + (isSuccess ? 'alert-success' : 'alert-danger');
        container.style.display = 'block';

        setTimeout(function() { container.style.display = 'none'; }, 5000);
    }

    function sendPipelineCommand(command) {
        const btnId = 'pipeline' + command.charAt(0).toUpperCase() + command.slice(1) + 'Btn';
        const btn = document.getElementById(btnId);
        if (btn) btn.disabled = true;

        fetch('/api/yolo/pipeline/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: command })
        })
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success) {
                    showPipelineResult('Command "' + command + '" sent successfully via Cloud MQTT', true);
                    if (command === 'start' || command === 'restart') setPipelineStatusUI('running');
                    else if (command === 'pause') setPipelineStatusUI('paused');
                    else if (command === 'stop') setPipelineStatusUI('stopped');
                } else {
                    showPipelineResult(res.error || 'Failed to send command', false);
                }
            })
            .catch(function(err) {
                showPipelineResult('Error: ' + err.message, false);
            })
            .finally(function() {
                if (btn) btn.disabled = false;
            });
    }

    // Commands that require admin password
    const protectedCommands = { stop: true, restart: true };

    function requestPipelineCommand(command) {
        // Start does not need confirmation
        if (command === 'start') {
            sendPipelineCommand(command);
            return;
        }

        // All other commands need confirmation modal
        pendingPipelineCommand = command;

        const titleEl = document.getElementById('pipelineConfirmTitle');
        const msgEl = document.getElementById('pipelineConfirmMessage');
        const headerEl = document.getElementById('pipelineConfirmHeader');
        const pwdSection = document.getElementById('pipelinePasswordSection');
        const pwdInput = document.getElementById('pipelineAdminPassword');
        const pwdError = document.getElementById('pipelinePasswordError');
        const confirmBtn = document.getElementById('pipelineConfirmBtn');

        if (pwdInput) pwdInput.value = '';
        if (pwdError) pwdError.style.display = 'none';

        var commandConfig = {
            stop: {
                title: 'Stop YOLO Pipeline',
                message: 'This will stop the YOLO detection pipeline. The system will not detect violations until restarted.',
                headerClass: 'bg-danger text-white',
                btnClass: 'btn-danger',
                needsPassword: true
            },
            pause: {
                title: 'Pause YOLO Pipeline',
                message: 'This will pause the YOLO detection pipeline. Detection will be suspended until resumed.',
                headerClass: 'bg-warning',
                btnClass: 'btn-warning',
                needsPassword: false
            },
            restart: {
                title: 'Restart YOLO Pipeline',
                message: 'This will restart the YOLO detection pipeline. There may be a brief interruption in detection.',
                headerClass: 'bg-info text-white',
                btnClass: 'btn-info',
                needsPassword: true
            }
        };

        var cfg = commandConfig[command];
        if (!cfg) return;

        if (titleEl) titleEl.textContent = cfg.title;
        if (msgEl) msgEl.textContent = cfg.message;
        if (headerEl) headerEl.className = 'modal-header ' + cfg.headerClass;
        if (confirmBtn) confirmBtn.className = 'btn ' + cfg.btnClass;
        if (pwdSection) pwdSection.style.display = cfg.needsPassword ? 'block' : 'none';

        var modal = new bootstrap.Modal(document.getElementById('pipelineConfirmModal'));
        modal.show();

        if (cfg.needsPassword && pwdInput) {
            setTimeout(function() { pwdInput.focus(); }, 300);
        }
    }

    function executePipelineConfirm() {
        if (!pendingPipelineCommand) return;

        var command = pendingPipelineCommand;
        var needsPassword = protectedCommands[command] || false;
        var pwdInput = document.getElementById('pipelineAdminPassword');
        var pwdError = document.getElementById('pipelinePasswordError');

        if (needsPassword) {
            var password = pwdInput ? pwdInput.value : '';
            if (!password) {
                if (pwdError) {
                    pwdError.textContent = 'Please enter the admin password';
                    pwdError.style.display = 'block';
                }
                return;
            }

            // Verify password server-side then send command
            fetch('/api/verify-admin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: password })
            })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (!data.success) {
                        if (pwdError) {
                            pwdError.textContent = data.error || 'Invalid admin password';
                            pwdError.style.display = 'block';
                        }
                        return;
                    }
                    // Password OK - close modal and send command
                    var modalEl = document.getElementById('pipelineConfirmModal');
                    bootstrap.Modal.getInstance(modalEl).hide();
                    pendingPipelineCommand = null;
                    sendPipelineCommand(command);
                })
                .catch(function(err) {
                    if (pwdError) {
                        pwdError.textContent = 'Failed to verify password';
                        pwdError.style.display = 'block';
                    }
                });
        } else {
            // No password needed - just close and send
            var modalEl = document.getElementById('pipelineConfirmModal');
            bootstrap.Modal.getInstance(modalEl).hide();
            pendingPipelineCommand = null;
            sendPipelineCommand(command);
        }
    }

    function setupHandlers() {
        if (yoloEnabledSwitch) {
            yoloEnabledSwitch.addEventListener('change', function() {
                const endpoint = this.checked ? '/api/yolo/enable' : '/api/yolo/disable';
                fetch(endpoint, { method: 'POST' })
                    .then(() => setYoloEnabledUI(this.checked))
                    .catch(() => {
                        this.checked = !this.checked;
                        setYoloEnabledUI(this.checked);
                    });
            });
        }

        const saveBtn = document.getElementById('saveTopicsBtn');
        if (saveBtn) saveBtn.addEventListener('click', saveTopics);
        const loadBtn = document.getElementById('loadTopicsBtn');
        if (loadBtn) loadBtn.addEventListener('click', loadYoloTopics);
        const resetBtn = document.getElementById('resetTopicsBtn');
        if (resetBtn) resetBtn.addEventListener('click', resetTopics);
        const clearBtn = document.getElementById('clearYoloHistoryBtn');
        if (clearBtn) clearBtn.addEventListener('click', function() {
            yoloMessages = [];
            renderYoloMessages();
        });

        const startBtn = document.getElementById('btn-start-stream');
        if (startBtn) startBtn.addEventListener('click', function() {
            const img = document.getElementById('yoloStreamImg');
            if (img && img.dataset.streamUrl) {
                startStream(img.dataset.streamUrl);
                return;
            }
            loadStreamUrl();
        });

        const stopStreamBtn = document.getElementById('btn-stop-stream');
        if (stopStreamBtn) stopStreamBtn.addEventListener('click', stopStream);

        // Pipeline control buttons (Cloud MQTT)
        var pipelineStartBtn = document.getElementById('pipelineStartBtn');
        if (pipelineStartBtn) pipelineStartBtn.addEventListener('click', function() { requestPipelineCommand('start'); });

        var pipelinePauseBtn = document.getElementById('pipelinePauseBtn');
        if (pipelinePauseBtn) pipelinePauseBtn.addEventListener('click', function() { requestPipelineCommand('pause'); });

        var pipelineStopBtn = document.getElementById('pipelineStopBtn');
        if (pipelineStopBtn) pipelineStopBtn.addEventListener('click', function() { requestPipelineCommand('stop'); });

        var pipelineRestartBtn = document.getElementById('pipelineRestartBtn');
        if (pipelineRestartBtn) pipelineRestartBtn.addEventListener('click', function() { requestPipelineCommand('restart'); });

        // Confirm button in modal
        var confirmBtn = document.getElementById('pipelineConfirmBtn');
        if (confirmBtn) confirmBtn.addEventListener('click', executePipelineConfirm);

        // Enter key in password field
        var pwdInput = document.getElementById('pipelineAdminPassword');
        if (pwdInput) {
            pwdInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') executePipelineConfirm();
            });
        }
    }

    function attachSocketHandlers() {
        if (!socket) {
            setSocketBadge(false);
            return;
        }

        setSocketBadge(socket.connected);

        socket.on('connect', () => setSocketBadge(true));
        socket.on('disconnect', () => setSocketBadge(false));

        socket.on('yolo_summary', updateYoloStatus);
        socket.on('yolo_counts', updateYoloStatus);

        socket.on('mqtt_message', function(message) {
            const topic = (message.topic || '').toLowerCase();
            if (message.robot_id === 'CLOUD' &&
                (topic.includes('safety') || topic.includes('violations') || topic.includes('yolo'))) {
                yoloMessages.unshift({
                    timestamp: message.timestamp,
                    topic: message.topic,
                    payload: message.payload
                });
                if (yoloMessages.length > 50) {
                    yoloMessages = yoloMessages.slice(0, 50);
                }
                renderYoloMessages();
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        setYoloEnabledUI(true);
        loadYoloStatus();
        loadYoloTopics();
        loadYoloHistory();
        loadStreamUrl();
        setupHandlers();
        attachSocketHandlers();
        setInterval(loadYoloStatus, 2000);
        setInterval(loadYoloHistory, 5000);
    });
})();
