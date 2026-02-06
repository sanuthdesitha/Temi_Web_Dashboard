/**
 * Settings page JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    setupEventHandlers();
    updateSpeedValue();
});

function setupEventHandlers() {
    // Save settings button
    document.getElementById('btn-save-settings').addEventListener('click', saveSettings);
    
    // Clear logs button
    document.getElementById('btn-clear-logs').addEventListener('click', clearLogs);
    
    // Test MQTT button
    const testMqttBtn = document.getElementById('btn-test-mqtt');
    if (testMqttBtn) testMqttBtn.addEventListener('click', testMqttConnection);

    // Test MQTT from Settings button
    const testMqttSettingsBtn = document.getElementById('testMqttSettingsBtn');
    if (testMqttSettingsBtn) testMqttSettingsBtn.addEventListener('click', testMqttConnection);

    // Test SMTP button
    const testSmtpBtn = document.getElementById('btn-test-smtp');
    if (testSmtpBtn) testSmtpBtn.addEventListener('click', testSmtpConnection);

    // Test Telegram button
    const testTelegramBtn = document.getElementById('btn-test-telegram');
    if (testTelegramBtn) testTelegramBtn.addEventListener('click', testTelegramConnection);

    // Test WhatsApp button
    const testWhatsappBtn = document.getElementById('btn-test-whatsapp');
    if (testWhatsappBtn) testWhatsappBtn.addEventListener('click', testWhatsappConnection);
    
    // Speed slider
    document.getElementById('default_movement_speed').addEventListener('input', updateSpeedValue);
}

function updateSpeedValue() {
    const value = document.getElementById('default_movement_speed').value;
    document.getElementById('speed-value').textContent = value;
}

function saveSettings() {
    const settings = {
        default_mqtt_broker: document.getElementById('default_mqtt_broker').value.trim(),
        default_mqtt_port: document.getElementById('default_mqtt_port').value,
        default_mqtt_username: document.getElementById('default_mqtt_username').value.trim(),
        default_mqtt_password: document.getElementById('default_mqtt_password').value.trim(),
        default_mqtt_use_tls: document.getElementById('default_mqtt_use_tls').checked ? 'true' : 'false',
        low_battery_threshold: document.getElementById('low_battery_threshold').value,
        low_battery_action: document.getElementById('low_battery_action').value,
        low_battery_webview_url: document.getElementById('low_battery_webview_url').value,
        default_movement_speed: document.getElementById('default_movement_speed').value,
        home_base_location: document.getElementById('home_base_location').value.trim(),
        waypoint_timeout: document.getElementById('waypoint_timeout').value,
        waypoint_max_retries: document.getElementById('waypoint_max_retries').value,
        patrol_stop_home_timeout_seconds: document.getElementById('patrol_stop_home_timeout_seconds').value,
        patrol_stop_always_send_home: document.getElementById('patrol_stop_always_send_home').checked ? 'true' : 'false',
        detection_timeout_seconds: document.getElementById('detection_timeout_seconds').value,
        no_violation_seconds: document.getElementById('no_violation_seconds').value,
        yolo_script_path: document.getElementById('yolo_script_path').value.trim(),
        no_violation_tts: document.getElementById('no_violation_tts').value.trim(),
        tts_wait_seconds: document.getElementById('tts_wait_seconds').value,
        display_wait_seconds: document.getElementById('display_wait_seconds').value,
        webview_close_delay_seconds: document.getElementById('webview_close_delay_seconds').value,
        patrolling_webview_url: document.getElementById('patrolling_webview_url').value.trim(),
        no_violation_webview_url: document.getElementById('no_violation_webview_url').value.trim(),
        violation_webview_url: document.getElementById('violation_webview_url').value.trim(),
        arrival_action_delay_seconds: document.getElementById('arrival_action_delay_seconds').value,
        violation_action_default: document.getElementById('violation_action_default').value,
        violation_tts_default: document.getElementById('violation_tts_default').value,
        violation_display_content_default: document.getElementById('violation_display_content_default').value.trim(),
        high_violation_threshold: document.getElementById('high_violation_threshold').value,
        yolo_shutdown_timeout: document.getElementById('yolo_shutdown_timeout').value,
        violation_debounce_window: document.getElementById('violation_debounce_window').value,
        violation_smoothing_factor: document.getElementById('violation_smoothing_factor').value,
        outlier_threshold: document.getElementById('outlier_threshold').value,
        map_scale_pixels_per_meter: document.getElementById('map_scale_pixels_per_meter').value,
        map_origin_x: document.getElementById('map_origin_x').value,
        map_origin_y: document.getElementById('map_origin_y').value,
        yolo_stream_url: document.getElementById('yolo_stream_url').value.trim(),
        notifications_enabled: document.getElementById('notifications_enabled').checked ? 'true' : 'false',
        notify_in_app: document.getElementById('notify_in_app').checked ? 'true' : 'false',
        notify_email: document.getElementById('notify_email').checked ? 'true' : 'false',
        notify_sms: document.getElementById('notify_sms').checked ? 'true' : 'false',
        notify_webpush: document.getElementById('notify_webpush').checked ? 'true' : 'false',
        notify_telegram: document.getElementById('notify_telegram').checked ? 'true' : 'false',
        notify_whatsapp: document.getElementById('notify_whatsapp').checked ? 'true' : 'false',
        notify_only_high: document.getElementById('notify_only_high').value,
        notify_digest_frequency: document.getElementById('notify_digest_frequency').value,
        smtp_host: document.getElementById('smtp_host').value.trim(),
        smtp_port: document.getElementById('smtp_port').value,
        smtp_user: document.getElementById('smtp_user').value.trim(),
        smtp_password: document.getElementById('smtp_password').value.trim(),
        smtp_from: document.getElementById('smtp_from').value.trim(),
        smtp_to: document.getElementById('smtp_to').value.trim(),
        smtp_use_tls: document.getElementById('smtp_use_tls').checked ? 'true' : 'false',
        twilio_account_sid: document.getElementById('twilio_account_sid').value.trim(),
        twilio_auth_token: document.getElementById('twilio_auth_token').value.trim(),
        twilio_from: document.getElementById('twilio_from').value.trim(),
        twilio_to: document.getElementById('twilio_to').value.trim(),
        telegram_bot_token: document.getElementById('telegram_bot_token').value.trim(),
        telegram_chat_id: document.getElementById('telegram_chat_id').value.trim(),
        twilio_whatsapp_from: document.getElementById('twilio_whatsapp_from').value.trim(),
        twilio_whatsapp_to: document.getElementById('twilio_whatsapp_to').value.trim()
    };
    
    appUtils.showLoading(true);
    appUtils.apiCall('/api/settings', 'POST', settings).then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            appUtils.showToast('Settings saved successfully', 'success');
        } else {
            appUtils.showToast('Failed to save settings', 'danger');
        }
    });
}

function clearLogs() {
    if (!confirm('Are you sure you want to clear all activity logs?')) {
        return;
    }
    
    appUtils.showLoading(true);
    appUtils.apiCall('/api/logs/clear', 'POST', {}).then(response => {
        appUtils.showLoading(false);
        
        if (response.success) {
            appUtils.showToast('All logs cleared', 'success');
        } else {
            appUtils.showToast('Failed to clear logs', 'danger');
        }
    });
}

function testMqttConnection() {
    appUtils.showToast('Testing MQTT Cloud Broker connection...', 'info');

    appUtils.apiCall('/api/mqtt/test', 'POST', {})
        .then(response => {
            if (response.success) {
                appUtils.showToast('✅ ' + response.message, 'success');
            } else {
                appUtils.showToast('❌ ' + (response.error || 'MQTT connection test failed'), 'danger');
            }
        })
        .catch(error => {
            console.error('MQTT test error:', error);
            appUtils.showToast('❌ Error testing MQTT connection', 'danger');
        });
}

function testSmtpConnection() {
    appUtils.showToast('Testing SMTP...', 'info');
    appUtils.apiCall('/api/settings/test_smtp', 'POST', {})
        .then(response => {
            if (response.success) {
                appUtils.showToast('SMTP test email sent', 'success');
            } else {
                appUtils.showToast(response.error || 'SMTP test failed', 'danger');
            }
        })
        .catch(() => {
            appUtils.showToast('SMTP test failed', 'danger');
        });
}

function testTelegramConnection() {
    appUtils.showToast('Testing Telegram...', 'info');
    appUtils.apiCall('/api/settings/test_telegram', 'POST', {})
        .then(response => {
            if (response.success) {
                appUtils.showToast('Telegram test message sent', 'success');
            } else {
                appUtils.showToast(response.error || 'Telegram test failed', 'danger');
            }
        })
        .catch(() => {
            appUtils.showToast('Telegram test failed', 'danger');
        });
}

function testWhatsappConnection() {
    appUtils.showToast('Testing WhatsApp...', 'info');
    appUtils.apiCall('/api/settings/test_whatsapp', 'POST', {})
        .then(response => {
            if (response.success) {
                appUtils.showToast('WhatsApp test message sent', 'success');
            } else {
                appUtils.showToast(response.error || 'WhatsApp test failed', 'danger');
            }
        })
        .catch(() => {
            appUtils.showToast('WhatsApp test failed', 'danger');
        });
}
