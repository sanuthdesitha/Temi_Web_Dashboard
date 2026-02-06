================================================================================
TEMI ROBOT CONTROL WEBAPP - WINDOWS SETUP GUIDE
================================================================================

Complete step-by-step instructions for installing and running the Temi Control
WebApp on Windows systems.

SYSTEM REQUIREMENTS
================================================================================

Minimum Requirements:
  • Windows 7 or later
  • Python 3.8 or later installed
  • 500 MB free disk space
  • 2 GB RAM
  • Internet connection (for initial setup)

Recommended:
  • Windows 10 or Windows 11
  • Python 3.10 or later
  • 1 GB free disk space
  • 4 GB RAM or more

CHECKING PYTHON INSTALLATION
================================================================================

1. INSTALL PYTHON (if not already installed):
   - Download from: https://www.python.org/downloads/
   - Download "Python 3.10" or later for Windows
   - During installation, IMPORTANT: Check "Add Python to PATH"
   - Complete the installation

2. VERIFY PYTHON:
   - Open Command Prompt (Win+R, type "cmd", Enter)
   - Run: python --version
   - Should show: Python 3.x.x (3.8 or higher)
   - Run: pip --version
   - Should show: pip x.x.x

3. IF PYTHON NOT FOUND:
   - Python may need to be added to PATH manually
   - Or restart computer after installation
   - Or use python3 instead of python in commands

INSTALLATION STEPS
================================================================================

STEP 1: EXTRACT FILES
────────────────────────────────────────────────────────────────────────────

1. Extract the zip file to a location such as:
   C:\Temi-Control-App-Production\

2. You should have a folder structure like:
   C:\Temi-Control-App-Production\
   ├── windows\
   │   ├── SETUP.bat
   │   ├── RUN.bat
   │   └── app\
   ├── linux\
   ├── QUICK_START.txt
   └── requirements.txt

STEP 2: RUN SETUP.BAT
────────────────────────────────────────────────────────────────────────────

1. Navigate to: C:\Temi-Control-App-Production\windows\

2. Double-click: SETUP.bat
   OR
   Right-click SETUP.bat → "Run as administrator"

3. The script will:
   ✓ Check Python installation
   ✓ Create virtual environment (venv folder)
   ✓ Install all Python dependencies
   ✓ Initialize the database
   ✓ Set up default admin account

4. Wait for completion (may take 2-5 minutes)

5. You should see: "Setup complete! Run RUN.bat to start the app"

TROUBLESHOOTING SETUP.BAT
────────────────────────────────────────────────────────────────────────────

Error: "'python' is not recognized as an internal or external command"

Solution 1 (Recommended):
  - Reinstall Python from https://www.python.org/downloads/
  - IMPORTANT: During installation, check "Add Python to PATH"
  - Restart computer
  - Run SETUP.bat again

Solution 2:
  - Try using python3 instead:
  - Open Command Prompt in the windows\ folder
  - Run: python3 -m pip install -r ../requirements.txt

Error: "Access Denied" or permission issues

Solution:
  - Right-click SETUP.bat → "Run as administrator"
  - Alternatively, open Command Prompt as administrator first:
    * Win+R → type "cmd" → Ctrl+Shift+Enter
    * Navigate to the windows folder: cd C:\Temi-Control-App-Production\windows\
    * Run: SETUP.bat

Error: "Module not found" or pip errors

Solution:
  - Delete the venv folder (if it exists):
    * Windows Explorer → Delete the venv folder
    * Or: rmdir /s venv
  - Run SETUP.bat again
  - This will start from scratch

Error: "Port 5000 already in use"

Solution:
  - This happens if you run multiple instances
  - Either stop the other instance (Ctrl+C in its window)
  - Or configure a different port (advanced - see Configuration section)

STEP 3: RUN THE APPLICATION
────────────────────────────────────────────────────────────────────────────

1. Navigate to: C:\Temi-Control-App-Production\windows\

