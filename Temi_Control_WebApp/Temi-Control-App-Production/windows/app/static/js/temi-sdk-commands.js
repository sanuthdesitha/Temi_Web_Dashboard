/**
 * Temi SDK Commands Helper
 * Simplifies sending MQTT commands to Temi robot via SDK
 */

class TemiSDKCommands {
    constructor(robotSerial) {
        this.serial = robotSerial;
        this.baseUrl = '/api/mqtt/publish';
        this.baseTopic = `temi/${robotSerial}/command`;
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

        try {
            console.log(`[TemiSDK] Sending command: ${topic}`, payload);

            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, payload })
            });

            console.log(`[TemiSDK] Response status: ${response.status}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log(`[TemiSDK] Response result:`, result);

            if (!result.success) {
                const error = result.error || 'Unknown error';
                console.error(`[TemiSDK] Command failed: ${error}`);
                if (typeof toastr !== 'undefined') {
                    toastr.error(`Failed to send command: ${error}`);
                } else {
                    alert(`Failed to send command: ${error}`);
                }
            } else {
                console.log(`[TemiSDK] Command sent successfully: ${category}/${action}`);
                if (typeof toastr !== 'undefined') {
                    toastr.success(`${category}/${action} sent`);
                } else {
                    alert(`Command sent: ${category}/${action}`);
                }
            }

            return result;
        } catch (error) {
            console.error(`[TemiSDK] Error sending command:`, error);
            if (typeof toastr !== 'undefined') {
                toastr.error(`Error: ${error.message}`);
            } else {
                alert(`Error: ${error.message}`);
            }
            throw error;
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
