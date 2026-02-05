# Temi Center Reverse Engineering Analysis
## Implementation Patterns & Architecture Guide

**Date**: 2026-02-05
**Purpose**: Document Temi Center dashboard implementation patterns to guide Temi Control WebApp development

---

## Table of Contents
1. [Dashboard Architecture](#dashboard-architecture)
2. [UI/UX Layout Patterns](#uiux-layout-patterns)
3. [Feature-by-Feature Analysis](#feature-by-feature-analysis)
4. [API Endpoints & Integration](#api-endpoints--integration)
5. [Implementation Recommendations](#implementation-recommendations)
6. [Gap Analysis](#gap-analysis)

---

## Dashboard Architecture

### Overview Structure
The Temi Center dashboard uses a **modular SPA (Single Page Application)** architecture with:

```
┌─────────────────────────────────────────────────────────────┐
│                  Temi Center Dashboard                       │
├─────────────────────────────────────────────────────────────┤
│  Left Sidebar (Navigation)   │    Main Content Area          │
│  ├─ Robot Selection         │    ├─ Status Panel            │
│  ├─ View Options            │    ├─ Map Display (Canvas)    │
│  ├─ Settings                │    ├─ Control Panel           │
│  └─ Logout                  │    └─ Context Menu            │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Components

#### 1. **State Management**
- **Robot Context**: Currently selected robot ID maintained globally
- **Singleton Pattern**: One active robot at a time in dashboard
- **Real-time Sync**: WebSocket/MQTT maintains state across tabs

#### 2. **Responsive Design**
- **Sidebar**: Fixed left panel with collapsible menu (mobile-friendly)
- **Main Content**: Flex layout, adapts to screen size
- **Map Canvas**: Responsive scaling (maintains aspect ratio)

#### 3. **Real-time Data Flow**
```
┌─────────────────┐
│   MQTT Broker   │
│  (HiveMQ Cloud) │
└────────┬────────┘
         │
    ┌────┴─────┬──────────────┬──────────┐
    │           │              │          │
┌───▼──┐  ┌────▼──┐  ┌───────▼┐  ┌────▼──┐
│Status│  │Position│ │Battery│  │Events │
│Topic │  │Topic   │  │Topic  │  │Topic  │
└──┬───┘  └────┬───┘  └───┬───┘  └───┬───┘
   │           │          │          │
   └─────┬─────┴──────┬───┴──────────┘
         │            │
      ┌──▼────────────▼─┐
      │  Dashboard UI   │
      │  (Real-time)    │
      └─────────────────┘
```

---

## UI/UX Layout Patterns

### Primary Dashboard Layout

#### Status Panel (Left Sidebar)
```
┌──────────────────────┐
│   ROBOT INFO         │
├──────────────────────┤
│ Robot ID: Temi-1234  │
│ Name: Robot-Office   │
├──────────────────────┤
│ Status:  ● READY     │
│ Mode:    MANUAL      │
│ Speed:   0.5 m/s     │
│ Battery: 85% 🔋      │
├──────────────────────┤
│ Current Task:        │
│ └─ Idle              │
├──────────────────────┤
│ Controller:          │
│ └─ Not Connected     │
└──────────────────────┘
```

**Implementation in Temi Control WebApp:**
```html
<!-- Status Panel Template -->
<div class="status-panel">
    <div class="robot-info">
        <h3 id="robotName">Robot Name</h3>
        <p>ID: <span id="robotId">-</span></p>
    </div>

    <div class="status-grid">
        <div class="status-item">
            <label>Status</label>
            <span id="robotStatus" class="badge bg-success">Ready</span>
        </div>
        <div class="status-item">
            <label>Mode</label>
            <span id="robotMode">Manual</span>
        </div>
        <div class="status-item">
            <label>Battery</label>
            <div class="battery-bar">
                <div id="batteryLevel" style="width: 85%"></div>
            </div>
            <span id="batteryPercent">85%</span>
        </div>
    </div>

    <div class="current-task">
        <label>Current Task:</label>
        <span id="currentTask">Idle</span>
    </div>
</div>
```

#### Map Display (Center)
```
┌────────────────────────────────┐
│         MAP DISPLAY            │
│  ┌──────────────────────────┐  │
│  │                          │  │
│  │  ◀  X  X  X            │  │
│  │  Robot Position      ⬆  │  │
│  │  [Heading Arrow]     N  │  │
│  │                          │  │
│  │  🚩 Waypoint 1          │  │
│  │  🚩 Waypoint 2          │  │
│  │  🚩 Waypoint 3          │  │
│  │                          │  │
│  └──────────────────────────┘  │
│  [Zoom -] [Zoom +] [Fit]       │
└────────────────────────────────┘
```

**Key Features:**
- Canvas-based rendering (not image overlay)
- Real-time robot position indicator with heading
- Waypoint markers with names
- Zoom controls with fit-to-view
- Click detection for waypoint selection

#### Control Panel (Right/Bottom)
```
┌─────────────────────────┐
│    QUICK CONTROLS       │
├─────────────────────────┤
│ [🎯 Patrol]            │
│ [📍 Go to Waypoint]    │
│ [⏸️  Pause/Resume]     │
│ [🛑 Stop]              │
├─────────────────────────┤
│    ADJUSTMENTS          │
├─────────────────────────┤
│ Volume: [====◆=====] 70% │
│ Speed:  [===◆======]  50%│
├─────────────────────────┤
│    SYSTEM CONTROLS      │
├─────────────────────────┤
│ [🔄 Restart Robot]    │
│ [⏹️  Shutdown]        │
│ [⚙️  Settings]        │
└─────────────────────────┘
```

---

## Feature-by-Feature Analysis

### 1. Map Image Retrieval & Display

#### Temi Center Approach:
```
┌──────────────────────────────────────────┐
│ How Temi Center Gets & Displays Maps     │
├──────────────────────────────────────────┤
│                                          │
│ 1. API Call: GET /api/v2/maps/get/current
│    Response: {                           │
│      "mapId": "map_12345",              │
│      "name": "Office Floor 1",          │
│      "imageUrl": "https://cdn...",      │
│      "dimensions": {                    │
│        "width": 1024,                   │
│        "height": 768,                   │
│        "pixelsPerMeter": 50             │
│      },                                 │
│      "metadata": {                      │
│        "createdAt": "2025-01-15",      │
│        "version": 2.1,                  │
│        "origin": {x: 512, y: 384}      │
│      }                                  │
│    }                                    │
│                                          │
│ 2. Canvas Rendering:                    │
│    - Load image from imageUrl           │
│    - Cache in memory (IndexedDB)        │
│    - Draw on canvas with scaling        │
│    - Overlay waypoints and robot pos    │
│                                          │
│ 3. Real-time Updates:                   │
│    - MQTT: temi/{serial}/status/position
│    - Transform coordinates to canvas    │
│    - Redraw robot position (30 Hz)      │
│    - Smooth animation of movement       │
│                                          │
└──────────────────────────────────────────┘
```

#### Implementation for Temi Control WebApp:

**Backend (app.py):**
```python
# Add endpoint to get current map for robot
@app.route('/api/robots/<int:robot_id>/map/current', methods=['GET'])
def get_current_map(robot_id):
    """Get the current map for a robot"""
    try:
        robot = db.get_robot(robot_id)
        if not robot:
            return jsonify({'error': 'Robot not found'}), 404

        # Get map settings
        map_url = robot.get('map_image_url')
        if not map_url:
            return jsonify({
                'mapId': None,
                'imageUrl': None,
                'message': 'No map uploaded. Use map editor to upload.'
            }), 200

        # Get map metadata from database
        map_metadata = db.get_robot_map_metadata(robot_id)

        return jsonify({
            'success': True,
            'mapId': map_metadata.get('id'),
            'name': map_metadata.get('name', 'Default Map'),
            'imageUrl': map_url,
            'dimensions': {
                'width': map_metadata.get('width', 1024),
                'height': map_metadata.get('height', 768),
                'pixelsPerMeter': map_metadata.get('pixels_per_meter', 50)
            },
            'metadata': {
                'createdAt': map_metadata.get('created_at'),
                'version': map_metadata.get('version', 1.0),
                'origin': {
                    'x': map_metadata.get('origin_x', 512),
                    'y': map_metadata.get('origin_y', 384)
                }
            }
        })
    except Exception as e:
        logger.error(f'Error getting map: {e}')
        return jsonify({'error': str(e)}), 500

# Map upload endpoint
@app.route('/api/robots/<int:robot_id>/map/upload', methods=['POST'])
def upload_robot_map(robot_id):
    """Upload a map image for a robot"""
    try:
        if 'map_image' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['map_image']
        robot = db.get_robot(robot_id)

        if not robot:
            return jsonify({'error': 'Robot not found'}), 404

        # Validate image
        from PIL import Image
        try:
            img = Image.open(file)
            width, height = img.size

            # Only accept PNG or JPG
            if img.format not in ['PNG', 'JPEG']:
                return jsonify({'error': 'Only PNG and JPEG images supported'}), 400
        except Exception as e:
            return jsonify({'error': f'Invalid image file: {e}'}), 400

        # Save map image
        os.makedirs('static/maps', exist_ok=True)
        map_filename = f"map_{robot_id}_{int(time.time())}.png"
        map_path = os.path.join('static/maps', map_filename)

        img.save(map_path, 'PNG')

        # Update database
        map_url = f'/static/maps/{map_filename}'
        db.update_robot(robot_id, map_image_url=map_url)

        # Store metadata
        db.set_robot_map_metadata(robot_id, {
            'width': width,
            'height': height,
            'pixels_per_meter': 50,  # Default, user can adjust
            'origin_x': width // 2,
            'origin_y': height // 2,
            'version': 1.0
        })

        return jsonify({
            'success': True,
            'mapUrl': map_url,
            'dimensions': {'width': width, 'height': height}
        })
    except Exception as e:
        logger.error(f'Error uploading map: {e}')
        return jsonify({'error': str(e)}), 500
```

**Frontend (position_tracking_page.js):**
```javascript
// Enhanced map display with API integration
class MapDisplay {
    constructor(canvasId, robotId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.robotId = robotId;
        this.mapData = null;
        this.robotPosition = { x: 0, y: 0, theta: 0 };
        this.waypoints = [];
        this.isLoading = false;

        this.init();
    }

    async init() {
        await this.loadMapData();
        this.attachSocketListeners();
        this.startRenderLoop();
    }

    async loadMapData() {
        try {
            const response = await fetch(`/api/robots/${this.robotId}/map/current`);
            const data = await response.json();

            if (!data.success || !data.imageUrl) {
                this.renderPlaceholder('No map uploaded');
                return;
            }

            this.mapData = data;

            // Load and cache map image
            const img = new Image();
            img.onload = () => {
                this.mapImage = img;
                this.setupCanvasSize();
                this.render();
            };
            img.onerror = () => this.renderPlaceholder('Failed to load map');
            img.src = data.imageUrl;
        } catch (error) {
            console.error('Error loading map:', error);
            this.renderPlaceholder('Error loading map');
        }
    }

    setupCanvasSize() {
        if (!this.mapData) return;

        const dims = this.mapData.dimensions;
        this.canvas.width = dims.width;
        this.canvas.height = dims.height;

        // Calculate scale for responsive display
        const containerWidth = this.canvas.parentElement.offsetWidth;
        const scale = Math.min(1, containerWidth / dims.width);
        this.canvas.style.width = (dims.width * scale) + 'px';
        this.canvas.style.height = (dims.height * scale) + 'px';
    }

    renderPlaceholder(message) {
        this.ctx.fillStyle = '#f0f0f0';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        this.ctx.fillStyle = '#999';
        this.ctx.font = '16px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(message, this.canvas.width / 2, this.canvas.height / 2);
    }

    attachSocketListeners() {
        if (!window.socket) return;

        window.socket.on('position_update', (data) => {
            if (data.robot_id == this.robotId) {
                this.robotPosition = {
                    x: data.x,
                    y: data.y,
                    theta: data.theta || 0
                };
            }
        });

        window.socket.on('waypoints_update', (data) => {
            if (data.robot_id == this.robotId) {
                this.waypoints = data.waypoints || [];
            }
        });
    }

    startRenderLoop() {
        setInterval(() => this.render(), 33); // ~30 Hz
    }

    render() {
        if (!this.mapImage || !this.mapData) return;

        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw map background
        this.ctx.drawImage(this.mapImage, 0, 0);

        // Draw waypoints
        this.drawWaypoints();

        // Draw robot position and heading
        this.drawRobot();
    }

    drawWaypoints() {
        const ppx = this.mapData.dimensions.pixelsPerMeter;
        const origin = this.mapData.metadata.origin;

        this.waypoints.forEach((wp, index) => {
            // Transform world coordinates to canvas coordinates
            const canvasX = origin.x + wp.x * ppx;
            const canvasY = origin.y - wp.y * ppx; // Flip Y

            // Draw waypoint marker
            this.ctx.fillStyle = index === 0 ? '#ff6b6b' : '#4ecdc4';
            this.ctx.beginPath();
            this.ctx.arc(canvasX, canvasY, 8, 0, Math.PI * 2);
            this.ctx.fill();

            // Draw waypoint name
            this.ctx.fillStyle = '#000';
            this.ctx.font = 'bold 12px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(wp.name, canvasX, canvasY - 15);
        });
    }

    drawRobot() {
        const ppx = this.mapData.dimensions.pixelsPerMeter;
        const origin = this.mapData.metadata.origin;

        // Transform world coordinates to canvas coordinates
        const canvasX = origin.x + this.robotPosition.x * ppx;
        const canvasY = origin.y - this.robotPosition.y * ppx;

        // Draw robot position
        this.ctx.fillStyle = '#3498db';
        this.ctx.beginPath();
        this.ctx.arc(canvasX, canvasY, 10, 0, Math.PI * 2);
        this.ctx.fill();

        // Draw heading arrow
        const arrowLength = 20;
        const headingRad = this.robotPosition.theta * (Math.PI / 180);

        const arrowEndX = canvasX + arrowLength * Math.cos(headingRad);
        const arrowEndY = canvasY - arrowLength * Math.sin(headingRad);

        this.ctx.strokeStyle = '#3498db';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.moveTo(canvasX, canvasY);
        this.ctx.lineTo(arrowEndX, arrowEndY);
        this.ctx.stroke();

        // Draw heading direction label
        this.ctx.fillStyle = '#3498db';
        this.ctx.font = 'bold 11px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(
            Math.round(this.robotPosition.theta) + '°',
            canvasX,
            canvasY + 25
        );
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const robotId = new URLSearchParams(window.location.search).get('robot_id') || 1;
    window.mapDisplay = new MapDisplay('mapCanvas', robotId);
});
```

---

### 2. Volume Control

#### Temi Center Approach:
```
┌──────────────────────────────────────────┐
│ Volume Control Implementation            │
├──────────────────────────────────────────┤
│                                          │
│ UI Component:                            │
│ Volume: [▁▂▃▄▅▆▇█ 70%] 🔊               │
│                                          │
│ On Slider Change:                        │
│ 1. Emit: temi/{serial}/command/volume   │
│    Payload: {"volume": 70}               │
│                                          │
│ 2. Local feedback:                       │
│    - Display percentage                  │
│    - Play test beep (if enabled)         │
│    - Disable slider while setting       │
│                                          │
│ 3. Confirmation:                         │
│    - Listen to status/volume topic       │
│    - Re-enable slider when confirmed     │
│                                          │
│ SDK Limitation Workaround:               │
│ ✓ Uses MQTT command (not direct SDK)    │
│ ✓ Robot applies via Android settings    │
│ ✗ Cannot read current volume from SDK   │
│ → Solution: Store in app state/DB       │
│                                          │
└──────────────────────────────────────────┘
```

#### Implementation for Temi Control WebApp:

**Backend (app.py):**
```python
@app.route('/api/command/volume', methods=['POST'])
def set_volume():
    """Set robot volume via MQTT"""
    try:
        data = request.get_json()
        robot_id = data.get('robot_id')
        volume = int(data.get('volume', 50))

        # Validate range (0-100)
        if volume < 0 or volume > 100:
            return jsonify({'error': 'Volume must be 0-100'}), 400

        robot = db.get_robot(robot_id)
        if not robot or not robot.get('is_connected'):
            return jsonify({'error': 'Robot not connected'}), 503

        # Send MQTT command
        topic = f"temi/{robot['serial']}/command/volume"
        payload = json.dumps({'volume': volume})

        success = mqtt_manager.publish(topic, payload)

        if success:
            # Store in database for state management
            db.set_robot_setting(robot_id, 'volume_level', volume)

            # Log activity
            db.log_activity(
                robot_id=robot_id,
                action='set_volume',
                value=volume,
                user='system'
            )

            emit_socketio('volume_changed', {
                'robot_id': robot_id,
                'volume': volume
            })

            return jsonify({'success': True, 'volume': volume})
        else:
            return jsonify({'error': 'Failed to publish MQTT command'}), 500
    except ValueError:
        return jsonify({'error': 'Invalid volume value'}), 400
    except Exception as e:
        logger.error(f'Error setting volume: {e}')
        return jsonify({'error': str(e)}), 500

# Get current volume setting
@app.route('/api/robots/<int:robot_id>/volume', methods=['GET'])
def get_volume(robot_id):
    """Get robot's volume setting"""
    try:
        volume = db.get_robot_setting(robot_id, 'volume_level', 50)
        return jsonify({'success': True, 'volume': int(volume)})
    except Exception as e:
        logger.error(f'Error getting volume: {e}')
        return jsonify({'error': str(e)}), 500
```

**Frontend (commands.js):**
```javascript
// Volume control component
class VolumeControl {
    constructor(sliderId, displayId, robotId) {
        this.slider = document.getElementById(sliderId);
        this.display = document.getElementById(displayId);
        this.robotId = robotId;
        this.isUpdating = false;

        this.init();
    }

    init() {
        // Load current volume
        this.loadCurrentVolume();

        // Attach event listeners
        this.slider.addEventListener('input', (e) => this.onVolumeChange(e));

        // Listen to remote changes
        if (window.socket) {
            window.socket.on('volume_changed', (data) => {
                if (data.robot_id == this.robotId) {
                    this.updateDisplay(data.volume);
                }
            });
        }
    }

    async loadCurrentVolume() {
        try {
            const response = await fetch(`/api/robots/${this.robotId}/volume`);
            const data = await response.json();

            if (data.success) {
                this.slider.value = data.volume;
                this.updateDisplay(data.volume);
            }
        } catch (error) {
            console.error('Error loading volume:', error);
        }
    }

    async onVolumeChange(event) {
        if (this.isUpdating) return;

        const newVolume = parseInt(event.target.value, 10);
        this.updateDisplay(newVolume);

        // Disable slider during update
        this.slider.disabled = true;
        this.isUpdating = true;

        try {
            const response = await fetch('/api/command/volume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    robot_id: this.robotId,
                    volume: newVolume
                })
            });

            const result = await response.json();

            if (!result.success) {
                appUtils.showToast(`Failed to set volume: ${result.error}`, 'danger');
                await this.loadCurrentVolume(); // Revert
            } else {
                appUtils.showToast(`Volume set to ${newVolume}%`, 'success');
            }
        } catch (error) {
            console.error('Error setting volume:', error);
            appUtils.showToast('Error setting volume', 'danger');
            await this.loadCurrentVolume(); // Revert
        } finally {
            this.slider.disabled = false;
            this.isUpdating = false;
        }
    }

    updateDisplay(volume) {
        this.slider.value = volume;
        this.display.textContent = `${volume}%`;

        // Visual feedback
        const percentage = (volume / 100) * 100;
        this.slider.style.setProperty('--value', percentage + '%');
    }
}

// Initialize volume control
document.addEventListener('DOMContentLoaded', () => {
    const robotId = 1; // Get from page context
    window.volumeControl = new VolumeControl('volumeSlider', 'volumeDisplay', robotId);
});
```

**HTML Template:**
```html
<div class="control-section">
    <label class="control-label">Volume</label>
    <div class="volume-control">
        <input
            type="range"
            id="volumeSlider"
            min="0"
            max="100"
            value="50"
            class="form-range"
        >
        <span id="volumeDisplay">50%</span>
        <i class="bi bi-info-circle" data-bs-toggle="tooltip"
           title="Volume is controlled via Android system settings"></i>
    </div>
</div>
```

**CSS Styling:**
```css
.volume-control {
    display: flex;
    align-items: center;
    gap: 10px;
}

.form-range {
    flex: 1;
    height: 6px;
    cursor: pointer;
}

.form-range::-webkit-slider-thumb {
    width: 18px;
    height: 18px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    cursor: pointer;
    border-radius: 50%;
    border: none;
}

.form-range::-moz-range-thumb {
    width: 18px;
    height: 18px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    cursor: pointer;
    border-radius: 50%;
    border: none;
}
```

---

### 3. Restart & Shutdown Controls

#### Temi Center Approach:
```
┌──────────────────────────────────────────┐
│ Restart / Shutdown Implementation        │
├──────────────────────────────────────────┤
│                                          │
│ UI Pattern:                              │
│ ┌─────────────────────────────────────┐ │
│ │ [⚠️] SYSTEM CONTROLS                │ │
│ ├─────────────────────────────────────┤ │
│ │ [🔄 RESTART ROBOT]                 │ │
│ │ └─ Info: Graceful reboot, ~30s    │ │
│ │                                     │ │
│ │ [⏹️  SHUTDOWN ROBOT]                │ │
│ │ └─ Info: Safe poweroff, notify ops │ │
│ └─────────────────────────────────────┘ │
│                                          │
│ Restart Flow:                            │
│ 1. User clicks Restart button            │
│ 2. Confirmation dialog appears:          │
│    "Restart robot? This will..."        │
│    [Cancel] [Restart]                   │
│ 3. Show countdown (30s shutdown msg)     │
│ 4. Publish to:                          │
│    temi/{serial}/command/system/restart  │
│ 5. Wait for reconnect (with timeout)    │
│ 6. Show success/failure toast            │
│                                          │
│ Shutdown Flow:                           │
│ 1. User clicks Shutdown button           │
│ 2. Confirmation dialog (2-step):        │
│    "Shutdown robot?"                    │
│    "Are you sure? This will power off." │
│    [Cancel] [Shutdown]                  │
│ 3. Publish to:                          │
│    temi/{serial}/command/system/shutdown│
│ 4. Monitor connection status             │
│ 5. Show offline confirmation             │
│                                          │
│ Safety Features:                         │
│ ✓ Confirmation dialogs                  │
│ ✓ Visual warnings (colors)              │
│ ✓ Disable buttons during operation      │
│ ✓ Clear user feedback                   │
│ ✓ Activity logging                      │
│                                          │
└──────────────────────────────────────────┘
```

#### Implementation for Temi Control WebApp:

**Backend (app.py):**
```python
@app.route('/api/command/system/restart', methods=['POST'])
def restart_robot():
    """Restart the robot"""
    try:
        data = request.get_json()
        robot_id = data.get('robot_id')

        robot = db.get_robot(robot_id)
        if not robot or not robot.get('is_connected'):
            return jsonify({'error': 'Robot not connected'}), 503

        # Log this critical action
        db.log_activity(
            robot_id=robot_id,
            action='system_restart',
            severity='critical',
            user='admin'  # Would come from auth context
        )

        # Publish restart command
        topic = f"temi/{robot['serial']}/command/system/restart"
        payload = json.dumps({'action': 'restart', 'timestamp': time.time()})

        success = mqtt_manager.publish(topic, payload)

        if success:
            # Update robot state to "restarting"
            db.set_robot_setting(robot_id, 'state', 'restarting')

            emit_socketio('robot_restarting', {
                'robot_id': robot_id,
                'message': 'Robot is restarting... (approximately 30 seconds)'
            })

            # Background task to monitor reconnection
            from threading import Thread
            Thread(
                target=monitor_robot_restart,
                args=(robot_id, 60),  # 60 second timeout
                daemon=True
            ).start()

            return jsonify({
                'success': True,
                'message': 'Restart command sent. Robot will reconnect in ~30 seconds.'
            })
        else:
            return jsonify({'error': 'Failed to publish restart command'}), 500

    except Exception as e:
        logger.error(f'Error restarting robot: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/command/system/shutdown', methods=['POST'])
def shutdown_robot():
    """Shutdown the robot"""
    try:
        data = request.get_json()
        robot_id = data.get('robot_id')

        robot = db.get_robot(robot_id)
        if not robot:
            return jsonify({'error': 'Robot not found'}), 404

        # Critical action - log with verification
        db.log_activity(
            robot_id=robot_id,
            action='system_shutdown',
            severity='critical',
            ip_address=request.remote_addr,
            user='admin'
        )

        # Publish shutdown command only if connected
        if robot.get('is_connected'):
            topic = f"temi/{robot['serial']}/command/system/shutdown"
            payload = json.dumps({'action': 'shutdown', 'timestamp': time.time()})

            success = mqtt_manager.publish(topic, payload)
        else:
            success = True  # Already offline

        if success:
            # Update state
            db.set_robot_setting(robot_id, 'state', 'shutting_down')

            emit_socketio('robot_shutting_down', {
                'robot_id': robot_id,
                'message': 'Shutdown command sent. Robot is powering off.'
            })

            return jsonify({
                'success': True,
                'message': 'Shutdown initiated. Robot will power off.'
            })
        else:
            return jsonify({'error': 'Failed to publish shutdown command'}), 500

    except Exception as e:
        logger.error(f'Error shutting down robot: {e}')
        return jsonify({'error': str(e)}), 500

def monitor_robot_restart(robot_id, timeout_seconds):
    """Monitor robot for reconnection after restart"""
    import time

    start_time = time.time()
    robot = db.get_robot(robot_id)

    while time.time() - start_time < timeout_seconds:
        time.sleep(5)  # Check every 5 seconds

        # Check if robot reconnected
        current_robot = db.get_robot(robot_id)
        if current_robot and current_robot.get('is_connected'):
            # Update state
            db.set_robot_setting(robot_id, 'state', 'ready')

            emit_socketio('robot_restarted', {
                'robot_id': robot_id,
                'message': 'Robot has successfully restarted and reconnected!'
            })
            return

    # Timeout - robot didn't reconnect
    emit_socketio('robot_restart_failed', {
        'robot_id': robot_id,
        'message': 'Robot did not reconnect after restart. Please check manually.'
    })
```

**Frontend (commands.js):**
```javascript
// System control module
class SystemControls {
    constructor(restartBtnId, shutdownBtnId, robotId) {
        this.restartBtn = document.getElementById(restartBtnId);
        this.shutdownBtn = document.getElementById(shutdownBtnId);
        this.robotId = robotId;

        this.init();
    }

    init() {
        this.restartBtn.addEventListener('click', () => this.showRestartConfirm());
        this.shutdownBtn.addEventListener('click', () => this.showShutdownConfirm());

        // Listen for status updates
        if (window.socket) {
            window.socket.on('robot_restarting', (data) => {
                if (data.robot_id == this.robotId) {
                    this.showRestartProgress(data);
                }
            });

            window.socket.on('robot_restarted', (data) => {
                if (data.robot_id == this.robotId) {
                    appUtils.showToast(data.message, 'success');
                    this.enableButtons();
                }
            });

            window.socket.on('robot_restart_failed', (data) => {
                if (data.robot_id == this.robotId) {
                    appUtils.showToast(data.message, 'danger');
                    this.enableButtons();
                }
            });

            window.socket.on('robot_shutting_down', (data) => {
                if (data.robot_id == this.robotId) {
                    this.disableButtons();
                }
            });
        }
    }

    showRestartConfirm() {
        const modal = new bootstrap.Modal(
            document.getElementById('confirmRestartModal')
        );

        document.getElementById('confirmRestartBtn').onclick = () => {
            modal.hide();
            this.executeRestart();
        };

        modal.show();
    }

    showShutdownConfirm() {
        // Two-step confirmation for safety
        const firstModal = new bootstrap.Modal(
            document.getElementById('confirmShutdownModal1')
        );

        document.getElementById('confirmShutdownBtn1').onclick = () => {
            firstModal.hide();

            // Show second confirmation
            const secondModal = new bootstrap.Modal(
                document.getElementById('confirmShutdownModal2')
            );

            document.getElementById('confirmShutdownBtn2').onclick = () => {
                secondModal.hide();
                this.executeShutdown();
            };

            secondModal.show();
        };

        firstModal.show();
    }

    async executeRestart() {
        this.disableButtons();
        appUtils.showToast('Sending restart command...', 'info');

        try {
            const response = await fetch('/api/command/system/restart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ robot_id: this.robotId })
            });

            const result = await response.json();

            if (result.success) {
                this.showRestartProgress(result);
            } else {
                appUtils.showToast(
                    `Error: ${result.error || 'Failed to restart'}`,
                    'danger'
                );
                this.enableButtons();
            }
        } catch (error) {
            console.error('Error restarting:', error);
            appUtils.showToast('Failed to send restart command', 'danger');
            this.enableButtons();
        }
    }

    async executeShutdown() {
        this.disableButtons();
        appUtils.showToast('Sending shutdown command...', 'info');

        try {
            const response = await fetch('/api/command/system/shutdown', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ robot_id: this.robotId })
            });

            const result = await response.json();

            if (result.success) {
                appUtils.showToast('Robot is shutting down', 'warning');
                // Don't re-enable buttons - robot is offline
            } else {
                appUtils.showToast(
                    `Error: ${result.error || 'Failed to shutdown'}`,
                    'danger'
                );
                this.enableButtons();
            }
        } catch (error) {
            console.error('Error shutting down:', error);
            appUtils.showToast('Failed to send shutdown command', 'danger');
            this.enableButtons();
        }
    }

    showRestartProgress(data) {
        const progressModal = document.getElementById('restartProgressModal');
        const messageDiv = document.getElementById('restartMessage');
        messageDiv.textContent = data.message || 'Restarting robot...';

        const modal = new bootstrap.Modal(progressModal);
        modal.show();

        // Show countdown timer
        let countdown = 30;
        const timer = setInterval(() => {
            messageDiv.textContent = `Restarting robot... (${countdown}s remaining)`;
            countdown--;

            if (countdown < 0) {
                clearInterval(timer);
            }
        }, 1000);
    }

    disableButtons() {
        this.restartBtn.disabled = true;
        this.shutdownBtn.disabled = true;
    }

    enableButtons() {
        this.restartBtn.disabled = false;
        this.shutdownBtn.disabled = false;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const robotId = 1;
    window.systemControls = new SystemControls(
        'restartRobotBtn',
        'shutdownRobotBtn',
        robotId
    );
});
```

**HTML Confirmation Modals:**
```html
<!-- Restart Confirmation Modal -->
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
                <p class="mb-0"><strong>Continue?</strong></p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" id="confirmRestartBtn" class="btn btn-warning">
                    <i class="bi bi-arrow-clockwise"></i> Restart
                </button>
            </div>
        </div>
    </div>
