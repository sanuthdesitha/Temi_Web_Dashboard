================================================================================
TEMI ROBOT CONTROL WEBAPP - LINUX SETUP GUIDE
================================================================================

Complete step-by-step instructions for installing and running the Temi Control
WebApp on Linux systems.

SUPPORTED DISTRIBUTIONS
================================================================================

Tested and supported on:
  • Ubuntu 18.04 LTS and later
  • Debian 9 and later
  • CentOS 7 and later
  • Any Debian/Ubuntu-based distribution

Minimum Requirements:
  • Python 3.8 or later
  • pip3 package manager
  • 500 MB free disk space
  • 2 GB RAM
  • Internet connection (for initial setup)

Recommended:
  • Ubuntu 20.04 LTS or later
  • Python 3.10 or later
  • 1 GB free disk space
  • 4 GB RAM or more
  • SSD disk for better performance

CHECKING PYTHON INSTALLATION
================================================================================

1. CHECK PYTHON AND PIP:
   Open terminal and run:
   $ python3 --version
   $ pip3 --version

   Should show: Python 3.8 or later, pip x.x.x

2. IF NOT INSTALLED:
   Ubuntu/Debian:
   $ sudo apt update
   $ sudo apt install python3 python3-pip python3-venv

   CentOS/RHEL:
   $ sudo yum install python3 python3-pip

3. VERIFY INSTALLATION:
   $ python3 --version
   $ pip3 --version

INSTALLATION STEPS
================================================================================

STEP 1: EXTRACT FILES
────────────────────────────────────────────────────────────────────────────

1. Extract the zip file to your home directory:
   $ unzip Temi-Control-App-Production.zip -d ~

2. You should have:
   ~/Temi-Control-App-Production/
   ├── linux/
   │   ├── setup.sh
   │   ├── run.sh
   │   └── app/
   ├── windows/
   ├── QUICK_START.txt
   └── requirements.txt

3. Navigate to the directory:
   $ cd ~/Temi-Control-App-Production

STEP 2: RUN SETUP SCRIPT
────────────────────────────────────────────────────────────────────────────

1. Make the script executable:
   $ chmod +x linux/setup.sh

2. Run the setup script:
   $ ./linux/setup.sh

3. The script will:
   ✓ Check Python 3 and pip3 installation
   ✓ Create virtual environment (venv)
   ✓ Install all Python dependencies
   ✓ Initialize the SQLite database
   ✓ Set up default admin account

4. Wait for completion (may take 2-5 minutes on first run)

5. You should see:
   "Setup complete! You can now run the application."
   "Run: ./linux/run.sh to start the app"

TROUBLESHOOTING SETUP SCRIPT
────────────────────────────────────────────────────────────────────────────

Error: "python3: command not found"

Solution:
  - Install Python 3:
    Ubuntu: $ sudo apt install python3 python3-pip python3-venv
    CentOS: $ sudo yum install python3 python3-pip
  - Run setup.sh again

Error: "Permission denied" when running setup.sh

Solution:
  - Make it executable: chmod +x linux/setup.sh
  - Then run: ./linux/setup.sh

Error: "pip3 command not found"

Solution:
  - Install pip3:
    Ubuntu: $ sudo apt install python3-pip
    CentOS: $ sudo yum install python3-pip
  - Run setup.sh again

Error: Module installation fails (pip errors)

Solution 1:
  - Ensure internet connection is working
  - Try again - temporary network glitch

Solution 2:
  - Upgrade pip: pip3 install --upgrade pip
  - Delete venv: rm -rf venv
  - Run setup.sh again

Error: "Permission denied" when creating venv

Solution:
  - Check disk space: df -h
  - Check folder permissions: ls -la
  - Ensure write permissions in directory
  - Run: chmod u+w linux/

Error: Database initialization fails

Solution:
  - Check disk space: df -h
  - Delete any corrupted database:
    rm -f app/database.db
  - Re-run setup.sh

STEP 3: RUN THE APPLICATION
────────────────────────────────────────────────────────────────────────────

1. Make the run script executable:
   $ chmod +x linux/run.sh

2. Start the application:
   $ ./linux/run.sh

3. You should see output like:
   ────────────────────────────────────────────────────────────
   Activating virtual environment...
   Virtual environment activated

   Starting Temi Robot Control WebApp...
   * Running on http://127.0.0.1:5000
   * Press CTRL+C to quit
   ────────────────────────────────────────────────────────────

