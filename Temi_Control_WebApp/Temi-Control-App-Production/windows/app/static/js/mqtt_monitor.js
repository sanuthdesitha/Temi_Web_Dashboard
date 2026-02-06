// MQTT monitor page logic
(function() {
    const socket = window.socket || (window.io ? io() : null);
    let allMessages = [];
    let autoScroll = true;
    let pauseUpdates = false;
    let categoryFilter = 'all';

    function getTopicCategory(topic) {
        if (topic.includes('/command/')) return 'command';
        if (topic.includes('/status/')) return 'status';
        if (topic.includes('/event/')) return 'event';
        if (topic.includes('nokia/safety') || topic.includes('yolo') || topic.includes('violations')) return 'yolo';
        return 'other';
    }

    function setSocketBadge(connected) {
        const badge = document.getElementById('socketStatusBadge');
        if (!badge) return;
        badge.textContent = connected ? 'Socket: Connected' : 'Socket: Disconnected';
        badge.className = connected ? 'badge bg-success' : 'badge bg-danger';
    }

    function updateMessageCount() {
        const badge = document.getElementById('messageCountBadge');
        if (badge) badge.textContent = `Messages: ${allMessages.length}`;
    }

    function renderMessages() {
        const robotFilter = document.getElementById('robotFilter').value;
        const topicFilter = document.getElementById('topicFilter').value.toLowerCase();
        const payloadFilter = document.getElementById('payloadFilter').value.toLowerCase();

        const filtered = allMessages.filter(msg => {
            if (robotFilter && msg.robot_id != robotFilter) return false;
            if (topicFilter && !msg.topic.toLowerCase().includes(topicFilter)) return false;
            if (payloadFilter) {
                const payloadStr = JSON.stringify(msg.payload).toLowerCase();
                if (!payloadStr.includes(payloadFilter)) return false;
            }
            if (categoryFilter !== 'all') {
                const cat = getTopicCategory(msg.topic);
                if (cat !== categoryFilter) return false;
            }
            return true;
        });

        const container = document.getElementById('messageContainer');
        if (!container) return;

        if (filtered.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted p-5">
                    <i class="bi bi-inbox" style="font-size: 3rem;"></i>
                    <p class="mt-3">No messages match your filters</p>
                </div>
            `;
            return;
        }

        let html = '';
        filtered.forEach(msg => {
            const timestamp = new Date(msg.timestamp).toLocaleTimeString();
            const payloadStr = JSON.stringify(msg.payload, null, 2);
            let topicType = 'secondary';
            if (msg.topic.includes('status')) topicType = 'info';
            else if (msg.topic.includes('event')) topicType = 'success';
            else if (msg.topic.includes('command')) topicType = 'warning';
            else if (msg.topic.includes('yolo') || msg.topic.includes('safety')) topicType = 'danger';

            html += `
                <div class="message-entry">
                    <div>
                        <span class="message-timestamp">${timestamp}</span>
                        <span class="message-robot ms-3">Robot ${msg.robot_id}</span>
                        <span class="badge bg-${topicType} topic-badge ms-2">${msg.topic}</span>
                    </div>
                    <div class="message-payload">${payloadStr}</div>
                </div>
            `;
        });

        container.innerHTML = html;
        if (autoScroll) {
            container.scrollTop = container.scrollHeight;
        }
    }

    function loadMessageHistory() {
        fetch('/api/mqtt/history?limit=50')
            .then(r => r.json())
            .then(response => {
                if (response.success && response.messages) {
                    allMessages = response.messages;
                    updateMessageCount();
                    renderMessages();
                }
            })
            .catch(() => {});
    }

    function loadRobots() {
        fetch('/api/robots')
            .then(r => r.json())
            .then(response => {
                if (response.success && response.robots) {
                    const select = document.getElementById('robotFilter');
                    response.robots.forEach(robot => {
                        const option = document.createElement('option');
                        option.value = robot.id;
                        option.textContent = `Robot ${robot.id} - ${robot.name}`;
                        select.appendChild(option);
                    });
                }
            })
            .catch(() => {});
    }

    function setupHandlers() {
        const clearBtn = document.getElementById('clearBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                if (!confirm('Clear all message history?')) return;
                fetch('/api/mqtt/clear', { method: 'POST' })
                    .then(() => {
                        allMessages = [];
                        updateMessageCount();
                        renderMessages();
                    });
            });
        }

        document.getElementById('autoScrollSwitch').addEventListener('change', function() {
            autoScroll = this.checked;
        });

        document.getElementById('pauseUpdatesSwitch').addEventListener('change', function() {
            pauseUpdates = this.checked;
        });

        ['robotFilter', 'topicFilter', 'payloadFilter'].forEach(id => {
            document.getElementById(id).addEventListener('input', renderMessages);
            document.getElementById(id).addEventListener('change', renderMessages);
        });

        const categoryGroup = document.getElementById('topicCategoryGroup');
        if (categoryGroup) {
            categoryGroup.addEventListener('click', function(e) {
                const btn = e.target.closest('button[data-category]');
                if (!btn) return;
                categoryFilter = btn.dataset.category;
                categoryGroup.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderMessages();
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

        socket.on('mqtt_message', function(message) {
            if (pauseUpdates) return;
            allMessages.unshift(message);
            if (allMessages.length > 200) {
                allMessages = allMessages.slice(0, 200);
            }
            updateMessageCount();
            renderMessages();
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        setupHandlers();
        loadMessageHistory();
        loadRobots();
        attachSocketHandlers();
    });
})();