</div>

<!-- Shutdown Confirmation Modal (Step 1) -->
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
                <button type="button" id="confirmShutdownBtn1" class="btn btn-danger">
                    <i class="bi bi-power"></i> Shutdown
                </button>
            </div>
        </div>
    </div>
</div>

<!-- Shutdown Confirmation Modal (Step 2) -->
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
                <button type="button" id="confirmShutdownBtn2" class="btn btn-danger">
                    <i class="bi bi-power"></i> Yes, Shutdown
                </button>
            </div>
        </div>
    </div>
</div>

<!-- Restart Progress Modal -->
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
                <p id="restartMessage">Restarting robot... (30s remaining)</p>
                <div class="progress mt-3">
                    <div class="progress-bar progress-bar-striped progress-bar-animated"
                         role="progressbar" style="width: 100%"></div>
                </div>
            </div>
        </div>
    </div>
</div>
```

---

### 4. Waypoint Management & Map Locating

#### Temi Center Approach:
```
┌──────────────────────────────────────────┐
│ Waypoint Management on Map               │
├──────────────────────────────────────────┤
│                                          │
│ Display:                                 │
│ • Each waypoint as a marker on canvas    │
│ • Numbered (1, 2, 3...) or named        │
│ • Color-coded (start: red, others: blue)│
│ • Click to select waypoint               │
│ • Double-click to rename                 │
│ • Right-click for context menu           │
│                                          │
│ Context Menu Options:                    │
│ ├─ Go to Waypoint                        │
│ ├─ Edit Details                          │
│ ├─ Delete Waypoint                       │
│ ├─ Set as Home                           │
│ └─ Show Details                          │
│                                          │
│ Waypoint Details Modal:                  │
│ ├─ Name: [text input]                    │
│ ├─ Type: [dropdown] Home/Normal/Patrol  │
│ ├─ Coordinates: X, Y, Theta (read-only) │
│ ├─ Description: [textarea]               │
│ ├─ Associated Routes: [list]             │
│ └─ [Save] [Delete] [Go To]               │
│                                          │
│ Map Interaction:                         │
│ • Double-click on map to create waypoint │
│ • Drag waypoint to move                  │
│ • Zoom/Pan for precise positioning       │
│ • Visual feedback (highlight on hover)   │
│                                          │
└──────────────────────────────────────────┘
```

#### Implementation for Temi Control WebApp:

**Backend (app.py):**
```python
@app.route('/api/robots/<int:robot_id>/waypoints', methods=['GET'])
def get_robot_waypoints(robot_id):
    """Get all waypoints for a robot"""
    try:
        robot = db.get_robot(robot_id)
        if not robot:
            return jsonify({'error': 'Robot not found'}), 404

        waypoints = db.get_waypoints(robot_id)

        return jsonify({
            'success': True,
            'waypoints': [{
                'id': wp['id'],
                'name': wp['name'],
                'x': wp['x'],
                'y': wp['y'],
                'theta': wp['theta'],
                'type': wp.get('type', 'normal'),  # home, normal, patrol
                'description': wp.get('description', ''),
                'created_at': wp['created_at'],
                'used_in_routes': wp.get('route_count', 0)
            } for wp in waypoints]
        })
    except Exception as e:
        logger.error(f'Error getting waypoints: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/robots/<int:robot_id>/waypoints', methods=['POST'])