4. Keep the terminal window open

5. Open web browser and go to: http://localhost:5000

TROUBLESHOOTING RUN SCRIPT
────────────────────────────────────────────────────────────────────────────

Error: "Permission denied" when running run.sh

Solution:
  $ chmod +x linux/run.sh
  $ ./linux/run.sh

Error: "Port 5000 already in use"

Solution 1 (Recommended):
  - Stop the other instance: Ctrl+C in its terminal
  - Wait 5 seconds
  - Run the app again

Solution 2 (Advanced):
  - Use different port by editing run.sh
  - Or: FLASK_PORT=5001 ./linux/run.sh

Error: "No module named flask"

Solution:
  - Virtual environment not activated properly
  - Delete venv: rm -rf venv
  - Re-run: ./linux/setup.sh
  - Then: ./linux/run.sh

Error: "Address already in use"

Solution:
  - Find process using port 5000:
    $ lsof -i :5000
    or $ ss -ltnp | grep 5000
  - Kill the process: kill <PID>
  - Then run the app again

STEP 4: FIRST TIME LOGIN
────────────────────────────────────────────────────────────────────────────

1. Open browser: http://localhost:5000

2. You'll see login page

3. Enter default credentials:
   Username: admin
   Password: admin

4. Click "Login"

5. You're now in the dashboard!

STEP 5: CONFIGURE ROBOTS
────────────────────────────────────────────────────────────────────────────

1. Click "Settings" in the navigation menu

2. Configure MQTT Broker:
   - MQTT Host: Enter your MQTT broker IP/hostname
     * Local broker: localhost or 127.0.0.1
     * Remote: IP address or domain
     * HiveMQ Cloud: Your cloud instance
   - Port: Usually 1883 (or 8883 for TLS)
   - Username/Password: If required

3. Add Robots:
   - Click "Add Robot"
   - Robot Name: Friendly name
   - Serial: Robot's MQTT serial number
   - Home Base: Default waypoint

4. Test Connection:
   - After saving, test MQTT connection

DAILY USAGE
================================================================================

STARTING THE APPLICATION:
1. Open terminal
2. Navigate: $ cd ~/Temi-Control-App-Production
3. Run: $ ./linux/run.sh
4. Wait for: "Running on http://127.0.0.1:5000"
5. Open browser: http://localhost:5000

STOPPING THE APPLICATION:
1. In the running terminal window
2. Press: Ctrl+C
3. Wait for graceful shutdown

RUNNING IN BACKGROUND (Useful for servers):
Option 1 - Using nohup:
  $ nohup ./linux/run.sh > app.log 2>&1 &
  $ echo $!  # Shows process ID

  To stop: kill <process-id>
  To view logs: tail -f app.log

Option 2 - Using screen:
  $ screen -S temi
  $ ./linux/run.sh

  To detach: Ctrl+A then D
  To reattach: screen -r temi

RUNNING AS SYSTEMD SERVICE (Advanced):

This allows automatic startup and management:

1. Create service file:
   $ sudo nano /etc/systemd/system/temi-control.service

2. Add content:
   ────────────────────────────────────────────────────────
   [Unit]
   Description=Temi Control WebApp
   After=network.target

   [Service]
   Type=simple
   User=<YOUR_USERNAME>
   WorkingDirectory=/home/<YOUR_USERNAME>/Temi-Control-App-Production
   ExecStart=/home/<YOUR_USERNAME>/Temi-Control-App-Production/linux/run.sh
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ────────────────────────────────────────────────────────

   (Replace <YOUR_USERNAME> with your actual username)

3. Enable and start:
   $ sudo systemctl daemon-reload
   $ sudo systemctl enable temi-control
   $ sudo systemctl start temi-control

4. Check status:
   $ sudo systemctl status temi-control

5. View logs:
   $ sudo journalctl -u temi-control -f

6. To stop:
   $ sudo systemctl stop temi-control

ACCESSING FROM OTHER COMPUTERS
================================================================================

To access the webapp from another computer:

1. Find your Linux computer's IP address:
   $ hostname -I
   or
   $ ip addr show

   Look for IPv4 address (usually 192.168.x.x or 10.0.x.x)

2. From another computer, open browser:
   http://<your-linux-ip>:5000

   Example: http://192.168.1.50:5000