2. Double-click: RUN.bat
   OR
   In Command Prompt, type: RUN.bat

3. The application will start, showing output like:
   ────────────────────────────────────────────────────────────
   * Running on http://127.0.0.1:5000
   * Press CTRL+C to quit
   ────────────────────────────────────────────────────────────

4. Keep this window open while using the app

5. Open your web browser and go to: http://localhost:5000

STEP 4: FIRST TIME LOGIN
────────────────────────────────────────────────────────────────────────────

1. You'll see the login page

2. Enter default credentials:
   Username: admin
   Password: admin

3. Click "Login"

4. You're now in the dashboard!

STEP 5: CONFIGURE ROBOTS AND MQTT
────────────────────────────────────────────────────────────────────────────

1. Click "Settings" in the navigation menu

2. Configure MQTT Broker:
   - MQTT Host: Enter your MQTT broker IP or hostname
     * Local broker: localhost or 127.0.0.1
     * HiveMQ Cloud: Use your cloud instance address
   - MQTT Port: Usually 1883 (standard) or 8883 (secure)
   - Username/Password: If required by your broker

3. Add Robots:
   - Go to "Robot Management" section
   - Click "Add Robot"
   - Enter robot details:
     * Name: Friendly name for the robot
     * Serial: Robot's MQTT serial number
     * Home Base: Default location/waypoint name

4. Click "Save" and test connection

DAILY USAGE
================================================================================

STARTING THE APPLICATION:
1. Open Windows Explorer
2. Navigate to: C:\Temi-Control-App-Production\windows\
3. Double-click: RUN.bat
4. Wait for: "Running on http://127.0.0.1:5000"
5. Open browser: http://localhost:5000

STOPPING THE APPLICATION:
1. Go to the Command Prompt window running the app
2. Press: Ctrl+C
3. The application will shut down gracefully

AUTOMATIC STARTUP (Advanced):
To run the app automatically when you start Windows:

1. Create a shortcut to: C:\Temi-Control-App-Production\windows\RUN.bat

2. Right-click the shortcut → Properties

3. Set "Start in" to: C:\Temi-Control-App-Production\windows\

4. Move the shortcut to: C:\Users\[YourUsername]\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\

5. Next reboot, the app will start automatically

ACCESSING FROM OTHER COMPUTERS
================================================================================

To access the webapp from another computer on your network:

1. Find your computer's IP address:
   - Open Command Prompt
   - Run: ipconfig
   - Look for: "IPv4 Address" (usually 192.168.x.x or 10.0.x.x)

2. From another computer, open browser and go to:
   http://<your-computer-ip>:5000

Example: If your IP is 192.168.1.50:
   http://192.168.1.50:5000

IMPORTANT: Firewall must allow port 5000
   - Windows Firewall will usually ask to allow on first run
   - Click "Allow access" if prompted

BACKING UP YOUR DATA
================================================================================

Your database and configurations are stored in the venv folder.

To back up:

1. Stop the application (Ctrl+C)

2. Copy the entire folder:
   From: C:\Temi-Control-App-Production\
   To: External drive or cloud storage

Alternatively, just back up the database:

1. Locate database file (usually created in venv folder)

2. Make a copy in a safe location

3. You can restore by copying back if needed

UPDATING THE APPLICATION
================================================================================

To update to a new version:

1. STOP the current app: Ctrl+C in the running window

2. BACKUP your data:
   - Copy entire C:\Temi-Control-App-Production\ to another location

3. Download the new version

4. EXTRACT the new version (overwrite existing files)
   - Windows will ask to confirm overwriting - click "Yes for All"

5. RUN SETUP.BAT again:
   - This updates dependencies if needed
   - Your database will be preserved

6. RUN the application:
   - Double-click RUN.bat

ADVANCED CONFIGURATION
================================================================================

CHANGING THE PORT (if 5000 is already in use):

1. Open Command Prompt in windows\ folder