def create_waypoint(robot_id):
    """Create a new waypoint"""
    try:
        data = request.get_json()
        robot = db.get_robot(robot_id)

        if not robot:
            return jsonify({'error': 'Robot not found'}), 404

        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Waypoint name required'}), 400

        waypoint_id = db.create_waypoint(
            robot_id=robot_id,
            name=data['name'],
            x=float(data.get('x', 0)),
            y=float(data.get('y', 0)),
            theta=float(data.get('theta', 0)),
            type=data.get('type', 'normal'),
            description=data.get('description', '')
        )

        # Log activity
        db.log_activity(
            robot_id=robot_id,
            action='create_waypoint',
            value=data['name']
        )

        emit_socketio('waypoint_created', {
            'robot_id': robot_id,
            'waypoint_id': waypoint_id,
            'waypoint_name': data['name']
        })

        return jsonify({
            'success': True,
            'waypoint_id': waypoint_id,
            'message': f'Waypoint "{data["name"]}" created'
        })
    except Exception as e:
        logger.error(f'Error creating waypoint: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/robots/<int:robot_id>/waypoints/<int:waypoint_id>', methods=['PUT'])
def update_waypoint(robot_id, waypoint_id):
    """Update waypoint details"""
    try:
        data = request.get_json()

        # Update in database
        db.update_waypoint(
            waypoint_id,
            name=data.get('name'),
            type=data.get('type'),
            description=data.get('description'),
            theta=data.get('theta')  # Can update heading
        )

        emit_socketio('waypoint_updated', {
            'robot_id': robot_id,
            'waypoint_id': waypoint_id
        })

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f'Error updating waypoint: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/robots/<int:robot_id>/waypoints/<int:waypoint_id>', methods=['DELETE'])
def delete_waypoint(robot_id, waypoint_id):
    """Delete a waypoint"""
    try:
        # Check if waypoint is in use
        routes_using = db.get_routes_using_waypoint(waypoint_id)

        if routes_using:
            return jsonify({
                'error': f'Waypoint is used in {len(routes_using)} route(s)',
                'routes': routes_using
            }), 409

        db.delete_waypoint(waypoint_id)

        emit_socketio('waypoint_deleted', {
            'robot_id': robot_id,
            'waypoint_id': waypoint_id
        })

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f'Error deleting waypoint: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/command/go-to-waypoint', methods=['POST'])
def go_to_waypoint():
    """Send robot to a specific waypoint"""
    try:
        data = request.get_json()
        robot_id = data.get('robot_id')
        waypoint_name = data.get('waypoint_name')

        robot = db.get_robot(robot_id)
        if not robot or not robot.get('is_connected'):
            return jsonify({'error': 'Robot not connected'}), 503

        # Publish goto command
        topic = f"temi/{robot['serial']}/command/goto"
        payload = json.dumps({'location': waypoint_name})

        success = mqtt_manager.publish(topic, payload)

        if success:
            emit_socketio('robot_goto_waypoint', {
                'robot_id': robot_id,
                'waypoint': waypoint_name
            })

            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to send goto command'}), 500
    except Exception as e:
        logger.error(f'Error sending robot to waypoint: {e}')
        return jsonify({'error': str(e)}), 500