3. Configure firewall to allow port 5000:
   UFW (Ubuntu):
   $ sudo ufw allow 5000/tcp

   Firewalld (CentOS):
   $ sudo firewall-cmd --permanent --add-port=5000/tcp
   $ sudo firewall-cmd --reload

BACKING UP YOUR DATA
================================================================================

Backup entire application:
$ tar czf backup-$(date +%Y%m%d).tar.gz \
    ~/Temi-Control-App-Production/

Restore:
$ tar xzf backup-*.tar.gz -C ~

Backup only database:
$ cp ~/Temi-Control-App-Production/app/database.db \
     ~/backup-database-$(date +%Y%m%d).db

UPDATING THE APPLICATION
================================================================================

To update to a new version:

1. STOP current app:
   $ Ctrl+C

2. BACKUP your data:
   $ tar czf backup-$(date +%Y%m%d).tar.gz \
       ~/Temi-Control-App-Production/

3. Extract new version (overwrite files)

4. Run setup script again:
   $ ./linux/setup.sh

5. Start application:
   $ ./linux/run.sh

ADVANCED CONFIGURATION
================================================================================

CHANGING DEFAULT PORT:

Option 1 - Environment variable:
  $ FLASK_PORT=8000 ./linux/run.sh

Option 2 - Edit run.sh:
  $ nano linux/run.sh
  Find: python3 app.py
  Change to: python3 app.py --port 8000

PRODUCTION DEPLOYMENT WITH NGINX:

For production use, run behind Nginx:

1. Install Gunicorn:
   $ pip3 install gunicorn

2. Run with Gunicorn:
   $ cd ~/Temi-Control-App-Production/linux/app
   $ gunicorn --workers 4 --bind 127.0.0.1:5000 app:app

3. Configure Nginx as reverse proxy (advanced topic)

ENVIRONMENTAL CONFIGURATION:

Create .env file in app directory:

$ cat > ~/Temi-Control-App-Production/linux/app/.env << EOF
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=your-secret-key-here
MQTT_HOST=localhost
MQTT_PORT=1883
EOF

Then restart application.

LOGS AND DEBUGGING
================================================================================

View application output:
$ ./linux/run.sh

This shows all messages in real-time.

Redirect logs to file:
$ ./linux/run.sh > app.log 2>&1 &

View logs:
$ tail -f app.log

Check for errors:
$ grep ERROR app.log

Check system logs:
$ sudo journalctl -xe

COMMON ISSUES AND SOLUTIONS
================================================================================

Issue: "Connection refused" to MQTT broker
Solution:
  - Verify broker is running: netstat -an | grep 1883
  - Check broker IP and port in settings
  - Test connectivity: telnet <broker-ip> 1883
  - Check firewall: sudo ufw status

Issue: "Permission denied" errors
Solution:
  - Check file permissions: ls -la
  - Fix permissions: chmod u+rw <filename>
  - Check directory permissions: chmod u+rx <dirname>
  - Ensure you own the files: chown -R $USER:$USER ~/Temi-Control-App-Production

Issue: "Cannot write to database"
Solution:
  - Check disk space: df -h
  - Check database permissions: ls -la app/database.db
  - Fix if needed: chmod u+rw app/database.db
  - Verify folder writable: chmod u+w app/

Issue: Web interface won't load
Solution:
  - Check app is running: ps aux | grep app.py
  - Check port listening: ss -ltn | grep 5000
  - Check firewall: sudo ufw status
  - Try direct URL: http://127.0.0.1:5000
  - Check browser console for errors (F12)

Issue: "Virtual environment" activation fails
Solution:
  - Delete venv: rm -rf venv
  - Re-run setup.sh: ./linux/setup.sh

Issue: MQTT connection timeouts
Solution:
  - Check network connectivity: ping <broker-ip>
  - Check firewall between machines
  - Verify correct IP/port in settings
  - Check MQTT broker logs

PERFORMANCE OPTIMIZATION
================================================================================

For optimal performance:

1. Monitor resources:
   $ top
   $ free -h

2. If high memory usage:
   - Limit number of concurrent connections
   - Increase system RAM
   - Run on more powerful server

3. If slow response:
   - Check network latency: ping localhost
   - Check disk I/O: iostat
   - Consider SSD instead of HDD

4. For many robots (10+):
   - Increase workers: Gunicorn --workers 8
   - Use database indexing (auto-done)
   - Monitor network bandwidth

5. Database optimization:
   - Periodic cleanup of old logs
   - Archive old patrol data
   - Run: VACUUM command periodically

