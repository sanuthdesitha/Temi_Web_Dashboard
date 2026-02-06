/**
 * Map Management JavaScript
 * Handles map upload and display
 */

let currentRobotId = null;
let currentMapData = null;

document.addEventListener('DOMContentLoaded', function() {
    loadRobots();
    setupEventListeners();
});

function setupEventListeners() {
    // Robot selection
    document.getElementById('robotSelect').addEventListener('change', function() {
        currentRobotId = parseInt(this.value, 10);
        if (currentRobotId) {
            loadCurrentMap(currentRobotId);
        } else {
            clearMapDisplay();
        }
    });

    // Map upload form
    document.getElementById('mapUploadForm').addEventListener('submit', handleMapUpload);

    // Enable upload button when file is selected
    document.getElementById('mapImageInput').addEventListener('change', function() {
        document.getElementById('uploadMapBtn').disabled = !this.files.length;
    });
}

function loadRobots() {
    fetch('/api/robots')
        .then(r => r.json())
        .then(response => {
            if (response.success && response.robots) {
                const select = document.getElementById('robotSelect');
                select.innerHTML = '<option value="">Select a robot...</option>';

                response.robots.forEach(robot => {
                    const option = document.createElement('option');
                    option.value = robot.id;
                    option.textContent = `${robot.name} (${robot.serial_number})`;
                    select.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading robots:', error);
            appUtils.showToast('Failed to load robots', 'danger');
        });
}

function loadCurrentMap(robotId) {
    fetch(`/api/robots/${robotId}/map/current`)
        .then(r => r.json())
        .then(data => {
            if (data.success && data.imageUrl) {
                currentMapData = data;
                displayMap(data.imageUrl, data.dimensions);
                updateMapInfo(data);
            } else {
                clearMapDisplay();
            }
        })
        .catch(error => {
            console.error('Error loading map:', error);
            clearMapDisplay();
        });
}

function displayMap(imageUrl, dimensions) {
    const container = document.getElementById('mapContainer');

    const img = document.createElement('img');
    img.src = imageUrl;
    img.style.maxWidth = '100%';
    img.style.maxHeight = '100%';
    img.style.objectFit = 'contain';

    container.innerHTML = '';
    container.appendChild(img);
}

function updateMapInfo(mapData) {
    const dims = mapData.dimensions;
    document.getElementById('mapDimensions').textContent =
        `${dims.width}x${dims.height} pixels`;

    document.getElementById('mapScale').textContent =
        `${dims.pixelsPerMeter} pixels/meter`;
}

function clearMapDisplay() {
    const container = document.getElementById('mapContainer');
    container.innerHTML = `
        <div class="text-center">
            <i class="bi bi-image text-muted" style="font-size: 3rem;"></i>
            <p class="text-muted mt-3">No map uploaded yet</p>
            <small class="text-muted">Upload a map image to display here</small>
        </div>
    `;

    document.getElementById('mapDimensions').textContent = '-';
    document.getElementById('mapScale').textContent = '-';
}

function handleMapUpload(event) {
    event.preventDefault();

    if (!currentRobotId) {
        appUtils.showToast('Please select a robot', 'warning');
        return;
    }

    const fileInput = document.getElementById('mapImageInput');
    if (!fileInput.files.length) {
        appUtils.showToast('Please select an image file', 'warning');
        return;
    }

    const file = fileInput.files[0];

    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
        appUtils.showToast('File is too large (max 10MB)', 'danger');
        return;
    }

    // Validate file type
    if (!['image/png', 'image/jpeg'].includes(file.type)) {
        appUtils.showToast('Only PNG and JPEG images are supported', 'danger');
        return;
    }

    // Show progress
    document.getElementById('uploadProgress').style.display = 'block';
    document.getElementById('uploadMapBtn').disabled = true;

    // Prepare form data
    const formData = new FormData();
    formData.append('map_image', file);

    // Upload
    fetch(`/api/robots/${currentRobotId}/upload-map`, {
        method: 'POST',
        body: formData
    })
        .then(r => r.json())
        .then(response => {
            document.getElementById('uploadProgress').style.display = 'none';

            if (response.success) {
                appUtils.showToast('Map uploaded successfully', 'success');

                // Reload map display
                loadCurrentMap(currentRobotId);

                // Show success modal
                document.getElementById('mapUploadInfo').innerHTML = `
                    <p>Map URL: <code>${response.url}</code></p>
                    <p>Dimensions: ${response.dimensions.width}x${response.dimensions.height}</p>
                `;

                const modal = new bootstrap.Modal(document.getElementById('mapUploadSuccessModal'));
                modal.show();

                // Reset form
                document.getElementById('mapUploadForm').reset();
                document.getElementById('uploadMapBtn').disabled = true;
            } else {
                appUtils.showToast(`Upload failed: ${response.error}`, 'danger');
                document.getElementById('uploadMapBtn').disabled = false;
            }
        })
        .catch(error => {
            console.error('Error uploading map:', error);
            appUtils.showToast('Upload failed: Network error', 'danger');
            document.getElementById('uploadProgress').style.display = 'none';
            document.getElementById('uploadMapBtn').disabled = false;
        });
}

// Auto-set origin to image center when file is selected
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('mapImageInput').addEventListener('change', function() {
        if (this.files.length) {
            const file = this.files[0];
            const reader = new FileReader();

            reader.onload = function(e) {
                const img = new Image();
                img.onload = function() {
                    // Set origin to center by default
                    document.getElementById('mapOriginX').value = Math.floor(img.width / 2);
                    document.getElementById('mapOriginY').value = Math.floor(img.height / 2);
                };
                img.src = e.target.result;
            };

            reader.readAsDataURL(file);
        }
    });
});