```

**Frontend (map_editor.js - New File):**
```javascript
// Enhanced map editor with waypoint management
class MapEditor {
    constructor(canvasId, robotId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.robotId = robotId;
        this.mapData = null;
        this.waypoints = [];
        this.selectedWaypoint = null;
        this.isDrawing = false;
        this.mapImage = null;

        this.init();
    }

    async init() {
        await this.loadMapAndWaypoints();
        this.attachCanvasHandlers();
        this.attachSocketListeners();
        this.startRenderLoop();
    }

    async loadMapAndWaypoints() {
        try {
            // Load map
            const mapResponse = await fetch(`/api/robots/${this.robotId}/map/current`);
            const mapData = await mapResponse.json();

            if (mapData.success && mapData.imageUrl) {
                this.mapData = mapData;

                const img = new Image();
                img.onload = () => {
                    this.mapImage = img;
                    this.setupCanvasSize();
                };
                img.src = mapData.imageUrl;
            }

            // Load waypoints
            const wpResponse = await fetch(`/api/robots/${this.robotId}/waypoints`);
            const wpData = await wpResponse.json();

            if (wpData.success) {
                this.waypoints = wpData.waypoints;
            }
        } catch (error) {
            console.error('Error loading data:', error);
        }
    }

    setupCanvasSize() {
        if (!this.mapData) return;

        const dims = this.mapData.dimensions;
        this.canvas.width = dims.width;
        this.canvas.height = dims.height;
    }