2. Run:
   setx FLASK_PORT 5001
   RUN.bat

3. Access at: http://localhost:5001

RUNNING IN PRODUCTION MODE (Not for beginners):

1. The current setup uses Flask development server
2. For production use, install Gunicorn:
   - pip install gunicorn
   - Run: gunicorn --workers 4 app:app
3. Use Nginx or Apache as reverse proxy

LOGS AND DEBUGGING
================================================================================

If something goes wrong:

1. The error messages appear in the Command Prompt window
2. Take a screenshot of error messages
3. Check the following files in the app\ folder:
   - app.py (main application)
   - Look for any "ERROR" or "EXCEPTION" messages
4. Common errors:
   - Port already in use: Use different port (see Advanced section)
   - MQTT connection failed: Check MQTT broker is running
   - Database error: Delete database and restart

COMMON ISSUES AND SOLUTIONS
================================================================================

Issue: "Could not connect to MQTT broker"
Solution:
  - Verify MQTT broker is running and accessible
  - Check host and port in settings
  - Check firewall allows port 1883 (or configured port)
  - If using cloud broker, verify credentials

Issue: "Cannot connect to robot"
Solution:
  - Verify robot is powered on
  - Verify robot serial number matches in settings
  - Check robot and broker are on same network
  - Try pinging robot from command prompt: ping <robot-ip>

Issue: "Web page won't load"
Solution:
  - Check app is still running (look for the Command Prompt window)
  - Try refreshing browser: F5
  - Try: http://127.0.0.1:5000 instead of http://localhost:5000
  - Close browser completely and reopen

Issue: "Can't save robot settings"
Solution:
  - Check database permissions
  - Delete venv folder and rerun SETUP.bat
  - Check disk space available

PERFORMANCE TIPS
================================================================================

For smooth operation:

1. Keep browser tab open (don't minimize window)
2. Close unnecessary programs to free up RAM
3. If managing many robots, add more RAM to computer
4. Use wired network connection for better stability
5. Keep software updated (Windows Update)

SECURITY CONSIDERATIONS
================================================================================

For production use:

1. Change default admin password immediately:
   - Login → Settings → Users → Edit Admin → Change Password

2. Create separate user accounts for different operators

3. Restrict network access:
   - Use VPN or firewall to limit access to trusted IPs
   - Don't expose port 5000 to the internet

4. Keep system updated:
   - Run Windows Update regularly
   - Periodically reinstall dependencies: pip install -r ../requirements.txt --upgrade

5. Back up database regularly

6. Use strong passwords for all accounts

UNINSTALLING / CLEANUP
================================================================================

If you want to remove the application:

1. Close the running app (Ctrl+C)

2. Delete the folder:
   C:\Temi-Control-App-Production\

3. Optional: Uninstall Python if you don't need it:
   - Control Panel → Programs → Uninstall a program
   - Find Python → Uninstall

The app doesn't install anything system-wide, so deletion is safe.

GETTING HELP
================================================================================

If you encounter issues:

1. Check QUICK_START.txt for basic troubleshooting

2. Check the Command Prompt output for error messages

3. Review this README_WINDOWS.txt troubleshooting section

4. Keep error messages and screenshots for support

TECHNICAL SPECIFICATIONS
================================================================================

Architecture:
  - Backend: Python Flask (web framework)
  - Frontend: HTML5, CSS3, JavaScript
  - Database: SQLite
  - Real-time: Socket.IO
  - Communication: MQTT (Temi SDK)

Default Ports:
  - Web Interface: 5000 (HTTP)
  - MQTT Broker: 1883 (if local)

Python Packages:
  - All listed in: requirements.txt
  - Installed automatically by SETUP.bat

Database:
  - SQLite 3
  - Automatically created on first run
  - Contains: robots, routes, waypoints, logs, settings

================================================================================
VERSION: 1.0.0 Production Release
LAST UPDATED: 2026-02-06
For more info, see: QUICK_START.txt
================================================================================