SECURITY CONSIDERATIONS
================================================================================

For production deployment:

1. CHANGE DEFAULT PASSWORD:
   - Login with admin/admin
   - Settings → Users → Change admin password

2. CREATE SEPARATE USERS:
   - Don't share admin account
   - Create operator accounts with limited permissions

3. RESTRICT NETWORK ACCESS:
   - Use firewall: ufw allow from 192.168.1.0/24 to any port 5000
   - Don't expose to internet without VPN
   - Use SSH tunneling for remote access:
     $ ssh -L 5000:localhost:5000 user@remote-server

4. ENABLE HTTPS (Advanced):
   - Generate self-signed certificate:
     $ openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
   - Configure Flask to use certificate
   - Access via: https://localhost:5000

5. SYSTEM SECURITY:
   - Keep Linux updated: sudo apt update && sudo apt upgrade
   - Use firewall: sudo ufw enable
   - Regular backups
   - Monitor logs: sudo tail -f /var/log/syslog

6. DATABASE SECURITY:
   - Ensure database file permissions: chmod 600 app/database.db
   - Regular backups to secure location
   - Encrypt backups if sensitive

UNINSTALLING
================================================================================

To completely remove the application:

1. Stop the app: Ctrl+C

2. Remove application folder:
   $ rm -rf ~/Temi-Control-App-Production

3. If installed as service:
   $ sudo systemctl disable temi-control
   $ sudo systemctl stop temi-control
   $ sudo rm /etc/systemd/system/temi-control.service
   $ sudo systemctl daemon-reload

4. Optional - Remove Python (if not needed for other projects):
   $ sudo apt remove python3 python3-pip

The application doesn't modify system files, so removal is safe.

DISK SPACE REQUIREMENTS
================================================================================

Application:
  - Base installation: ~300-500 MB
  - With virtual environment: ~400-600 MB

Database:
  - Empty: ~1 MB
  - Per 1000 patrol logs: ~5-10 MB
  - Per 1000 violations: ~2-5 MB

Logs:
  - Per day: ~1-10 MB (depending on activity)
  - Recommend keeping last 30 days: ~30-300 MB

Total for typical setup:
  - Minimum: ~500 MB
  - Recommended: ~1 GB
  - Large deployments: ~2-5 GB

CRON JOBS (Scheduled Maintenance)
================================================================================

Optional automated tasks:

1. Daily backup at 2 AM:
   $ crontab -e
   Add: 0 2 * * * tar czf /backups/temi-$(date +\%Y\%m\%d).tar.gz ~/Temi-Control-App-Production

2. Weekly database cleanup:
   Add: 0 3 0 * * sqlite3 ~/Temi-Control-App-Production/linux/app/database.db "VACUUM;"

3. Application restart daily:
   Add: 0 4 * * * /home/user/Temi-Control-App-Production/linux/run.sh >> /tmp/temi.log 2>&1

GETTING HELP
================================================================================

If you encounter issues:

1. Check QUICK_START.txt - basic troubleshooting

2. Review error messages in terminal output

3. Check this README_LINUX.txt troubleshooting section

4. View application logs for error details

5. Keep error messages and screenshots for support

SUPPORT INFORMATION
================================================================================

For issues or questions:
- Check QUICK_START.txt
- Review this README_LINUX.txt
- Check in-app help (accessible from dashboard)
- Contact: [Support contact info if available]

TECHNICAL DETAILS
================================================================================

Application Stack:
  - Backend: Python 3.8+ with Flask web framework
  - Frontend: HTML5, CSS3, JavaScript
  - Database: SQLite 3
  - Real-time Communication: Socket.IO
  - Robot Communication: MQTT protocol

Architecture:
  - Single-threaded Flask development server
  - Can scale to Gunicorn + Nginx for production

File Structure:
  - app.py: Main application entry point
  - database.py: Database operations
  - mqtt_manager.py: MQTT client wrapper
  - patrol_manager.py: Patrol execution logic
  - templates/: HTML templates
  - static/: CSS, JavaScript, images

Default Configuration:
  - Web Port: 5000
  - MQTT Port: 1883 (configurable)
  - Database: SQLite (auto-created)

Ports Used:
  - 5000: Web interface (configurable)
  - 1883: MQTT broker (configurable)

================================================================================
VERSION: 1.0.0 Production Release
LAST UPDATED: 2026-02-06
For more info, see: QUICK_START.txt
================================================================================