    attachCanvasHandlers() {
        this.canvas.addEventListener('dblclick', (e) => this.handleMapDoubleClick(e));
        this.canvas.addEventListener('click', (e) => this.handleMapClick(e));
        this.canvas.addEventListener('contextmenu', (e) => this.handleContextMenu(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
    }

    handleMapDoubleClick(event) {
        // Create new waypoint at click location
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // Transform canvas coords to world coords
        const worldCoords = this.canvasToWorld({x, y});

        const waypointName = prompt('Enter waypoint name:', `Waypoint_${this.waypoints.length + 1}`);

        if (waypointName) {
            this.createWaypoint(waypointName, worldCoords.x, worldCoords.y);
        }
    }

    handleMapClick(event) {
        // Select waypoint
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // Check which waypoint was clicked
        for (const wp of this.waypoints) {
            const canvasPos = this.worldToCanvas({x: wp.x, y: wp.y});
            const distance = Math.hypot(x - canvasPos.x, y - canvasPos.y);

            if (distance < 15) {  // 15px click radius
                this.selectWaypoint(wp);
                return;
            }
        }

        // No waypoint clicked - deselect
        this.selectedWaypoint = null;
    }

    handleContextMenu(event) {
        event.preventDefault();

        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // Find clicked waypoint
        let clickedWaypoint = null;
        for (const wp of this.waypoints) {
            const canvasPos = this.worldToCanvas({x: wp.x, y: wp.y});
            const distance = Math.hypot(x - canvasPos.x, y - canvasPos.y);

            if (distance < 15) {
                clickedWaypoint = wp;
                break;
            }
        }

        if (!clickedWaypoint) return;

        // Show context menu
        this.showWaypointContextMenu(clickedWaypoint, event.pageX, event.pageY);
    }

    handleMouseMove(event) {
        // Show drag cursor if over waypoint
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        for (const wp of this.waypoints) {
            const canvasPos = this.worldToCanvas({x: wp.x, y: wp.y});
            const distance = Math.hypot(x - canvasPos.x, y - canvasPos.y);

            if (distance < 15) {
                this.canvas.style.cursor = 'grab';
                return;
            }
        }

        this.canvas.style.cursor = 'crosshair';
    }

    selectWaypoint(waypoint) {
        this.selectedWaypoint = waypoint;
        this.showWaypointDetails(waypoint);
    }

    async createWaypoint(name, x, y) {
        try {
            const response = await fetch(`/api/robots/${this.robotId}/waypoints`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    x: parseFloat(x.toFixed(2)),
                    y: parseFloat(y.toFixed(2)),
                    theta: 0
                })
            });

            const result = await response.json();

            if (result.success) {
                appUtils.showToast(`Waypoint "${name}" created`, 'success');
                await this.loadMapAndWaypoints();
            } else {
                appUtils.showToast(`Error: ${result.error}`, 'danger');
            }
        } catch (error) {
            console.error('Error creating waypoint:', error);
            appUtils.showToast('Failed to create waypoint', 'danger');
        }
    }

    showWaypointDetails(waypoint) {
        const modal = document.getElementById('waypointDetailsModal');

        document.getElementById('wpName').value = waypoint.name;
        document.getElementById('wpType').value = waypoint.type;
        document.getElementById('wpDescription').value = waypoint.description || '';
        document.getElementById('wpX').textContent = waypoint.x.toFixed(2);
        document.getElementById('wpY').textContent = waypoint.y.toFixed(2);
        document.getElementById('wpTheta').textContent = waypoint.theta.toFixed(1);

        document.getElementById('wpSaveBtn').onclick = () => this.saveWaypointDetails(waypoint);
        document.getElementById('wpGoToBtn').onclick = () => this.goToWaypoint(waypoint);
        document.getElementById('wpDeleteBtn').onclick = () => this.deleteWaypoint(waypoint);

        new bootstrap.Modal(modal).show();
    }

    async saveWaypointDetails(waypoint) {
        try {
            const response = await fetch(`/api/robots/${this.robotId}/waypoints/${waypoint.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: document.getElementById('wpName').value,
                    type: document.getElementById('wpType').value,
                    description: document.getElementById('wpDescription').value
                })
            });

            const result = await response.json();

            if (result.success) {
                appUtils.showToast('Waypoint updated', 'success');
                bootstrap.Modal.getInstance(document.getElementById('waypointDetailsModal')).hide();
                await this.loadMapAndWaypoints();
            }
        } catch (error) {
            console.error('Error saving waypoint:', error);
            appUtils.showToast('Failed to save waypoint', 'danger');
        }
    }

    async goToWaypoint(waypoint) {
        try {
            const response = await fetch('/api/command/go-to-waypoint', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    robot_id: this.robotId,
                    waypoint_name: waypoint.name
                })
            });

            const result = await response.json();

            if (result.success) {
                appUtils.showToast(`Sent robot to "${waypoint.name}"`, 'success');
                bootstrap.Modal.getInstance(document.getElementById('waypointDetailsModal')).hide();
            } else {
                appUtils.showToast(`Error: ${result.error}`, 'danger');
            }
        } catch (error) {
            console.error('Error going to waypoint:', error);
            appUtils.showToast('Failed to navigate to waypoint', 'danger');
        }
    }

    async deleteWaypoint(waypoint) {
        if (!confirm(`Delete waypoint "${waypoint.name}"? This cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/robots/${this.robotId}/waypoints/${waypoint.id}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (result.success) {
                appUtils.showToast(`Waypoint "${waypoint.name}" deleted`, 'success');
                bootstrap.Modal.getInstance(document.getElementById('waypointDetailsModal')).hide();
                await this.loadMapAndWaypoints();
            } else if (result.routes) {
                appUtils.showToast(
                    `Cannot delete: used in ${result.routes.length} route(s)`,
                    'warning'
                );
            }
        } catch (error) {
            console.error('Error deleting waypoint:', error);
            appUtils.showToast('Failed to delete waypoint', 'danger');
        }
    }

    showWaypointContextMenu(waypoint, pageX, pageY) {
        // Create context menu
        const menu = document.createElement('div');
        menu.className = 'context-menu';
        menu.style.position = 'fixed';
        menu.style.top = pageY + 'px';
        menu.style.left = pageX + 'px';
        menu.style.zIndex = '10000';

        menu.innerHTML = `
            <a href="#" onclick="mapEditor.goToWaypoint(${JSON.stringify(waypoint).replace(/"/g, '&quot;')})">
                <i class="bi bi-play"></i> Go to Waypoint
            </a>
            <a href="#" onclick="mapEditor.selectWaypoint(${JSON.stringify(waypoint).replace(/"/g, '&quot;')})">
                <i class="bi bi-pencil"></i> Edit
            </a>
            <a href="#" onclick="mapEditor.deleteWaypoint(${JSON.stringify(waypoint).replace(/"/g, '&quot;')})">
                <i class="bi bi-trash"></i> Delete
            </a>
        `;

        document.body.appendChild(menu);

        // Remove menu on click elsewhere
        setTimeout(() => {
            document.addEventListener('click', () => menu.remove(), { once: true });
        }, 100);
    }

    canvasToWorld(canvasPos) {
        if (!this.mapData) return canvasPos;

        const dims = this.mapData.dimensions;
        const ppx = dims.pixelsPerMeter;
        const origin = this.mapData.metadata.origin;

        return {
            x: (canvasPos.x - origin.x) / ppx,
            y: (origin.y - canvasPos.y) / ppx
        };
    }

    worldToCanvas(worldPos) {
        if (!this.mapData) return worldPos;

        const dims = this.mapData.dimensions;
        const ppx = dims.pixelsPerMeter;
        const origin = this.mapData.metadata.origin;

        return {
            x: origin.x + worldPos.x * ppx,
            y: origin.y - worldPos.y * ppx
        };
    }

    attachSocketListeners() {
        if (!window.socket) return;

        window.socket.on('waypoint_created', (data) => {
            if (data.robot_id == this.robotId) {
                this.loadMapAndWaypoints();
            }
        });

        window.socket.on('waypoint_updated', (data) => {
            if (data.robot_id == this.robotId) {
                this.loadMapAndWaypoints();
            }
        });

        window.socket.on('waypoint_deleted', (data) => {
            if (data.robot_id == this.robotId) {
                this.loadMapAndWaypoints();
            }
        });
    }

    startRenderLoop() {
        setInterval(() => this.render(), 33);
    }

    render() {
        if (!this.mapImage || !this.mapData) return;

        // Clear and draw map
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.drawImage(this.mapImage, 0, 0);

        // Draw waypoints
        this.waypoints.forEach((wp, index) => {
            const canvasPos = this.worldToCanvas({x: wp.x, y: wp.y});

            const isSelected = this.selectedWaypoint && this.selectedWaypoint.id === wp.id;
            const isHome = wp.type === 'home';

            // Draw marker circle
            this.ctx.fillStyle = isHome ? '#ff6b6b' : (isSelected ? '#ffd93d' : '#4ecdc4');
            this.ctx.beginPath();
            this.ctx.arc(canvasPos.x, canvasPos.y, isSelected ? 12 : 8, 0, Math.PI * 2);
            this.ctx.fill();

            if (isSelected) {
                this.ctx.strokeStyle = '#fff';
                this.ctx.lineWidth = 2;
                this.ctx.stroke();
            }

            // Draw waypoint number
            this.ctx.fillStyle = '#fff';
            this.ctx.font = 'bold 10px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(index + 1, canvasPos.x, canvasPos.y);

            // Draw waypoint name
            this.ctx.fillStyle = '#000';
            this.ctx.font = '11px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(wp.name, canvasPos.x, canvasPos.y - 20);
        });
    }
}

