# Temi Robot Control WebApp - Quick Start Guide

**Status**: ✅ Production Ready | **Version**: 2.0 | **Date**: 2026-02-06

---

## 🚀 Get Running in 5 Minutes

### Windows

**Step 1: Setup (First Time Only)**
```batch
cd "d:\OPTIK\NOKIA\Temi\Temi_Control_WebApp\Temi-Control-App-Production"
copy .env.example .env
REM Edit .env with your MQTT broker details
notepad .env

cd windows
SETUP.bat
```

**Step 2: Configure**
- Edit the `.env` file with your:
  - MQTT broker IP address
  - MQTT username and password
  - Admin credentials (recommended: change password)
  - Home base waypoint name (default: "home base")

**Step 3: Run**
```batch
cd windows
RUN.bat
```

**Step 4: Access**
- Open browser: http://localhost:5000
- Login with credentials from .env

### Linux

**Step 1: Setup (First Time Only)**
```bash
cd ~/Temi-Control-App-Production
cp .env.example .env
nano .env  # Edit with your MQTT broker details

chmod +x linux/setup.sh linux/run.sh
./linux/setup.sh
```

**Step 2: Run**
```bash
./linux/run.sh
```

**Step 3: Access**
- Open browser: http://localhost:5000

---

## 📋 What's Included

### Dashboard Features ✅
- **MQTT Connection Status** - See broker and robot connection status in real-time
- **Robot List** - View all robots and their current status
- **Quick Actions** - Send commands to robots from dashboard
- **System Status** - Monitor overall system health

### Robot Control ✅
- Send navigation commands (Go To Waypoint)
- Control volume and system settings
- Restart/shutdown robots
- Display webviews on robot screens

### Patrol Management ✅
- Create multi-waypoint patrol routes
- Start/pause/stop patrols
- Configure dwell times and violation detection
- Automatically return to home base

### Violation Detection ✅
- Real-time YOLO-based detection
- Violation history and statistics
- Debouncing to prevent false positives
- WhatsApp/SMS alerts

---

## 🔧 Essential Configuration (.env)

```env
# MQTT Broker (REQUIRED)
MQTT_HOST=your_broker_ip_or_hostname
MQTT_PORT=1883
MQTT_USERNAME=your_mqtt_username
MQTT_PASSWORD=your_mqtt_password

# For HiveMQ Cloud, use:
# MQTT_HOST=your-instance.hivemq.cloud
# MQTT_PORT=8883
# Plus credentials

# Security (CHANGE THESE!)
SECRET_KEY=change-this-to-something-random
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=change-this-password

# Robot Settings
HOME_BASE_LOCATION=home base
FLASK_PORT=5000

# Optional: WhatsApp Alerts
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+1415555555
TWILIO_ALERT_RECIPIENTS=+1234567890
```

---

## 📱 First Run Checklist

After starting the application:

- [ ] Dashboard loads without errors
- [ ] MQTT Connection Status shows broker status
- [ ] Robot list appears with connection status
- [ ] Can log in with admin credentials
- [ ] Can see robot list in Robot Management
- [ ] Can create a test patrol route
- [ ] Test MQTT connection button works

---

## ⚠️ Common Issues & Fixes

### Port 5000 Already in Use
```batch
# Windows
netstat -ano | findstr :5000
taskkill /PID <process_id> /F

# Linux
lsof -i :5000
kill -9 <process_id>
```

### MQTT Connection Failed
1. Verify broker IP in .env
2. Verify username/password
3. Test broker connectivity:
   ```bash
   # Windows: Use MQTTBox or check firewall
   # Linux: mosquitto_sub -h broker_ip -u username -P password
   ```

### Application Crashes on Startup
1. Check if .env file exists
2. Review error message in console
3. Verify database.db file permissions
4. Check that port 5000 is free

### Can't Access http://localhost:5000
1. Verify application is running (no error in console)
2. Check firewall allows port 5000
3. Try http://127.0.0.1:5000 instead

---

## 🆚 RUN.bat vs RUN_DIRECT.bat

**Use RUN.bat** (Recommended for Production)
- Creates isolated virtual environment
- Guaranteed clean dependencies
- Slightly slower startup (5-10 sec)
- More stable and reliable

**Use RUN_DIRECT.bat** (Development Only)
- Faster startup (3-5 sec)
- Uses system Python
- May have package conflicts
- Good for quick testing

---

## 📊 Verifying Everything Works

### Test MQTT Connection
1. Go to Settings page
2. Click "Test Cloud MQTT Connection" button
3. Should show "Connected" status

### Test Robot Command
1. Go to Robot Management
2. Select a robot
3. Try a simple command (e.g., set volume to 50%)
4. Verify command executes on robot

### Test Patrol
1. Go to Patrol Control
2. Create a simple route with 2 waypoints
3. Start the patrol
4. Watch robot navigate waypoints
5. Verify it returns to home base

---

## 🔄 Stopping the Application

**Windows**
- Press `Ctrl+C` in the command prompt window
- Or close the command window

**Linux**
- Press `Ctrl+C` in the terminal
- Or type: `kill -9 $(lsof -ti:5000)`

---

## 📈 Next Steps

### After Successful Startup
1. **Configure Settings**
   - Set home base location for your robots
   - Configure MQTT broker details
   - Set up alerts if needed

2. **Add Robots**
   - Go to Robot Management
   - Add each robot with its ID
   - Verify MQTT connection

3. **Create Routes**
   - Go to Route Management
   - Create patrol routes with waypoints
   - Test with one robot first

4. **Start Patrols**
   - Go to Patrol Control
   - Select robot and route
   - Start patrol and monitor

5. **Monitor Violations** (if using YOLO)
   - Go to Violations page
   - View detection history
   - Configure alerts as needed

---

## 💾 Backup Important Files

```
temi_control.db      <- Robot and patrol database
.env                 <- Credentials and configuration
app.log              <- Application logs (useful for debugging)
```

Keep these backed up regularly!

---

## 🔗 Useful Links

- **GitHub Repository**: https://github.com/sanuthdesitha/Temi_Web_Dashboard
- **MQTT Documentation**: http://mqtt.org/
- **HiveMQ Cloud**: https://www.hivemq.cloud/
- **Twilio (WhatsApp)**: https://www.twilio.com/
- **Application Logs**: Check `app.log` in the app directory

---

## 📞 Troubleshooting Resources

1. **Check application log**: `app.log` in the app directory
2. **Verify MQTT broker is running** and accessible
3. **Ensure .env file is properly configured**
4. **Check network connectivity** between server and MQTT broker
5. **Review error messages** in the console

---

## ✅ You're Ready!

The application is fully configured and ready to deploy.

**Start with**:
- Windows: `cd windows && RUN.bat`
- Linux: `./linux/run.sh`

Then access: **http://localhost:5000**

Good luck! 🚀

---

*For detailed information, see PRODUCTION_DEPLOYMENT_CHECKLIST.md*
