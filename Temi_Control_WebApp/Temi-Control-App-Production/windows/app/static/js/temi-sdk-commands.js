/**
 * Temi SDK Commands Helper
 * Simplifies sending MQTT commands to Temi robot via SDK
 */

class TemiSDKCommands {
    constructor(robotSerial) {
        this.serial = robotSerial;
        this.baseUrl = '/api/mqtt/publish';
        this.baseTopic = `temi/${robotSerial}/command`;
        this.responseTimeout = 10000; // 10 seconds timeout for robot response
        this._pendingCallbacks = {};  // Track pending response callbacks
    }

    /**
     * Send MQTT command to robot
     * @param {string} category - Command category (system, audio, ui, etc.)
     * @param {string} action - Command action
     * @param {object} payload - Command payload
     * @returns {Promise}
     */
    async send(category, action, payload = {}) {
        const topic = `${this.baseTopic}/${category}/${action}`;
        const commandKey = `${category}/${action}`;

        try {
            console.log(`[TemiSDK] Sending command: ${topic}`, payload);

            // Start response timeout tracking
            this._startResponseTimeout(commandKey);

            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, payload })
            });

            console.log(`[TemiSDK] Response status: ${response.status}`);

            if (!response.ok) {
                this._clearResponseTimeout(commandKey);
                const errorBody = await response.json().catch(() => ({}));
                throw new Error(errorBody.error || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log(`[TemiSDK] Response result:`, result);

            if (!result.success) {
                this._clearResponseTimeout(commandKey);
                const error = result.error || 'Unknown error';
                console.error(`[TemiSDK] Command failed: ${error}`);
                if (typeof toastr !== 'undefined') {
                    toastr.error(`Failed: ${error}`);
                }
            } else {
                console.log(`[TemiSDK] Command published: ${commandKey}`);
                if (typeof toastr !== 'undefined') {
                    toastr.info(`Command sent: ${commandKey} — waiting for robot response...`);
                }
            }

            return result;
        } catch (error) {
            this._clearResponseTimeout(commandKey);
            console.error(`[TemiSDK] Error sending command:`, error);
            if (typeof toastr !== 'undefined') {
                toastr.error(`Error: ${error.message}`);
            }
            throw error;
        }
    }

    /**
     * Start a timeout timer for a command response
     */
    _startResponseTimeout(commandKey) {
        // Clear any existing timeout for this command
        this._clearResponseTimeout(commandKey);

        this._pendingCallbacks[commandKey] = setTimeout(() => {
            console.warn(`[TemiSDK] No response for ${commandKey} after ${this.responseTimeout / 1000}s`);
            if (typeof toastr !== 'undefined') {
                toastr.warning(`No response from robot for: ${commandKey}`);
            }
            // Update the response display
            const responseEl = document.getElementById('responseDisplay');
            if (responseEl && responseEl.textContent === 'Waiting for robot response...') {
                responseEl.textContent = `No response received for: ${commandKey} (timeout after ${this.responseTimeout / 1000}s)`;
            }
            delete this._pendingCallbacks[commandKey];
        }, this.responseTimeout);
    }

    /**
     * Clear a pending response timeout (called when response is received)
     */
    _clearResponseTimeout(commandKey) {
        if (this._pendingCallbacks[commandKey]) {
            clearTimeout(this._pendingCallbacks[commandKey]);
            delete this._pendingCallbacks[commandKey];
        }
    }

    /**
     * Call this when a robot MQTT response is received to clear the timeout
     */
    onResponseReceived(topic) {
        // Extract category/action from response topic
        // Response topics: temi/{serial}/status/{category}/{info}
        const parts = topic.split('/');
        if (parts.length >= 5) {
            const category = parts[3]; // status topic category
            // Try to match against pending commands
            for (const key of Object.keys(this._pendingCallbacks)) {
                if (topic.includes(category)) {
                    this._clearResponseTimeout(key);
                }
            }
        }
    }

    // ====================================
    // SYSTEM COMMANDS
    // ====================================

    async restart() {
        return this.send('system', 'restart', {});
    }

    async shutdown() {
        return this.send('system', 'shutdown', {});
    }

    // ====================================
    // AUDIO COMMANDS
    // ====================================

    async setVolume(level) {
        return this.send('audio', 'setVolume', { level: Math.max(0, Math.min(10, level)) });
    }

    async getVolume() {
        return this.send('audio', 'getVolume', {});
    }

    async cancelAllTts() {
        return this.send('audio', 'cancelTts', {});
    }

    // ====================================
    // UI COMMANDS
    // ====================================

    async showTopBar() {
        return this.send('ui', 'showTopBar', {});
    }

    async hideTopBar() {
        return this.send('ui', 'hideTopBar', {});
    }

    async setHardButtonsDisabled(disabled) {
        return this.send('ui', 'setHardButtonsDisabled', { disabled });
    }

    async isHardButtonsDisabled() {
        return this.send('ui', 'isHardButtonsDisabled', {});
    }

    async toggleNavigationBillboard(disabled) {
        return this.send('ui', 'toggleNavigationBillboard', { disabled });
    }

    async isNavigationBillboardDisabled() {
        return this.send('ui', 'isNavigationBillboardDisabled', {});
    }

    async showAppList() {
        return this.send('ui', 'showAppList', {});
    }

    async setTopBadgeEnabled(enabled) {
        return this.send('ui', 'setTopBadgeEnabled', { enabled });
    }

    async isTopBadgeEnabled() {
        return this.send('ui', 'isTopBadgeEnabled', {});
    }

    // ====================================
    // SENSOR COMMANDS
    // ====================================

    async setCliffDetectionEnabled(enabled) {
        return this.send('sensor', 'setCliffDetectionEnabled', { enabled });
    }

    async isCliffDetectionEnabled() {
        return this.send('sensor', 'isCliffDetectionEnabled', {});
    }

    async hasCliffSensor() {
        return this.send('sensor', 'hasCliffSensor', {});
    }

    async setFrontTOFEnabled(enabled) {
        return this.send('sensor', 'setFrontTOFEnabled', { enabled });
    }

    async isFrontTOFEnabled() {
        return this.send('sensor', 'isFrontTOFEnabled', {});
    }

    async setBackTOFEnabled(enabled) {
        return this.send('sensor', 'setBackTOFEnabled', { enabled });
    }

    async isBackTOFEnabled() {
        return this.send('sensor', 'isBackTOFEnabled', {});
    }

    // ====================================
    // INFO COMMANDS
    // ====================================

    async getBattery() {
        return this.send('info', 'getBattery', {});
    }

    async getSerialNumber() {
        return this.send('info', 'getSerialNumber', {});
    }

    async getRoboxVersion() {
        return this.send('info', 'getRoboxVersion', {});
    }

    async getLauncherVersion() {
        return this.send('info', 'getLauncherVersion', {});
    }

    async getLocations() {
        return this.send('info', 'getLocations', {});
    }

    async getNickName() {
        return this.send('info', 'getNickName', {});
    }

    async isReady() {
        return this.send('info', 'isReady', {});
    }

    // ====================================
    // SETTINGS COMMANDS
    // ====================================

    async setPrivacyMode(enabled) {
        return this.send('settings', 'setPrivacyMode', { enabled });
    }

    async getPrivacyMode() {
        return this.send('settings', 'getPrivacyMode', {});
    }

    async toggleWakeup(disabled) {
        return this.send('settings', 'toggleWakeup', { disabled });
    }

    async isWakeupDisabled() {
        return this.send('settings', 'isWakeupDisabled', {});
    }

    async setAutoReturn(enabled) {
        return this.send('settings', 'setAutoReturn', { enabled });
    }

    async isAutoReturnOn() {
        return this.send('settings', 'isAutoReturnOn', {});
    }

    async setNavigationSafety(level) {
        return this.send('settings', 'setNavigationSafety', { level: level.toUpperCase() });
    }

    async getNavigationSafety() {
        return this.send('settings', 'getNavigationSafety', {});
    }

    async setGoToSpeed(speed) {
        return this.send('settings', 'setGoToSpeed', { speed: speed.toUpperCase() });
    }

    async getGoToSpeed() {
        return this.send('settings', 'getGoToSpeed', {});
    }

    async setMinimumObstacleDistance(distance) {
        return this.send('settings', 'setMinimumObstacleDistance', { distance });
    }

    async getMinimumObstacleDistance() {
        return this.send('settings', 'getMinimumObstacleDistance', {});
    }

    // ====================================
    // MAP COMMANDS
    // ====================================

    async getMapImage(format = 'png', chunkSize = 120000) {
        return this.send('map', 'getImage', { format, chunk_size: chunkSize });
    }

    async getMapData() {
        return this.send('map', 'getData', {});
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TemiSDKCommands;
}