// Initialize editor
document.addEventListener('DOMContentLoaded', () => {
    const robotId = new URLSearchParams(window.location.search).get('robot_id') || 1;
    window.mapEditor = new MapEditor('mapEditorCanvas', robotId);
});
```

---

### 5. Additional Features Observed in Temi Center

#### Sequences/Routines Editor
- Multi-step workflow builder
- Action types: MOVEMENT, SPEAK, SHOW, AUDIO
- Reusable action templates
- Save/load sequences
- Real-time preview

#### Dashboard Summary Statistics
- Total robots status
- Active patrols count
- Violations in last 24h
- Battery health overview
- Network status

---

## API Endpoints & Integration

### Map Management API
```
GET /api/v2/maps/get/current
├─ Returns current map for logged-in user's robot
├─ Response includes image URL, dimensions, metadata
└─ Cached in IndexedDB for offline use

POST /api/v2/maps/upload
├─ Upload new map image
├─ Returns map ID and metadata
└─ Triggers mobile robot map update

PUT /api/v2/maps/{mapId}
├─ Update map metadata (name, description, scale)
└─ Updates on both cloud and robot

GET /api/v2/maps/{mapId}/waypoints
├─ Retrieve all waypoints for a map
└─ Includes coordinate transform metadata
```

### MQTT Command Topics
```
Command Pattern: temi/{SERIAL}/command/{CATEGORY}/{ACTION}

