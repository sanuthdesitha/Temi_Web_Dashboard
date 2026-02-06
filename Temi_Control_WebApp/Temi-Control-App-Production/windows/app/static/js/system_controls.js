/**
 * System Controls Module
 * Handles volume control, restart, and shutdown operations
 */

class SystemControls {
    constructor() {
        this.currentRobotId = null;
        this.isUpdating = false;
        this.init();
    }

    init() {
        this.attachEventListeners();
        this.monitorRobotSelection();
        this.monitorSocketEvents();
    }

    attachEventListeners() {
        // Volume slider
        const volumeSlider = document.getElementById('volumeSlider');
        if (volumeSlider) {
            volumeSlider.addEventListener('input', (e) => this.updateVolumeDisplay(e.target.value));
            volumeSlider.addEventListener('change', () => this.setVolume());
        }

        // Quick volume buttons
        document.querySelectorAll('.quick-volume').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const volume = parseInt(e.currentTarget.dataset.volume, 10);
                document.getElementById('volumeSlider').value = volume;
                this.updateVolumeDisplay(volume);
                this.setVolume();
            });
        });

        // Set volume button
        const setVolumeBtn = document.getElementById('setVolumeBtn');
        if (setVolumeBtn) {
            setVolumeBtn.addEventListener('click', () => this.setVolume());
        }

        // System control buttons
        const restartBtn = document.getElementById('restartRobotBtn');
        if (restartBtn) {
            restartBtn.addEventListener('click', () => this.showRestartConfirm());
        }

        const shutdownBtn = document.getElementById('shutdownRobotBtn');
        if (shutdownBtn) {
            shutdownBtn.addEventListener('click', () => this.showShutdownConfirm());
        }
    }

    monitorRobotSelection() {
        const robotSelect = document.getElementById('selectedRobotId');
        if (robotSelect) {
            robotSelect.addEventListener('change', (e) => {
                this.currentRobotId = parseInt(e.target.value, 10) || null;
                if (this.currentRobotId) {
                    this.loadRobotVolume();
                }
            });
        }
    }

    monitorSocketEvents() {
        if (!window.socket) return;

        window.socket.on('volume_changed', (data) => {
            if (data.robot_id == this.currentRobotId) {
                this.updateVolumeDisplay(data.volume);
            }
        });

        window.socket.on('robot_restarting', (data) => {
            if (data.robot_id == this.currentRobotId) {
                this.showRestartProgress(data);
            }
        });

        window.socket.on('robot_restarted', (data) => {
            if (data.robot_id == this.currentRobotId) {
                appUtils.showToast(data.message, 'success');
                this.disableSystemButtons(false);
            }
        });

        window.socket.on('robot_restart_timeout', (data) => {
            if (data.robot_id == this.currentRobotId) {
                appUtils.showToast(data.message, 'danger');
                this.disableSystemButtons(false);
            }
        });

        window.socket.on('robot_shutting_down', (data) => {
            if (data.robot_id == this.currentRobotId) {
                appUtils.showToast(data.message, 'warning');
                this.disableSystemButtons(true);
            }
        });
    }

    updateVolumeDisplay(volume) {
        const volumeValue = document.getElementById('volumeValue');
        if (volumeValue) {
            volumeValue.textContent = volume + '%';
        }
    }

    loadRobotVolume() {
        if (!this.currentRobotId) return;

        fetch(`/api/robots/${this.currentRobotId}/volume`)
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('volumeSlider').value = data.volume;
                    this.updateVolumeDisplay(data.volume);
                }
            })
            .catch(error => console.error('Error loading volume:', error));
    }

    async setVolume() {
        if (!this.currentRobotId) {
            appUtils.showToast('Please select a robot first', 'warning');
            return;
        }

        if (this.isUpdating) return;

        const volume = parseInt(document.getElementById('volumeSlider').value, 10);

        this.isUpdating = true;
        document.getElementById('setVolumeBtn').disabled = true;

        try {
            const response = await fetch('/api/command/volume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    robot_id: this.currentRobotId,
                    volume: volume
                })
            });

            const result = await response.json();

            if (result.success) {
                appUtils.showToast(`Volume set to ${volume}%`, 'success');
            } else {
                appUtils.showToast(`Error: ${result.error}`, 'danger');
                // Revert slider
                this.loadRobotVolume();
            }
        } catch (error) {
            console.error('Error setting volume:', error);
            appUtils.showToast('Failed to set volume', 'danger');
            this.loadRobotVolume();
        } finally {
            this.isUpdating = false;
            document.getElementById('setVolumeBtn').disabled = false;
        }
    }

    showRestartConfirm() {
        if (!this.currentRobotId) {
            appUtils.showToast('Please select a robot first', 'warning');
            return;
        }

        // Create confirmation modal
        const html = `
            <div class="modal fade" id="confirmRestartModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content border-warning">
                        <div class="modal-header bg-warning text-dark">
                            <h5 class="modal-title">
                                <i class="bi bi-exclamation-triangle"></i> Restart Robot?
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>Restarting the robot will:</p>
                            <ul>
                                <li>Stop any current operation</li>
                                <li>Perform a graceful reboot</li>
                                <li>Take approximately 30 seconds</li>
                                <li>Automatically reconnect when ready</li>
                            </ul>
                            <p class="mb-0"><strong>Do you want to continue?</strong></p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-warning" id="confirmRestartBtn">
                                <i class="bi bi-arrow-clockwise"></i> Restart
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if present
        const existing = document.getElementById('confirmRestartModal');
        if (existing) existing.remove();

        // Add new modal
        document.body.insertAdjacentHTML('beforeend', html);

        const modal = new bootstrap.Modal(document.getElementById('confirmRestartModal'));

        document.getElementById('confirmRestartBtn').addEventListener('click', () => {
            modal.hide();
            this.executeRestart();
        });

        modal.show();

        // Clean up modal after hide
        modal._element.addEventListener('hidden.bs.modal', () => {
            document.getElementById('confirmRestartModal').remove();
        });
    }

    showShutdownConfirm() {
        if (!this.currentRobotId) {
            appUtils.showToast('Please select a robot first', 'warning');
            return;
        }

        // First confirmation
        const html1 = `
            <div class="modal fade" id="confirmShutdownModal1" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content border-danger">
                        <div class="modal-header bg-danger text-white">
                            <h5 class="modal-title">
                                <i class="bi bi-power"></i> Shutdown Robot?
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>Are you sure you want to shutdown the robot?</p>
                            <p class="text-muted">This will power off the device.</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-danger" id="confirmShutdownBtn1">
                                <i class="bi bi-power"></i> Shutdown
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modals
        const existing1 = document.getElementById('confirmShutdownModal1');
        if (existing1) existing1.remove();

        document.body.insertAdjacentHTML('beforeend', html1);

        const modal1 = new bootstrap.Modal(document.getElementById('confirmShutdownModal1'));

        document.getElementById('confirmShutdownBtn1').addEventListener('click', () => {
            modal1.hide();
            this.showShutdownConfirm2();
        });

        modal1.show();

        modal1._element.addEventListener('hidden.bs.modal', () => {
            document.getElementById('confirmShutdownModal1').remove();
        });
    }

    showShutdownConfirm2() {
        // Second confirmation
        const html2 = `
            <div class="modal fade" id="confirmShutdownModal2" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content border-danger">
                        <div class="modal-header bg-danger text-white">
                            <h5 class="modal-title">
                                <i class="bi bi-exclamation-octagon"></i> Confirm Shutdown
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p><strong>This action cannot be undone immediately.</strong></p>
                            <p>The robot will power off and require manual restart.</p>
                            <p class="mb-0 text-danger"><strong>Are you absolutely sure?</strong></p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-danger" id="confirmShutdownBtn2">
                                <i class="bi bi-power"></i> Yes, Shutdown
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', html2);

        const modal2 = new bootstrap.Modal(document.getElementById('confirmShutdownModal2'));

        document.getElementById('confirmShutdownBtn2').addEventListener('click', () => {
            modal2.hide();
            this.executeShutdown();
        });

        modal2.show();

        modal2._element.addEventListener('hidden.bs.modal', () => {
            document.getElementById('confirmShutdownModal2').remove();
        });
    }

    async executeRestart() {
        this.disableSystemButtons(true);
        appUtils.showToast('Sending restart command...', 'info');

        try {
            const response = await fetch('/api/command/system/restart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ robot_id: this.currentRobotId })
            });

            const result = await response.json();

            if (result.success) {
                appUtils.showToast(result.message, 'success');
            } else {
                appUtils.showToast(`Error: ${result.error}`, 'danger');
                this.disableSystemButtons(false);
            }
        } catch (error) {
            console.error('Error restarting:', error);
            appUtils.showToast('Failed to send restart command', 'danger');
            this.disableSystemButtons(false);
        }
    }

    async executeShutdown() {
        this.disableSystemButtons(true);
        appUtils.showToast('Sending shutdown command...', 'info');

        try {
            const response = await fetch('/api/command/system/shutdown', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ robot_id: this.currentRobotId })
            });

            const result = await response.json();

            if (result.success) {
                appUtils.showToast(result.message, 'warning');
                // Don't re-enable buttons - robot is offline
            } else {
                appUtils.showToast(`Error: ${result.error}`, 'danger');
                this.disableSystemButtons(false);
            }
        } catch (error) {
            console.error('Error shutting down:', error);
            appUtils.showToast('Failed to send shutdown command', 'danger');
            this.disableSystemButtons(false);
        }
    }

    showRestartProgress(data) {
        const html = `
            <div class="modal fade" id="restartProgressModal" tabindex="-1" data-bs-backdrop="static">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-info text-white">
                            <h5 class="modal-title">
                                <i class="bi bi-arrow-clockwise"></i> Restarting Robot...
                            </h5>
                        </div>
                        <div class="modal-body">
                            <div class="spinner-border mb-3" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p id="restartMessage">${data.message}</p>
                            <div class="progress mt-3">
                                <div class="progress-bar progress-bar-striped progress-bar-animated"
                                     role="progressbar" style="width: 100%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const existing = document.getElementById('restartProgressModal');
        if (existing) existing.remove();

        document.body.insertAdjacentHTML('beforeend', html);

        const modal = new bootstrap.Modal(document.getElementById('restartProgressModal'));
        modal.show();

        // Countdown
        let countdown = 30;
        const interval = setInterval(() => {
            const msg = document.getElementById('restartMessage');
            if (msg) {
                msg.textContent = `Restarting robot... (${countdown}s remaining)`;
            }
            countdown--;

            if (countdown < 0) {
                clearInterval(interval);
            }
        }, 1000);

        modal._element.addEventListener('hidden.bs.modal', () => {
            clearInterval(interval);
            document.getElementById('restartProgressModal').remove();
        });
    }

    disableSystemButtons(disabled) {
        const restartBtn = document.getElementById('restartRobotBtn');
        const shutdownBtn = document.getElementById('shutdownRobotBtn');

        if (restartBtn) restartBtn.disabled = disabled;
        if (shutdownBtn) shutdownBtn.disabled = disabled;
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.systemControls = new SystemControls();
});
