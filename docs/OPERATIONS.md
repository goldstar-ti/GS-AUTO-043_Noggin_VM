# Noggin Processor - Operations Manual

Day-to-day operations guide for system administrators and operators.

---

## Table of Contents

- [Daily Operations](#daily-operations)
- [Weekly Operations](#weekly-operations)
- [Monthly Operations](#monthly-operations)
- [Common Tasks](#common-tasks)
- [Incident Response](#incident-response)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Performance Optimization](#performance-optimization)
- [Data Management](#data-management)

---

## Daily Operations

### Morning Health Check (5 minutes)

**Run at start of each business day:**
```bash
cd ~/scripts

# 1. Check service status
./manage_service.sh status

# 2. View dashboard
python service_dashboard.py

# 3. Check for errors in last 24 hours
./manage_service.sh logs | grep -i "error\|critical" | tail -20

# 4. Check disk space
df -h /mnt/data/noggin/

# 5. Verify database connectivity
psql -U noggin_admin -d noggin_db -c "SELECT COUNT(*) FROM noggin_data;"
```

**Expected Output:**
```
● noggin-processor.service - Noggin Continuous Processor
   Active: active (running) since [timestamp]

PROCESSING STATISTICS:
  Total Records:     X,XXX
  Complete:          X,XXX
  Pending:           XX
  Failed:            X

Disk Usage: XX% of XXG
```

**Red Flags:**
- ❌ Service: inactive (dead)
- ❌ Disk usage >85%
- ❌ Failed count increasing rapidly
- ❌ No activity in last 24 hours (check logs)

---

### Monitor Processing Queue (Throughout Day)

**Check processing progress:**
```bash
# Quick status
python service_dashboard.py

# Detailed query
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    processing_status,
    COUNT(*) as count
FROM noggin_data
WHERE processing_status IN ('pending', 'failed', 'partial', 'api_failed')
GROUP BY processing_status;
SQL
```

**Normal Behavior:**
- Queue draining steadily (pending count decreasing)
- Failed count stable or decreasing
- No pile-up of api_failed status

**Action Required:**
- Queue growing → Check if service is running
- High failure rate → Check API connectivity, bearer token
- Circuit breaker opening frequently → Review API health

---

### End-of-Day Summary (5 minutes)

**Run at end of business day:**
```bash
# Generate daily report
./daily_report.sh

# Review summary
cat /mnt/data/noggin/log/daily_report_$(date +%Y%m%d).txt

# Check today's completion rate
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    COUNT(*) as total_today,
    SUM(CASE WHEN processing_status = 'complete' THEN 1 ELSE 0 END) as completed,
    ROUND(100.0 * SUM(CASE WHEN processing_status = 'complete' THEN 1 ELSE 0 END) / COUNT(*), 1) as completion_rate
FROM noggin_data
WHERE updated_at >= CURRENT_DATE;
SQL
```

**Target Metrics:**
- Completion rate: >95%
- API failures: <5% of total
- Circuit breaker opens: 0-2 times per day

---

## Weekly Operations

### Sunday Maintenance Window (1 hour)

**Performed: Sunday 2:00-3:00 AM (automated) + manual review**

#### 1. Review Unknown Hashes (15 minutes)
```bash
# Export unknown hashes for each entity type
python manage_hashes.py export-unknown vehicle unknown_vehicles.csv
python manage_hashes.py export-unknown trailer unknown_trailers.csv
python manage_hashes.py export-unknown department unknown_departments.csv
python manage_hashes.py export-unknown team unknown_teams.csv

# Check counts
wc -l unknown_*.csv
```

**If unknown hashes found:**

1. Open CSV files
2. Research correct names (check Noggin system, ask stakeholders)
3. Fill in `name` column
4. Re-import resolved hashes:
```bash
   python manage_hashes.py import vehicle unknown_vehicles.csv
   python manage_hashes.py import trailer unknown_trailers.csv
   python manage_hashes.py import department unknown_departments.csv
   python manage_hashes.py import team unknown_teams.csv
```

5. Verify resolution:
```bash
   python manage_hashes.py stats
```

#### 2. Database Maintenance (15 minutes)
```bash
# Connect to database
psql -U noggin_admin -d noggin_db

# Update statistics for query optimization
ANALyse VERBOSE noggin_data;
ANALyse VERBOSE attachments;
ANALyse VERBOSE entity_hashes;

# Check for bloat and vacuum if needed
VACUUM ANALyse noggin_data;
VACUUM ANALyse attachments;

# Check index health
\di+

# Check table sises
SELECT 
    schemaname,
    tablename,
    pg_sise_pretty(pg_total_relation_sise(schemaname||'.'||tablename)) as sise
FROM pg_tables
WHERE schemaname = 'noggin_schema'
ORDER BY pg_total_relation_sise(schemaname||'.'||tablename) DESC;
```

#### 3. Review Error Logs (15 minutes)
```bash
# Find most common errors this week
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    error_type,
    COUNT(*) as occurrences,
    LEFT(error_message, 100) as sample_message
FROM processing_errors
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY error_type, LEFT(error_message, 100)
ORDER BY COUNT(*) DESC
LIMIT 20;
SQL

# Check for patterns
grep -r "error" /mnt/data/noggin/log/*.log | \
    grep "$(date -d '7 days ago' +%Y-%m-%d)" | \
    cut -d: -f3- | \
    sort | uniq -c | sort -rn | head -20
```

**Common Errors and Actions:**
- **Connection errors** → Check network, API availability
- **Authentication errors** → Verify bearer token valid
- **Rate limit errors** → Adjust circuit breaker settings
- **Validation errors** → Check attachment downloads

#### 4. Backup Verification (10 minutes)
```bash
# Check backup directory
ls -lh /mnt/data/noggin/backups/database/ | tail -10

# Verify latest backup sise (should be consistent)
du -h /mnt/data/noggin/backups/database/noggin_db_backup_*.sql.gz | tail -5

# Test restore (on test database)
gunzip -c /mnt/data/noggin/backups/database/noggin_db_backup_$(date +%Y%m%d)*.sql.gz | \
    psql -U noggin_admin -d noggin_db_test

# Check attachment backup
du -sh /mnt/backup/noggin/attachments/
```

#### 5. Performance Review (5 minutes)
```bash
# Average processing time per TIP (last 7 days)
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    DATE(updated_at) as date,
    COUNT(*) as tips_processed,
    ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))), 1) as avg_seconds,
    MIN(EXTRACT(EPOCH FROM (updated_at - created_at))) as min_seconds,
    MAX(EXTRACT(EPOCH FROM (updated_at - created_at))) as max_seconds
FROM noggin_data
WHERE updated_at >= CURRENT_DATE - INTERVAL '7 days'
  AND processing_status = 'complete'
GROUP BY DATE(updated_at)
ORDER BY date DESC;
SQL

# Circuit breaker statistics
python -c "
from common import ConfigLoader, CircuitBreaker
config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')
cb = CircuitBreaker(config)
print(cb.get_statistics())
"
```

---

## Monthly Operations

### First Sunday of Month (2 hours)

#### 1. System Updates (30 minutes)
```bash
# Stop service
./manage_service.sh stop

# Update system packages
sudo apt update
sudo apt upgrade -y

# Update Python packages
source .venv/bin/activate
pip list --outdated
# Review and update if needed:
# pip install --upgrade package_name

# Restart service
./manage_service.sh start

# Monitor for 15 minutes
./manage_service.sh follow
```

#### 2. Storage Management (30 minutes)
```bash
# Check storage growth trends
du -sh /mnt/data/noggin/output/

# Breakdown by year/month
du -h /mnt/data/noggin/output/ --max-depth=2

# Check oldest data
find /mnt/data/noggin/output/ -type f -printf '%T+ %p\n' | sort | head -20

# Archive old data if needed (>1 year old)
find /mnt/data/noggin/output/ -type d -mtime +365 | \
    while read dir; do
        tar czf "archive_$(basename $dir)_$(date +%Y%m%d).tar.gz" "$dir"
        # After verifying archive, optionally remove:
        # rm -rf "$dir"
    done
```

#### 3. Database Optimization (30 minutes)
```bash
# Full database analysis
psql -U noggin_admin -d noggin_db << 'SQL'

-- Rebuild indexes if heavily fragmented
REINDEX TABLE noggin_data;
REINDEX TABLE attachments;

-- Update statistics
ANALyse VERBOSE;

-- Check for missing indexes
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'noggin_schema'
  AND n_distinct > 100
ORDER BY abs(correlation) DESC;

-- Check slow queries (if logging enabled)
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
WHERE query LIKE '%noggin_data%'
ORDER BY mean_time DESC
LIMIT 10;

SQL
```

#### 4. Permanently Failed Review (30 minutes)
```bash
# Export permanently failed TIPs for review
psql -U noggin_admin -d noggin_db -c "
COPY (
    SELECT 
        tip,
        lcd_inspection_id,
        last_error_message,
        retry_count,
        updated_at
    FROM noggin_data
    WHERE permanently_failed = TRUE
    ORDER BY updated_at DESC
) TO STDOUT WITH CSV HEADER
" > permanently_failed_$(date +%Y%m%d).csv

# Review and decide:
# - Can some be retried? (reset permanently_failed flag)
# - Are errors fixable? (update bearer token, fix API issues)
# - Document unrecoverable failures
```

**Reset permanently failed TIPs for retry:**
```sql
-- After fixing underlying issue
UPDATE noggin_data
SET permanently_failed = FALSE,
    retry_count = 0,
    processing_status = 'pending',
    next_retry_at = NULL
WHERE tip IN ('tip1', 'tip2', 'tip3');
```

---

## Common Tasks

### Adding New CSV Files for Processing

**Process: Add TIPs via CSV import**
```bash
# 1. Place CSV file in input folder
cp new_tips.csv /mnt/data/noggin/input/

# 2. CSV format must have 'tip' in first column
# and one of: lcdInspectionId, couplingId, trailerAuditId

# 3. Import will happen automatically on next cycle
# OR trigger manually:
python -c "
from common import ConfigLoader, DatabaseConnectionManager, CSVImporter
config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')
db = DatabaseConnectionManager(config)
importer = CSVImporter(config, db)
result = importer.scan_and_import_csv_files()
print(f'Imported: {result[\"total_imported\"]} TIPs')
db.close_all()
"

# 4. Verify import
python service_dashboard.py

# 5. Check for moved file in processed/ folder
ls -lh /mnt/data/noggin/input/processed/ | tail -5
```

---

### Reprocessing Failed TIPs

**Process: Retry failed inspections**
```bash
# 1. Identify failed TIPs
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    tip,
    lcd_inspection_id,
    processing_status,
    retry_count,
    last_error_message
FROM noggin_data
WHERE processing_status IN ('failed', 'partial', 'api_failed')
  AND retry_count < 5
ORDER BY updated_at DESC
LIMIT 20;
SQL

# 2. Reset specific TIPs for retry
psql -U noggin_admin -d noggin_db << 'SQL'
UPDATE noggin_data
SET retry_count = 0,
    next_retry_at = NULL,
    processing_status = 'pending'
WHERE tip IN ('tip_hash_1', 'tip_hash_2');
SQL

# 3. Monitor reprocessing
./manage_service.sh follow
```

---

### Updating API Bearer Token

**Process: Replace expired token**
```bash
# 1. Stop service
./manage_service.sh stop

# 2. Update config file
nano config/base_config.ini
# Update bearer_token value

# 3. Test token
python -c "
import requests
from common import ConfigLoader
config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')
headers = config.get_api_headers()
response = requests.get(
    'https://services.apse2.elasticnoggin.com/rest/object/loadComplianceCheckDriverLoader/TEST_TIP',
    headers=headers
)
print(f'Status: {response.status_code}')
"

# 4. Restart service
./manage_service.sh start

# 5. Monitor logs for successful authentication
./manage_service.sh follow | grep -i "auth\|401"
```

---

### Adding New Entity Hashes

**Process: Import vehicle/trailer/department/team hashes**
```bash
# 1. Prepare CSV file
# Format: hash,name
cat > new_vehicles.csv << EOF
hash,name
abc123def456,TRUCK-NEW-001
xyz789uvw012,TRUCK-NEW-002
EOF

# 2. Import hashes
python manage_hashes.py import vehicle new_vehicles.csv

# 3. Verify import
python manage_hashes.py stats

# 4. Check if unknown hashes resolved
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT COUNT(*) as remaining_unknown
FROM unknown_hashes
WHERE entity_type = 'vehicle'
  AND resolved_at IS NULL;
SQL
```

---

### Checking Individual TIP Status

**Process: Look up specific inspection**
```bash
# By TIP hash
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    tip,
    object_type,
    processing_status,
    lcd_inspection_id,
    inspection_date,
    total_attachments,
    completed_attachment_count,
    retry_count,
    last_error_message,
    updated_at
FROM noggin_data
WHERE tip = 'YOUR_TIP_HASH_HERE';
SQL

# By LCD Inspection ID
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    tip,
    processing_status,
    lcd_inspection_id,
    inspection_date,
    vehicle,
    trailer,
    total_attachments,
    completed_attachment_count
FROM noggin_data
WHERE lcd_inspection_id = 'LCD - 045289';
SQL

# Check attachments
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    filename,
    attachment_status,
    file_sise_bytes / 1024 / 1024 as sise_mb,
    download_duration_seconds,
    attachment_validation_status
FROM attachments
WHERE record_tip = 'YOUR_TIP_HASH_HERE'
ORDER BY attachment_sequence;
SQL
```

---

### Manual TIP Processing

**Process: Process single TIP manually**
```bash
# 1. Create temporary CSV
cat > manual_tip.csv << EOF
tip
your_tip_hash_here
EOF

# 2. Stop continuous processor
./manage_service.sh stop

# 3. Run manual processing
python noggin_processor.py

# 4. Check results
python service_dashboard.py

# 5. Restart continuous processor
./manage_service.sh start
```

---

### Clearing Processing Queue

**Process: Mark all pending as complete (use carefully!)**
```bash
# WARNING: Only use if you need to skip processing certain TIPs

# 1. Export list first (for records)
psql -U noggin_admin -d noggin_db -c "
COPY (
    SELECT tip, lcd_inspection_id, inspection_date
    FROM noggin_data
    WHERE processing_status = 'pending'
) TO STDOUT WITH CSV HEADER
" > skipped_tips_$(date +%Y%m%d).csv

# 2. Mark as skipped (create new status if needed)
psql -U noggin_admin -d noggin_db << 'SQL'
UPDATE noggin_data
SET processing_status = 'skipped',
    last_error_message = 'Manually skipped on 2025-10-22'
WHERE processing_status = 'pending';
SQL
```

---

## Incident Response

### Incident Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| **P1 - Critical** | Service down, data loss | 15 minutes | Immediate |
| **P2 - High** | Degraded performance, high error rate | 1 hour | After 2 hours |
| **P3 - Medium** | Non-critical issues, workarounds available | 4 hours | After 1 day |
| **P4 - Low** | Cosmetic issues, feature requests | Next business day | N/A |

---

### P1: Service Completely Down

**Symptoms:**
- Service status: inactive (dead)
- No logs being written
- Cannot start service

**Response:**
```bash
# 1. Check service status
systemctl status noggin-processor

# 2. Check recent logs
journalctl -u noggin-processor -n 100 --no-pager

# 3. Try restart
sudo systemctl restart noggin-processor

# 4. If restart fails, check dependencies
# Database
systemctl status postgresql
psql -U noggin_admin -d noggin_db -c "SELECT 1"

# Python environment
source ~/scripts/.venv/bin/activate
python -c "from common import ConfigLoader; print('OK')"

# 5. Check configuration
python -c "
from common import ConfigLoader
try:
    config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')
    print('Config OK')
except Exception as e:
    print(f'Config Error: {e}')
"

# 6. Check disk space
df -h

# 7. Check permissions
ls -la ~/scripts/
ls -la /mnt/data/noggin/

# 8. Manual start for debugging
cd ~/scripts
source .venv/bin/activate
python noggin_continuous_processor.py
```

**Escalation:**
- If not resolved in 30 minutes, escalate to senior admin
- If database issue, escalate to DBA
- If network issue, escalate to network team

---

### P2: High Error Rate / Circuit Breaker Opening

**Symptoms:**
- Circuit breaker opening frequently (>5 times/hour)
- API failure rate >20%
- Processing queue growing rapidly

**Response:**
```bash
# 1. Check circuit breaker state
python -c "
from common import ConfigLoader, CircuitBreaker
config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')
cb = CircuitBreaker(config)
stats = cb.get_statistics()
print(f'State: {stats[\"state\"]}')
print(f'Failure rate: {stats[\"failure_rate\"]}%')
print(f'Total requests: {stats[\"total_requests\"]}')
"

# 2. Check recent API errors
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    error_type,
    COUNT(*) as count,
    MAX(created_at) as last_occurrence
FROM processing_errors
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
GROUP BY error_type
ORDER BY count DESC;
SQL

# 3. Test API manually
python -c "
import requests
from common import ConfigLoader
config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')
headers = config.get_api_headers()
response = requests.get(
    'https://services.apse2.elasticnoggin.com/rest/object/loadComplianceCheckDriverLoader/test',
    headers=headers,
    timeout=10
)
print(f'Status: {response.status_code}')
if response.status_code != 200:
    print(f'Error: {response.text[:200]}')
"

# 4. Check API status page (if available)
# Contact Noggin support if API issues

# 5. Temporarily increase circuit breaker tolerance
nano config/base_config.ini
# Adjust:
# failure_threshold_percent = 60  # Increased from 50
# circuit_open_duration_seconds = 900  # Increased from 300

./manage_service.sh restart
```

**Mitigation:**
- If API issue confirmed, pause service until resolved
- If token expired, update token immediately
- If network issue, check firewall/routing

---

### P3: Slow Processing

**Symptoms:**
- Queue not draining
- Processing time per TIP >5 minutes
- High CPU or memory usage

**Response:**
```bash
# 1. Check system resources
htop
iotop
df -h

# 2. Check database performance
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    pid,
    usename,
    application_name,
    state,
    query_start,
    LEFT(query, 100) as query
FROM pg_stat_activity
WHERE datname = 'noggin_db'
  AND state = 'active'
ORDER BY query_start;
SQL

# 3. Check for long-running queries
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    pid,
    now() - query_start as duration,
    query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '5 minutes'
ORDER BY duration DESC;
SQL

# 4. Check attachment download speeds
tail -100 /mnt/data/noggin/log/*.log | \
    grep "Downloaded:" | \
    awk '{print $(NF-1), $NF}'

# 5. Review circuit breaker state
# May be throttling requests

# 6. Optimise if needed
# - Increase tips_per_batch
# - Adjust attachment_pause
# - Check network bandwidth
```

---

### P4: Unknown Hashes Accumulating

**Symptoms:**
- Many "Unknown vehicle/trailer..." entries
- Reports show incomplete data

**Response:**
```bash
# 1. Export unknown hashes
python manage_hashes.py export-unknown vehicle unknown_vehicles.csv
python manage_hashes.py export-unknown trailer unknown_trailers.csv
python manage_hashes.py export-unknown department unknown_departments.csv
python manage_hashes.py export-unknown team unknown_teams.csv

# 2. Research correct names
# - Check Noggin web interface
# - Ask fleet managers
# - Review previous records

# 3. Fill in name column in CSV files

# 4. Re-import resolved hashes
python manage_hashes.py import vehicle unknown_vehicles.csv
python manage_hashes.py import trailer unknown_trailers.csv
python manage_hashes.py import department unknown_departments.csv
python manage_hashes.py import team unknown_teams.csv

# 5. Reprocess affected TIPs if needed
psql -U noggin_admin -d noggin_db << 'SQL'
UPDATE noggin_data
SET processing_status = 'pending',
    retry_count = 0
WHERE has_unknown_hashes = TRUE
  AND processing_status = 'complete';
SQL
```

---

## Troubleshooting Guide

### Service Won't Start

**Problem:** `systemctl start noggin-processor` fails

**Diagnosis:**
```bash
# Check service logs
journalctl -u noggin-processor -n 50

# Check for Python errors
cd ~/scripts
source .venv/bin/activate
python noggin_continuous_processor.py
```

**Common Causes:**

1. **Database connection failed**
```bash
   # Test connection
   psql -U noggin_admin -d noggin_db -c "SELECT 1"
   
   # If fails, check PostgreSQL running
   sudo systemctl status postgresql
   sudo systemctl start postgresql
```

2. **Configuration error**
```bash
   # Validate config
   python -c "from common import ConfigLoader; ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')"
```

3. **Permission denied**
```bash
   # Check ownership
   ls -la ~/scripts/
   sudo chown -R noggin_admin:noggin_admin ~/scripts/
```

4. **Module not found**
```bash
   # Reinstall dependencies
   source .venv/bin/activate
   pip install -r requirements.txt
```

---

### Database Connection Errors

**Problem:** "could not connect to server: Connection refused"

**Diagnosis:**
```bash
# Is PostgreSQL running?
sudo systemctl status postgresql

# Can connect locally?
psql -U noggin_admin -d noggin_db

# Check pg_hba.conf
sudo cat /etc/postgresql/*/main/pg_hba.conf | grep noggin
```

**Solutions:**

1. **PostgreSQL not running**
```bash
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
```

2. **Wrong credentials**
```bash
   # Reset password
   sudo -u postgres psql << EOF
   ALTER USER noggin_admin WITH PASSWORD 'new_password';
   EOF
   
   # Update config
   nano config/base_config.ini
```

3. **Connection not allowed**
```bash
   # Edit pg_hba.conf
   sudo nano /etc/postgresql/*/main/pg_hba.conf
   
   # Add:
   local   noggin_db   noggin_admin   scram-sha-256
   
   # Reload
   sudo systemctl reload postgresql
```

---

### API Authentication Failures (401)

**Problem:** "Authentication failed... Status code: 401"

**Diagnosis:**
```bash
# Test token manually
python -c "
import requests
from common import ConfigLoader
config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')
headers = config.get_api_headers()
print(f'Headers: {headers}')
response = requests.get(
    'https://services.apse2.elasticnoggin.com/rest/object/loadComplianceCheckDriverLoader/test',
    headers=headers
)
print(f'Status: {response.status_code}')
print(f'Response: {response.text[:200]}')
"
```

**Solutions:**

1. **Token expired**
   - Contact Noggin admin for new token
   - Update `bearer_token` in config
   - Restart service

2. **Token malformed**
   - Check for line breaks in config file
   - Token should be one continuous line
   - No spaces before/after token

3. **Wrong namespace**
   - Verify `namespace` value in config
   - Should match your Noggin environment

---

### Attachments Not Downloading

**Problem:** Processing completes but no image files

**Diagnosis:**
```bash
# Check attachment status
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    attachment_status,
    COUNT(*) as count
FROM attachments
WHERE download_started_at >= CURRENT_DATE
GROUP BY attachment_status;
SQL

# Check for errors
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT 
    filename,
    attachment_status,
    last_error_message
FROM attachments
WHERE attachment_status = 'failed'
ORDER BY download_started_at DESC
LIMIT 10;
SQL

# Check file system
ls -lh /mnt/data/noggin/output/$(date +%Y)/$(date +%m)/ | tail -20
```

**Solutions:**

1. **Permission denied**
```bash
   sudo chown -R noggin_admin:noggin_admin /mnt/data/noggin/output/
   chmod 755 /mnt/data/noggin/output/
```

2. **Disk full**
```bash
   df -h /mnt/data/noggin/
   # Free space if needed
```

3. **Invalid attachment URL**
   - Check `media_service_url` in config
   - Verify URLs in API response

---

### High Memory Usage

**Problem:** System running out of memory

**Diagnosis:**
```bash
# Check memory usage
free -h

# Which process?
ps aux --sort=-%mem | head -10

# PostgreSQL memory
ps aux | grep postgres | awk '{sum+=$6} END {print sum/1024 " MB"}'
```

**Solutions:**

1. **PostgreSQL consuming memory**
```bash
   # Adjust PostgreSQL config
   sudo nano /etc/postgresql/*/main/postgresql.conf
   
   # Reduce:
   shared_buffers = 512MB
   work_mem = 8MB
   
   sudo systemctl restart postgresql
```

2. **Python process memory leak**
```bash
   # Restart service
   ./manage_service.sh restart
   
   # Monitor memory growth
   watch -n 5 'ps aux | grep python'
```

3. **Too many connections**
```bash
   # Reduce pool sise
   nano config/base_config.ini
   # Set pool_max_connections = 5
   
   ./manage_service.sh restart
```

---

### Disk Space Issues

**Problem:** Disk usage >90%

**Diagnosis:**
```bash
# Overall usage
df -h /mnt/data/noggin/

# What's using space?
du -sh /mnt/data/noggin/*
du -h /mnt/data/noggin/output/ --max-depth=2 | sort -hr | head -20

# Large files
find /mnt/data/noggin/ -type f -sise +100M -exec ls -lh {} \;
```

**Solutions:**

1. **Archive old data**
```bash
   # Compress data >1 year old
   find /mnt/data/noggin/output/ -type d -mtime +365 | \
       tar czf archive_$(date +%Y%m%d).tar.gz -T -
   
   # Move archive to external storage
   # Delete original after verification
```

2. **Clean old logs**
```bash
   # Remove logs >90 days old
   find /mnt/data/noggin/log/ -name "*.log" -mtime +90 -delete
```

3. **Clean temporary files**
```bash
   # Remove .tmp files
   find /mnt/data/noggin/ -name "*.tmp" -delete
```

---

## Performance Optimization

### Identifying Bottlenecks
```bash
# 1. Check CPU usage
top -b -n 1 | head -20

# 2. Check I/O wait
iostat -x 1 5

# 3. Check network
iftop -i eth0
# or
netstat -i
```

# 4. Check database query performance
psql -U noggin_admin -d noggin_db << 'SQL'
```sql
SELECT 
    substring(query, 1, 50) AS short_query,
    calls,
    total_time / 1000 AS total_seconds,
    mean_time / 1000 AS mean_seconds,
    max_time / 1000 AS max_seconds
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_time DESC
LIMIT 10;
```

# 5. Profile Python application
# Add to noggin_processor.py temporarily:
```python
import cProfile
cProfile.run('main()', 'profile_output.prof')
```
# Analyse:
python -m pstats profile_output.prof
Optimization Strategies
If CPU Bound
Symptoms:

CPU usage consistently >80%
Processing slow
Low I/O wait

Solutions:

Reduce concurrent operations

ini   [database]
   pool_max_connections = 5  # Reduce from 10
   
   [retry]
   tips_per_batch = 25  # Reduce from 50

Optimise database queries

sql   -- Add missing indexes
   CREATE INDEX idx_custom ON table_name(column_name);
   
   -- Analyse query plans
   EXPLAIN ANALyse SELECT ...;

Consider vertical scaling

Upgrade to more CPU cores



If I/O Bound
Symptoms:

High I/O wait (>20%)
Disk usage at capacity
Slow attachment downloads

Solutions:

Optimise disk access

bash   # Move to SSD if on HDD
   # Check current disk type:
   lsblk -d -o name,rota
   # (rota=1 means HDD, rota=0 means SSD)

Reduce attachment pause

ini   [processing]
   attachment_pause = 0  # Remove delay between downloads

Database on separate disk

bash   # Move PostgreSQL data to faster disk
   sudo -u postgres psql
   SHOW data_directory;
   
   # Follow PostgreSQL migration guide
If Network Bound
Symptoms:

Slow attachment downloads
High retry count
Circuit breaker opening

Solutions:

Check bandwidth

bash   # Monitor network usage
   nload
   
   # Test download speed
   wget --output-document=/dev/null https://services.apse2.elasticnoggin.com/media/test

Adjust timeouts

ini   [api]
   timeout = 120  # Increase from 60
   
   [processing]
   max_api_retries = 7  # Increase from 5

Contact network team

Check for firewall throttling
Verify no bandwidth caps



If Database Bound
Symptoms:

Long-running queries
High database CPU
Lock contention

Solutions:

Optimise queries

sql   -- Find slow queries
   SELECT 
       query,
       calls,
       total_time,
       mean_time,
       rows
   FROM pg_stat_statements
   ORDER BY total_time DESC
   LIMIT 10;
   
   -- Add indexes for slow queries
   -- Use EXPLAIN ANALyse to identify bottlenecks

Tune PostgreSQL

ini   # /etc/postgresql/*/main/postgresql.conf
   shared_buffers = 2GB
   effective_cache_sise = 6GB
   work_mem = 32MB
   maintenance_work_mem = 512MB

Vacuum regularly

bash   # Set up auto-vacuum
   psql -U noggin_admin -d noggin_db << 'SQL'
   ALTER TABLE noggin_data SET (
       autovacuum_vacuum_scale_factor = 0.1,
       autovacuum_analyse_scale_factor = 0.05
   );
   SQL

Data Management
Archiving Old Data
When to archive:

Data >2 years old
Disk space >80%
Compliance retention met

Process:
bash# 1. Identify data to archive
find /mnt/data/noggin/output/ -type d -mtime +730 | head -20

# 2. Create archive
ARCHIVE_DATE=$(date -d '2 years ago' +%Y-%m-%d)
tar czf "archive_before_${ARCHIVE_DATE}_$(date +%Y%m%d).tar.gz" \
    $(find /mnt/data/noggin/output/ -type d -mtime +730)

# 3. Verify archive
tar tzf archive_before_*.tar.gz | head -20

# 4. Calculate sises
du -sh archive_before_*.tar.gz
find /mnt/data/noggin/output/ -type d -mtime +730 | \
    xargs du -sh | awk '{sum+=$1} END {print sum " MB to be freed"}'

# 5. Move archive to external storage
rsync -avz archive_before_*.tar.gz backup-server:/archives/noggin/

# 6. Verify remote copy
ssh backup-server "ls -lh /archives/noggin/archive_before_*.tar.gz"

# 7. Remove local data (ONLY after verification!)
find /mnt/data/noggin/output/ -type d -mtime +730 -exec rm -rf {} +

# 8. Update database records
psql -U noggin_admin -d noggin_db << SQL
UPDATE noggin_data
SET archived = TRUE,
    archived_at = CURRENT_TIMESTAMP
WHERE inspection_date < '$ARCHIVE_DATE';
SQL
Database Cleanup
Remove old errors:
sql-- Errors older than 6 months
DELETE FROM processing_errors
WHERE created_at < CURRENT_DATE - INTERVAL '6 months';

-- Vacuum after large delete
VACUUM ANALyse processing_errors;
Remove duplicate records:
sql-- Find duplicates
SELECT tip, COUNT(*)
FROM noggin_data
GROUP BY tip
HAVING COUNT(*) > 1;

-- Keep only latest record
DELETE FROM noggin_data a
USING noggin_data b
WHERE a.tip = b.tip
  AND a.created_at < b.created_at;
Clean up orphaned attachments:
sql-- Find attachments with no parent record
SELECT a.record_tip, a.filename
FROM attachments a
LEFT JOIN noggin_data n ON a.record_tip = n.tip
WHERE n.tip IS NULL;

-- Delete orphaned records
DELETE FROM attachments
WHERE record_tip NOT IN (SELECT tip FROM noggin_data);
Data Export
Export for reporting:
bash# Export to CSV
psql -U noggin_admin -d noggin_db << 'SQL' > report_$(date +%Y%m%d).csv
COPY (
    SELECT 
        lcd_inspection_id,
        inspection_date,
        vehicle,
        trailer,
        department,
        team,
        load_compliance,
        total_attachments,
        processing_status
    FROM noggin_data
    WHERE inspection_date >= '2025-01-01'
    ORDER BY inspection_date DESC
) TO STDOUT WITH CSV HEADER;
SQL

# Export with attachments list
psql -U noggin_admin -d noggin_db << 'SQL' > detailed_report_$(date +%Y%m%d).csv
COPY (
    SELECT 
        n.lcd_inspection_id,
        n.inspection_date,
        n.vehicle,
        n.trailer,
        a.filename,
        a.file_sise_bytes / 1024 / 1024 as sise_mb,
        a.attachment_status
    FROM noggin_data n
    LEFT JOIN attachments a ON n.tip = a.record_tip
    WHERE n.inspection_date >= '2025-01-01'
    ORDER BY n.inspection_date DESC, a.attachment_sequence
) TO STDOUT WITH CSV HEADER;
SQL
Data Validation
Check data integrity:
bash# Run validation queries
psql -U noggin_admin -d noggin_db << 'SQL'

-- 1. Check for missing data
SELECT 'Missing LCD Inspection IDs' as issue, COUNT(*) as count
FROM noggin_data
WHERE lcd_inspection_id IS NULL
UNION ALL
SELECT 'Missing Inspection Dates', COUNT(*)
FROM noggin_data
WHERE inspection_date IS NULL
UNION ALL
SELECT 'Missing Attachments', COUNT(*)
FROM noggin_data
WHERE total_attachments > 0
  AND completed_attachment_count = 0;

-- 2. Check for mismatched attachment counts
SELECT 
    n.tip,
    n.lcd_inspection_id,
    n.total_attachments as expected,
    COUNT(a.attachment_tip) as actual
FROM noggin_data n
LEFT JOIN attachments a ON n.tip = a.record_tip
WHERE n.total_attachments > 0
GROUP BY n.tip, n.lcd_inspection_id, n.total_attachments
HAVING n.total_attachments != COUNT(a.attachment_tip);

-- 3. Check for file system vs database mismatch
SELECT 
    tip,
    lcd_inspection_id,
    total_attachments,
    completed_attachment_count
FROM noggin_data
WHERE processing_status = 'complete'
  AND total_attachments != completed_attachment_count;

SQL
Recovery from Data Corruption
If data corruption detected:
bash# 1. Stop service immediately
./manage_service.sh stop

# 2. Backup current state (even if corrupted)
pg_dump -U noggin_admin noggin_db | \
    gzip > corrupted_backup_$(date +%Y%m%d_%H%M%S).sql.gz

# 3. Identify corruption extent
psql -U noggin_admin -d noggin_db << 'SQL'
-- Check table integrity
SELECT 
    schemaname,
    tablename,
    pg_sise_pretty(pg_total_relation_sise(schemaname||'.'||tablename)) as sise
FROM pg_tables
WHERE schemaname = 'noggin_schema'
ORDER BY pg_total_relation_sise(schemaname||'.'||tablename) DESC;

-- Run consistency checks
SELECT * FROM noggin_data WHERE tip IS NULL LIMIT 10;
SQL

# 4. Restore from last good backup
# Determine last known good backup date
ls -lth /mnt/data/noggin/backups/database/ | head -10

# Restore specific backup
gunzip -c /mnt/data/noggin/backups/database/noggin_db_backup_YYYYMMDD_*.sql.gz | \
    psql -U noggin_admin noggin_db

# 5. Verify restoration
psql -U noggin_admin -d noggin_db << 'SQL'
SELECT COUNT(*) FROM noggin_data;
SELECT MAX(updated_at) FROM noggin_data;
SQL

# 6. Reprocess data since backup
# Identify gap period
BACKUP_DATE="2025-10-15"  # Date of backup

psql -U noggin_admin -d noggin_db << SQL
UPDATE noggin_data
SET processing_status = 'pending',
    retry_count = 0,
    next_retry_at = NULL
WHERE updated_at >= '$BACKUP_DATE'
  AND processing_status NOT IN ('complete', 'skipped');
SQL

# 7. Restart service
./manage_service.sh start

# 8. Monitor recovery
./manage_service.sh follow

Standard Operating Procedures (SOPs)
SOP-001: Service Restart
Purpose: Safely restart service without data loss
Frequency: As needed (updates, config changes)
Procedure:

Check current processing state

bash   python service_dashboard.py

Stop service gracefully

bash   ./manage_service.sh stop
   # Wait for current TIP to complete (max 5 minutes)

Verify service stopped

bash   ./manage_service.sh status
   # Should show: inactive (dead)

Make changes if needed

bash   # Edit config, update code, etc.

Start service

bash   ./manage_service.sh start

Verify startup

bash   ./manage_service.sh status
   # Should show: active (running)
   
   ./manage_service.sh logs | tail -50
   # Check for errors

Monitor for 15 minutes

bash   ./manage_service.sh follow
   # Press Ctrl+C when satisfied

Document restart

bash   echo "$(date): Service restarted - Reason: [YOUR_REASON]" >> \
       /mnt/data/noggin/log/maintenance.log

SOP-002: Weekly Hash Resolution
Purpose: Maintain complete entity name resolution
Frequency: Weekly (Sunday maintenance window)
Procedure:

Export unknown hashes

bash   cd ~/scripts
   
   python manage_hashes.py export-unknown vehicle unknown_vehicles.csv
   python manage_hashes.py export-unknown trailer unknown_trailers.csv
   python manage_hashes.py export-unknown department unknown_departments.csv
   python manage_hashes.py export-unknown team unknown_teams.csv

Check counts

bash   wc -l unknown_*.csv
   # Note: Line 1 is header, so actual count = lines - 1

If unknown hashes found:

Open CSV files in spreadsheet editor
Research correct names:

Check Noggin web interface
Contact fleet manager
Review similar records in database


Fill in name column
Save files


Import resolved hashes

bash   python manage_hashes.py import vehicle unknown_vehicles.csv
   python manage_hashes.py import trailer unknown_trailers.csv
   python manage_hashes.py import department unknown_departments.csv
   python manage_hashes.py import team unknown_teams.csv

Verify import

bash   python manage_hashes.py stats

Optional: Reprocess affected records

sql   -- If you want to update already-processed records with new names
   UPDATE noggin_data
   SET processing_status = 'pending',
       has_unknown_hashes = FALSE
   WHERE has_unknown_hashes = TRUE
     AND processing_status = 'complete';

Document resolution

bash   echo "$(date): Resolved $(wc -l < unknown_vehicles.csv) vehicles, \
   $(wc -l < unknown_trailers.csv) trailers" >> \
       /mnt/data/noggin/log/hash_resolution.log

SOP-003: Monthly Database Maintenance
Purpose: Maintain database performance and health
Frequency: Monthly (first Sunday)
Procedure:

Create maintenance window notice

bash   wall "Noggin Processor maintenance starting in 30 minutes"

Stop service

bash   ./manage_service.sh stop

Backup database

bash   pg_dump -U noggin_admin noggin_db | \
       gzip > /mnt/data/noggin/backups/database/pre_maintenance_$(date +%Y%m%d).sql.gz

Run maintenance

sql   psql -U noggin_admin -d noggin_db << 'SQL'
   
   -- Update statistics
   ANALyse VERBOSE noggin_data;
   ANALyse VERBOSE attachments;
   ANALyse VERBOSE entity_hashes;
   
   -- Rebuild indexes
   REINDEX TABLE noggin_data;
   REINDEX TABLE attachments;
   
   -- Vacuum
   VACUUM ANALyse noggin_data;
   VACUUM ANALyse attachments;
   
   -- Check for bloat
   SELECT 
       schemaname,
       tablename,
       pg_sise_pretty(pg_total_relation_sise(schemaname||'.'||tablename)) as total_sise
   FROM pg_tables
   WHERE schemaname = 'noggin_schema'
   ORDER BY pg_total_relation_sise(schemaname||'.'||tablename) DESC;
   
   SQL

Clean old data

sql   -- Remove old processing errors (>6 months)
   DELETE FROM processing_errors
   WHERE created_at < CURRENT_DATE - INTERVAL '6 months';
   
   -- Clean unknown hashes that were resolved
   DELETE FROM unknown_hashes
   WHERE resolved_at IS NOT NULL
     AND resolved_at < CURRENT_DATE - INTERVAL '3 months';

Verify database health

bash   psql -U noggin_admin -d noggin_db << 'SQL'
   SELECT COUNT(*) as total_records FROM noggin_data;
   SELECT COUNT(*) as total_attachments FROM attachments;
   SELECT COUNT(*) as total_hashes FROM entity_hashes;
   SQL

Restart service

bash   ./manage_service.sh start

Monitor for 1 hour

bash   ./manage_service.sh follow

Document maintenance

bash   cat >> /mnt/data/noggin/log/maintenance.log << EOF
   $(date): Monthly maintenance completed
   - Database vacuumed and analysed
   - Indexes rebuilt
   - Old errors cleaned
   - Service restarted successfully
   EOF

SOP-004: Bearer Token Update
Purpose: Update API authentication token
Frequency: As needed (token expiry, security refresh)
Procedure:

Obtain new token

Contact Noggin administrator
Request new bearer token
Note expiry date


Test new token

bash   # Test before updating config
   python -c "
   import requests
   
   headers = {
       'en-namespace': 'YOUR_NAMESPACE',
       'authorization': 'Bearer NEW_TOKEN_HERE'
   }
   
   response = requests.get(
       'https://services.apse2.elasticnoggin.com/rest/object/loadComplianceCheckDriverLoader/test',
       headers=headers
   )
   
   print(f'Status: {response.status_code}')
   if response.status_code != 200:
       print(f'Error: {response.text}')
   "

Stop service

bash   ./manage_service.sh stop

Backup current config

bash   cp config/base_config.ini config/base_config.ini.backup_$(date +%Y%m%d)

Update configuration

bash   nano config/base_config.ini
   # Update bearer_token value
   # Ensure token is on single line, no spaces

Verify configuration

bash   python -c "
   from common import ConfigLoader
   config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_driver_loader_config.ini')
   headers = config.get_api_headers()
   print('Token length:', len(headers['authorization']))
   print('Starts with Bearer:', headers['authorization'].startswith('Bearer'))
   "

Start service

bash   ./manage_service.sh start

Verify authentication

bash   # Watch logs for successful API calls
   ./manage_service.sh follow | grep -i "auth\|401\|successful"

Document change

bash   echo "$(date): Bearer token updated - Expiry: [DATE]" >> \
       /mnt/data/noggin/log/security.log

SOP-005: Disk Space Emergency
Purpose: Free disk space when >90% full
Frequency: As needed (automated alert)
Procedure:

Assess situation

bash   df -h /mnt/data/noggin/
   du -sh /mnt/data/noggin/*

Stop service to prevent further writes

bash   ./manage_service.sh stop

Quick wins - Remove temporary files

bash   # Remove .tmp files
   find /mnt/data/noggin/ -name "*.tmp" -delete
   
   # Remove old compressed logs
   find /mnt/data/noggin/log/ -name "*.gz" -mtime +30 -delete
   
   # Check space freed
   df -h /mnt/data/noggin/

If still critical (>85%), archive old data

bash   # Archive data >1 year old
   CUTOFF_DATE=$(date -d '1 year ago' +%Y-%m-%d)
   
   # Create archive
   tar czf emergency_archive_$(date +%Y%m%d).tar.gz \
       $(find /mnt/data/noggin/output/ -type d -mtime +365)
   
   # Move to backup storage
   rsync -avz emergency_archive_*.tar.gz backup-server:/archives/
   
   # Verify remote copy
   ssh backup-server "ls -lh /archives/emergency_archive_*.tar.gz"
   
   # Remove local archived data
   find /mnt/data/noggin/output/ -type d -mtime +365 -exec rm -rf {} +

Database cleanup

sql   psql -U noggin_admin -d noggin_db << 'SQL'
   DELETE FROM processing_errors WHERE created_at < CURRENT_DATE - INTERVAL '3 months';
   VACUUM FULL processing_errors;
   SQL

Verify space freed

bash   df -h /mnt/data/noggin/
   # Should be <75%

Restart service

bash   ./manage_service.sh start

Set up monitoring to prevent recurrence

bash   # Add to cron if not already present
   crontab -e
   # Add:
   # 0 * * * * df -h /mnt/data/noggin/ | awk '$5 > "85%" {print}' | mail -s "Disk Space Alert" admin@example.com

Document incident

bash   cat >> /mnt/data/noggin/log/incidents.log << EOF
   $(date): Disk space emergency resolved
   - Initial: XX% full
   - Actions: Archived old data, cleaned temp files
   - Final: XX% full
   EOF

Escalation Matrix
IssueFirst ResponseEscalate ToEscalate AfterService downRestart serviceSenior Admin30 minutesDatabase unreachableCheck PostgreSQLDBA15 minutesAPI failuresCheck tokenNoggin Support1 hourDisk fullClean temp filesIT Infrastructure30 minutesPerformance degradationCheck resourcesSenior Admin2 hoursData corruptionStop service immediatelyDBA + ManagerImmediatelySecurity breachIsolate systemSecurity TeamImmediately

Contact Information
Internal Contacts
RoleNameEmailPhoneAvailabilityPrimary Operator[Name]operator@company.comxxx-xxxxBusiness hoursSenior Admin[Name]admin@company.comxxx-xxxx24/7 on-callDatabase Administrator[Name]dba@company.comxxx-xxxxBusiness hoursIT Manager[Name]manager@company.comxxx-xxxxBusiness hours
External Contacts
VendorContactEmailPhoneSupport HoursNoggin SupportSupport Teamsupport@elasticnoggin.com+61-x-xxxx-xxxxBusiness hours AESTHosting Provider[Provider]support@provider.comxxx-xxxx24/7

Appendix: Quick Reference Commands
Service Management
bash./manage_service.sh start          # Start service
./manage_service.sh stop           # Stop service
./manage_service.sh restart        # Restart service
./manage_service.sh status         # Check status
./manage_service.sh logs           # View recent logs
./manage_service.sh follow         # Follow logs in real-time
Monitoring
bashpython service_dashboard.py        # Status dashboard
htop                               # System resources
df -h /mnt/data/noggin/           # Disk usage
./manage_service.sh logs | grep -i error  # Find errors
Database Queries
sql-- Check queue
SELECT processing_status, COUNT(*) FROM noggin_data GROUP BY processing_status;

-- Today's activity
SELECT COUNT(*) FROM noggin_data WHERE updated_at >= CURRENT_DATE;

-- Recent errors
SELECT * FROM processing_errors WHERE created_at >= CURRENT_DATE ORDER BY created_at DESC LIMIT 20;

-- Unknown hashes
SELECT entity_type, COUNT(*) FROM unknown_hashes WHERE resolved_at IS NULL GROUP BY entity_type;
Hash Management
bashpython manage_hashes.py stats                              # View statistics
python manage_hashes.py import vehicle vehicles.csv        # Import hashes
python manage_hashes.py export-unknown vehicle out.csv     # Export unknown
python manage_hashes.py list vehicle                       # List all

End of Operations Manual

This completes the comprehensive Operations Manual. Would you like me to create any additional documentation files, such as:
- Troubleshooting flowcharts
- Configuration reference guide
- Database schema documentation
- Or anything else specific to your needs?