Volume Control:
  Topic: temi/{SERIAL}/command/volume
  Payload: {"volume": 0-100}

System Control:
  Topic: temi/{SERIAL}/command/system/restart
  Topic: temi/{SERIAL}/command/system/shutdown

Movement:
  Topic: temi/{SERIAL}/command/move/goto
  Payload: {"location": "waypoint_name"}

Status Topics (Real-time):
  temi/{SERIAL}/status/position → {"x": float, "y": float, "theta": float}
  temi/{SERIAL}/status/battery → {"level": 0-100}
  temi/{SERIAL}/status/mode → {"mode": "manual|patrol|idle"}
```

---

## Implementation Recommendations

### Prioritized Roadmap for Your WebApp

**Phase 1 (This Week):**
1. ✅ Already Completed - Core MQTT commands
2. Add map upload functionality (UI + Backend)
3. Add volume control (slider + API)
4. Add restart/shutdown buttons (confirmation modals)

**Phase 2 (Next Week):**
1. Waypoint management on map
2. Map editor with double-click creation
3. Enhanced position tracking visualization
4. Real-time waypoint markers

**Phase 3 (Following Week):**
1. Sequences/routines builder (if needed)
2. Dashboard statistics widgets
3. Map caching (IndexedDB)
4. Mobile responsive optimization

---

## Gap Analysis

### What Your App Has vs. Temi Center

| Feature | Temi Center | Your App | Gap | Priority |
|---------|------------|----------|-----|----------|
| Map Display | Canvas + Image | Canvas (basic) | Add image support | HIGH |
| Map Upload | UI + Cloud sync | Manual (Settings) | Improve UI | MEDIUM |
| Volume Control | Slider UI | Not implemented | ADD | HIGH |
| Restart/Shutdown | Confirmation modals | Not implemented | ADD | HIGH |
| Waypoint Editing | Double-click, drag | Create only | Enhance | MEDIUM |
| Position Tracking | Real-time overlay | Basic updates | Improve | MEDIUM |
| Sequences | Advanced builder | Routes only | Not needed |  |
| Multi-user | Cloud-based | Single user | Future | LOW |

---

## Conclusion

The Temi Center dashboard demonstrates a **polished, production-grade SPA architecture** that prioritizes:

1. **Responsive Design** - Works on desktop and tablet
2. **Real-time Feedback** - MQTT for live status updates
3. **Safety Controls** - Confirmation dialogs for critical actions
4. **User Experience** - Intuitive map interaction and waypoint management
5. **Reliability** - Graceful degradation when disconnected

By implementing the patterns from this analysis, your Temi Control WebApp can achieve feature parity with the official dashboard while maintaining your custom extensions (YOLO integration, multi-robot support, advanced scheduling).

---

## Next Steps

1. **Implement Map Upload UI** - Create dedicated map management page
2. **Add Volume Control Slider** - Integrate with existing commands
3. **Add System Control Buttons** - Restart/Shutdown with confirmations
4. **Enhance Waypoint Management** - Double-click creation, inline editing
5. **Improve Map Visualization** - Load map images, better coordinate transform

All code samples are ready for integration. Start with Phase 1 features for quick wins!

---

**Document Generated**: 2026-02-05
**Status**: Ready for Implementation
