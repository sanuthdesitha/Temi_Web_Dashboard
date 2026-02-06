/**
 * Position Tracker - Real-time robot position visualization
 * Displays robot positions on a 2D canvas with trail history
 */

class PositionTracker {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error(`Canvas with id '${canvasId}' not found`);
            return;
        }

        this.ctx = this.canvas.getContext('2d');
        this.scale = 50; // pixels per meter
        this.minScale = 10;
        this.maxScale = 120;
        this.viewPadding = 40;
        this.centerX = this.canvas.width / 2;
        this.centerY = this.canvas.height / 2;
        this.manualCalibration = null;

        // Position data
        this.currentPositions = {}; // robot_id -> {x, y, theta, timestamp}
        this.trails = {}; // robot_id -> [{x, y, timestamp}, ...]
        this.maxTrailLength = 100;
        this.backgroundImage = null;
        this.waypoints = {}; // robot_id -> [{name,x,y,theta}]

        // Visualization settings
        this.robotColors = {
            1: '#00C9FF', // Nokia cyan (primary robot)
            2: '#FF5722', // Orange (secondary)
            3: '#4CAF50', // Green
            4: '#9C27B0'  // Purple
        };

        this.setupEventListeners();
        this.draw();
    }

    setupEventListeners() {
        if (this.canvas) {
            // Handle canvas resize
            window.addEventListener('resize', () => {
                this.fitViewToData();
                this.draw();
            });

            // Optional: Add click handler to draw zones or waypoints
            this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
        }
    }

    /**
     * Update robot position
     * @param {number} robotId - Robot ID
     * @param {number} x - X coordinate (meters)
     * @param {number} y - Y coordinate (meters)
     * @param {number} theta - Heading angle (degrees)
     * @param {number} timestamp - Unix timestamp (milliseconds)
     */
    updatePosition(robotId, x, y, theta, timestamp = null) {
        if (!timestamp) {
            timestamp = Date.now();
        }

        const normalizedTheta = this.normalizeTheta(theta);

        // Update current position
        this.currentPositions[robotId] = {
            x: parseFloat(x),
            y: parseFloat(y),
            theta: normalizedTheta,
            timestamp: timestamp
        };

        // Add to trail
        if (!this.trails[robotId]) {
            this.trails[robotId] = [];
        }

        this.trails[robotId].push({
            x: parseFloat(x),
            y: parseFloat(y),
            timestamp: timestamp
        });

        // Trim trail to max length
        if (this.trails[robotId].length > this.maxTrailLength) {
            this.trails[robotId].shift();
        }

        this.fitViewToData();
        this.draw();
    }

    /**
     * Adjust scale and center so all positions stay in view
     */
    fitViewToData() {
        if (this.manualCalibration) {
            return;
        }
        let minX = null, maxX = null, minY = null, maxY = null;

        const considerPoint = (x, y) => {
            if (minX === null || x < minX) minX = x;
            if (maxX === null || x > maxX) maxX = x;
            if (minY === null || y < minY) minY = y;
            if (maxY === null || y > maxY) maxY = y;
        };

        for (const robotId in this.currentPositions) {
            const pos = this.currentPositions[robotId];
            if (pos) considerPoint(pos.x, pos.y);
        }

        for (const robotId in this.trails) {
            const trail = this.trails[robotId] || [];
            for (let i = 0; i < trail.length; i++) {
                considerPoint(trail[i].x, trail[i].y);
            }
        }

        for (const robotId in this.waypoints) {
            const list = this.waypoints[robotId] || [];
            for (let i = 0; i < list.length; i++) {
                considerPoint(list[i].x, list[i].y);
            }
        }

        if (minX === null || maxX === null || minY === null || maxY === null) {
            return;
        }

        const rangeX = Math.max(0.1, maxX - minX);
        const rangeY = Math.max(0.1, maxY - minY);
        const availableW = Math.max(1, this.canvas.width - this.viewPadding * 2);
        const availableH = Math.max(1, this.canvas.height - this.viewPadding * 2);
        const scaleX = availableW / rangeX;
        const scaleY = availableH / rangeY;
        const nextScale = Math.min(this.maxScale, Math.max(this.minScale, Math.min(scaleX, scaleY)));

        this.scale = nextScale;
        this.centerX = this.viewPadding + (minX + maxX) / 2 * this.scale;
        this.centerY = this.viewPadding + (maxY + minY) / 2 * -this.scale;

        // Recenter based on canvas if computed center is off
        const targetCenterX = this.canvas.width / 2;
        const targetCenterY = this.canvas.height / 2;
        const worldCenterX = (minX + maxX) / 2;
        const worldCenterY = (minY + maxY) / 2;
        this.centerX = targetCenterX - worldCenterX * this.scale;
        this.centerY = targetCenterY + worldCenterY * this.scale;
    }

    /**
     * Draw the position map
     */
    draw() {
        if (!this.ctx) return;

        // Clear canvas
        this.ctx.fillStyle = '#FFFFFF';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        if (this.backgroundImage) {
            try {
                this.ctx.globalAlpha = 0.9;
                this.ctx.drawImage(this.backgroundImage, 0, 0, this.canvas.width, this.canvas.height);
                this.ctx.globalAlpha = 1.0;
            } catch (e) {
                // Ignore draw errors
            }
        }

        // Draw grid
        this.drawGrid();

        // Draw waypoint zones (if any)
        this.drawWaypoints();

        // Draw all robot trails
        for (const robotId in this.trails) {
            this.drawTrail(robotId);
        }

        // Draw all robot positions
        for (const robotId in this.currentPositions) {
            this.drawRobot(robotId);
        }

        // Draw axes
        this.drawAxes();

        // Draw scale legend
        this.drawScaleLegend();
    }

    /**
     * Draw grid overlay
     */
    drawGrid() {
        this.ctx.strokeStyle = '#E0E0E0';
        this.ctx.lineWidth = 1;

        // Vertical lines (1 meter spacing)
        for (let x = this.centerX % this.scale; x < this.canvas.width; x += this.scale) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, this.canvas.height);
            this.ctx.stroke();
        }

        // Horizontal lines (1 meter spacing)
        for (let y = this.centerY % this.scale; y < this.canvas.height; y += this.scale) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(this.canvas.width, y);
            this.ctx.stroke();
        }
    }

    /**
     * Draw coordinate axes
     */
    drawAxes() {
        this.ctx.strokeStyle = '#000000';
        this.ctx.lineWidth = 2;

        // X axis (horizontal)
        this.ctx.beginPath();
        this.ctx.moveTo(0, this.centerY);
        this.ctx.lineTo(this.canvas.width, this.centerY);
        this.ctx.stroke();

        // Y axis (vertical)
        this.ctx.beginPath();
        this.ctx.moveTo(this.centerX, 0);
        this.ctx.lineTo(this.centerX, this.canvas.height);
        this.ctx.stroke();

        // Draw labels
        this.ctx.fillStyle = '#000000';
        this.ctx.font = '12px Arial';
        this.ctx.fillText('0', this.centerX + 5, this.centerY - 5);
    }

    /**
     * Draw scale legend
     */
    drawScaleLegend() {
        const legendX = 20;
        const legendY = 20;
        const legendSize = this.scale; // 1 meter

        // Draw legend box
        this.ctx.strokeStyle = '#000000';
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(legendX, legendY, legendSize, legendSize);

        // Label
        this.ctx.fillStyle = '#000000';
        this.ctx.font = '12px Arial';
        this.ctx.fillText('1m', legendX + legendSize + 5, legendY + legendSize / 2);
    }

    /**
     * Draw position trail for robot
     * @param {number} robotId - Robot ID
     */
    drawTrail(robotId) {
        const trail = this.trails[robotId];
        if (!trail || trail.length < 2) return;

        const color = this.robotColors[robotId] || '#999999';

        // Draw trail line
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = 1;
        this.ctx.globalAlpha = 0.5;

        this.ctx.beginPath();
        for (let i = 0; i < trail.length; i++) {
            const screenX = this.centerX + trail[i].x * this.scale;
            const screenY = this.centerY - trail[i].y * this.scale;

            if (i === 0) {
                this.ctx.moveTo(screenX, screenY);
            } else {
                this.ctx.lineTo(screenX, screenY);
            }
        }
        this.ctx.stroke();

        // Draw trail points (fade effect)
        this.ctx.globalAlpha = 1.0;
        for (let i = 0; i < trail.length; i++) {
            const alpha = (i / trail.length) * 0.6; // Fade older points
            this.ctx.globalAlpha = alpha;

            const screenX = this.centerX + trail[i].x * this.scale;
            const screenY = this.centerY - trail[i].y * this.scale;

            this.ctx.fillStyle = color;
            this.ctx.beginPath();
            this.ctx.arc(screenX, screenY, 2, 0, 2 * Math.PI);
            this.ctx.fill();
        }

        this.ctx.globalAlpha = 1.0;
    }

    /**
     * Draw robot at current position
     * @param {number} robotId - Robot ID
     */
    drawRobot(robotId) {
        const pos = this.currentPositions[robotId];
        if (!pos) return;

        const screenX = this.centerX + pos.x * this.scale;
        const screenY = this.centerY - pos.y * this.scale;
        const color = this.robotColors[robotId] || '#999999';

        // Save context state
        this.ctx.save();
        this.ctx.translate(screenX, screenY);
        this.ctx.rotate((-pos.theta * Math.PI) / 180); // Negate for correct direction

        // Draw robot body (triangle)
        this.ctx.fillStyle = color;
        this.ctx.beginPath();
        this.ctx.moveTo(15, 0); // Front point
        this.ctx.lineTo(-10, 10); // Right rear
        this.ctx.lineTo(-10, -10); // Left rear
        this.ctx.closePath();
        this.ctx.fill();

        // Draw robot outline
        this.ctx.strokeStyle = '#000000';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();

        // Draw heading indicator (line forward)
        this.ctx.strokeStyle = '#000000';
        this.ctx.lineWidth = 1;
        this.ctx.beginPath();
        this.ctx.moveTo(0, 0);
        this.ctx.lineTo(20, 0);
        this.ctx.stroke();

        // Restore context state
        this.ctx.restore();

        // Draw robot ID label
        this.ctx.fillStyle = color;
        this.ctx.font = 'bold 14px Arial';
        this.ctx.fillText(`R${robotId}`, screenX + 15, screenY - 15);

        // Draw position info
        this.ctx.fillStyle = '#000000';
        this.ctx.font = '11px Arial';
        this.ctx.fillText(`(${pos.x.toFixed(1)}, ${pos.y.toFixed(1)})`, screenX - 20, screenY + 20);
    }

    /**
     * Draw waypoint zones
     */
    drawWaypoints() {
        this.ctx.save();
        this.ctx.font = '11px Arial';
        this.ctx.textAlign = 'left';
        this.ctx.textBaseline = 'middle';

        Object.keys(this.waypoints).forEach(robotId => {
            const list = this.waypoints[robotId] || [];
            const color = this.robotColors[robotId] || '#555555';

            list.forEach((wp, idx) => {
                if (typeof wp.x !== 'number' || typeof wp.y !== 'number') return;
                const screenX = this.centerX + wp.x * this.scale;
                const screenY = this.centerY - wp.y * this.scale;

                this.ctx.fillStyle = '#FFFFFF';
                this.ctx.strokeStyle = color;
                this.ctx.lineWidth = 2;
                this.ctx.beginPath();
                this.ctx.arc(screenX, screenY, 6, 0, 2 * Math.PI);
                this.ctx.fill();
                this.ctx.stroke();

                // Optional heading indicator
                if (wp.theta !== undefined && wp.theta !== null) {
                    const heading = this.normalizeTheta(wp.theta);
                    const angle = (-heading * Math.PI) / 180;
                    const dx = Math.cos(angle) * 10;
                    const dy = Math.sin(angle) * 10;
                    this.ctx.beginPath();
                    this.ctx.moveTo(screenX, screenY);
                    this.ctx.lineTo(screenX + dx, screenY + dy);
                    this.ctx.stroke();
                }

                const label = wp.name || `WP${idx + 1}`;
                this.ctx.fillStyle = color;
                this.ctx.fillText(label, screenX + 10, screenY - 8);
            });
        });

        this.ctx.restore();
    }

    /**
     * Handle canvas click (for future features like markers, zones)
     * @param {MouseEvent} event - Click event
     */
    handleCanvasClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        const canvasX = event.clientX - rect.left;
        const canvasY = event.clientY - rect.top;

        // Convert screen coordinates to world coordinates
        const worldX = (canvasX - this.centerX) / this.scale;
        const worldY = (this.centerY - canvasY) / this.scale;

        console.log(`Clicked at world position: (${worldX.toFixed(2)}, ${worldY.toFixed(2)})`);
    }

    normalizeTheta(theta) {
        const value = parseFloat(theta);
        if (Number.isNaN(value)) return 0;
        const absVal = Math.abs(value);
        if (absVal <= (Math.PI * 2 + 0.5)) {
            return (value * 180) / Math.PI;
        }
        return value;
    }

    setWaypoints(robotId, waypoints) {
        if (!robotId) return;
        if (!Array.isArray(waypoints)) {
            this.waypoints[robotId] = [];
            this.draw();
            return;
        }
        this.waypoints[robotId] = waypoints.map(wp => ({
            name: wp.name || wp.waypoint_name || wp.location || wp.id || 'waypoint',
            x: Number(wp.x),
            y: Number(wp.y),
            theta: wp.theta
        })).filter(wp => !Number.isNaN(wp.x) && !Number.isNaN(wp.y));
        this.fitViewToData();
        this.draw();
    }

    /**
     * Export trajectory as data URL for download
     * @returns {string} Data URL
     */
    exportAsImage() {
        return this.canvas.toDataURL('image/png');
    }

    /**
     * Clear all position data
     */
    clear() {
        this.currentPositions = {};
        this.trails = {};
        this.draw();
    }

    setBackgroundImage(url) {
        if (!url) {
            this.backgroundImage = null;
            this.draw();
            return;
        }
        const img = new Image();
        img.onload = () => {
            this.backgroundImage = img;
            this.draw();
        };
        img.onerror = () => {
            this.backgroundImage = null;
            this.draw();
        };
        img.src = url;
    }

    setManualCalibration(scale, originX, originY) {
        if (!scale || scale <= 0) {
            this.manualCalibration = null;
            return;
        }
        this.manualCalibration = { scale, originX, originY };
        this.scale = scale;
        this.centerX = this.canvas.width / 2 + originX;
        this.centerY = this.canvas.height / 2 + originY;
        this.draw();
    }

    /**
     * Get all current positions
     * @returns {Object} Map of robot_id -> position
     */
    getPositions() {
        return Object.assign({}, this.currentPositions);
    }

    /**
     * Get trail for specific robot
     * @param {number} robotId - Robot ID
     * @returns {Array} Trail points
     */
    getTrail(robotId) {
        return this.trails[robotId] ? [...this.trails[robotId]] : [];
    }
}

// Global instance for use in HTML
let positionTracker = null;

/**
 * Initialize position tracker (call after DOM is ready)
 * @param {string} canvasId - Canvas element ID
 */
function initPositionTracker(canvasId = 'positionCanvas') {
    positionTracker = new PositionTracker(canvasId);
    return positionTracker;
}
