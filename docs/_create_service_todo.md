# Setup Noggin Processing Service

### 3. Enable and Start the Service

bash

```bash
# Reload systemd to recognize new service
./manage_service.sh reload

# Enable service to start on boot
./manage_service.sh enable

# Start the service
./manage_service.sh start

# Check status
./manage_service.sh status
```

---

### 4. Monitor Service Logs

bash

```bash
# View recent logs
./manage_service.sh logs

# Follow logs in real-time
./manage_service.sh follow
```

## Run the dashboard:

```bash
python service_dashboard.py
```

---
Make it executable and run:

bash

```bash
chmod +x test_systemd_service.sh
./test_systemd_service.sh
```

---

### Stage 10 Validation Checklist

- [ ] Service file created at `/etc/systemd/system/noggin-processor.service`
- [ ] `manage_service.sh` created and executable
- [ ] Systemd daemon reloaded
- [ ] Service starts without errors
- [ ] Service status shows "active (running)"
- [ ] Logs visible via `journalctl` or `manage_service.sh logs`
- [ ] `service_dashboard.py` shows current statistics
- [ ] Service can be stopped/started via `manage_service.sh`
- [ ] Service enabled to start on boot

---

### Expected Output

**Service status:**

```
● noggin-processor.service - Noggin Continuous Processor
     Loaded: loaded (/etc/systemd/system/noggin-processor.service; enabled)
     Active: active (running) since Tue 2025-10-22 18:45:32 AWST; 2min ago
   Main PID: 12345 (python)
      Tasks: 2
     Memory: 45.2M
     CGroup: /system.slice/noggin-processor.service
             └─12345 /home/noggin_admin/scripts/.venv/bin/python noggin_continuous_processor.py
```

**Dashboard:**

```
================================================================================
NOGGIN PROCESSOR SERVICE DASHBOARD
================================================================================
Timestamp: 2025-10-22 18:47:15
================================================================================

SERVICE STATUS:
  Active:  ACTIVE
  Enabled: ENABLED

PROCESSING STATISTICS:
  Total Records:     1,234
  Complete:          1,150
  Pending:           50
  Failed:            20
  Partial:           10
  Interrupted:       4
  API Failed:        0

TODAY'S ACTIVITY:
  Total Processed:   234
  Completed:         220

WORK QUEUE:
  Remaining:         84
  Completion Rate:   93.2%

================================================================================
```


