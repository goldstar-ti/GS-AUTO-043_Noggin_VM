# Log Maintenance & Automation


## Overview

The log maintenance system provides a robust, automated strategy for managing application log files. Its primary goal is to prevent disk space exhaustion on the server while ensuring that historical logs remain available for debugging and auditing purposes for a reasonable timeframe.

The system follows a two-stage lifecycle for log files:

1. **Compression Phase**: Active log files (`.log`) that are older than **7 days** are compressed using gzip (`.log.gz`). This step significantly reduces the storage footprint—often by 90% or more—while keeping the data accessible for retrospective analysis.
2. **Deletion Phase**: To ensure the disk does not eventually fill up with archives, any log files (compressed or uncompressed) older than **30 days** are permanently deleted.

## 1. Maintenance Script

**Location:** `/home/noggin_admin/scripts/sys/log_maintenance.py`

This Python script is the core engine of the maintenance process. It utilizes the application's shared logging library to safely identify, compress, and remove files based on their modification timestamps.

Before automating the script, you must ensure it has the correct permissions to execute and modify files in the log directory. Use the following commands to set the executable flag and ensure ownership matches the service user (`noggin_admin`):

```bash
# Set executable permission
chmod +x /home/noggin_admin/scripts/maintenance.py

# Ensure correct ownership
chown noggin_admin:noggin_admin /home/noggin_admin/scripts/maintenance.py
```

## 2. Systemd Automation Setup

To guarantee reliability, we use **Systemd** rather than a simple cron job. Systemd offers better logging, error handling, and dependency management. The setup requires two files: a **Service** (what to run) and a **Timer** (when to run it).

### A. Service File

The service unit defines the execution environment. We configure it as a `oneshot` service because the script performs a specific task and then exits, rather than running continuously as a daemon.

Create the file **`/etc/systemd/system/noggin-maintenance.service`** with the following content:

```ini
[Unit]
Description=Noggin Log Maintenance Service
# Wait for networking to be up, ensuring time sync and logging services are ready
After=network.target

[Service]
Type=oneshot
User=noggin_admin
Group=noggin_admin
WorkingDirectory=/home/noggin_admin/scripts
# critical: PYTHONPATH ensures the script can import 'common' modules found in the scripts dir
Environment="PYTHONPATH=/home/noggin_admin/scripts"
ExecStart=/usr/bin/python3 /home/noggin_admin/scripts/maintenance.py

[Install]
WantedBy=multi-user.target
```

### B. Timer File

The timer unit controls the schedule. By separating the schedule from the service definition, we gain flexibility and can trigger the maintenance task manually without waiting for the scheduled time.

Create the file **`/etc/systemd/system/noggin-maintenance.timer`** with the following content:

```ini
[Unit]
Description=Run Noggin Log Maintenance Daily

[Timer]
# Schedule execution daily at 02:00:00 AM server time
OnCalendar=*-*-* 02:00:00
# 'Persistent=true' ensures that if the system is down at 2 AM, 
# the job will run immediately upon the next boot.
Persistent=true

[Install]
WantedBy=timers.target
```

## 3. Installation & Verification Steps

Follow these steps to register the new units with the system and verify they are working correctly.

1. **Reload Systemd Configuration**:
   This command forces systemd to rescan the unit file directories and recognize your newly created service and timer files.
   
   ```bash
   sudo systemctl daemon-reload
   ```
2. **Enable and Start the Timer**:
   This command does two things: it sets the timer to start automatically on boot (`enable`) and starts it immediately (`--now`) so it begins counting down to the next 02:00 AM window.
   
   ```bash
   sudo systemctl enable --now noggin-maintenance.timer
   ```
3. **Verify the Timer is Active**:
   Check the list of active timers to confirm `noggin-maintenance` is scheduled.
   
   ```bash
   systemctl list-timers --all | grep noggin
   ```
   
   *Look at the `NEXT` column. It should show the execution time as tomorrow at 02:00.*
4. **Manual Test (Optional)**:
   You don't have to wait for 2 AM to test if the permissions and paths are correct. You can trigger the *service* directly (bypassing the timer) to perform an immediate maintenance run:
   
   ```bash
   sudo systemctl start noggin-maintenance.service
   ```
   
   **Check the execution logs:**
   Use `journalctl` to inspect the output of the service. This will show you the standard output and errors from the Python script.
   
   ```bash
   journalctl -u noggin-maintenance.service -f
   ```
   
   *Success criteria: You should see messages indicating "Maintenance complete" along with a count of files compressed or deleted.*

