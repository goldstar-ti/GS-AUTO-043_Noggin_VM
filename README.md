# Noggin Data Extraction System

Comprehensive PostgreSQL-based system for extracting, processing, and managing inspection data from the Noggin API.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Database Schema](#database-schema)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Overview

The Noggin Data Extraction System automates the retrieval and storage of Load Compliance Check inspection data from the Noggin API. It provides robust error handling, retry logic, circuit breaker pattern for API resilience, and continuous processing capabilities.

### Key Components

- **PostgreSQL Database**: Centralised data storage with full audit trail
- **Hash Manager**: Resolves entity hashes to human-readable names
- **Circuit Breaker**: Protects against API overload
- **CSV Importer**: Batch imports TIPs from CSV files
- **Continuous Processor**: Daemon-style background processing
- **Systemd Service**: Automatic startup and management

---

## System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Noggin API (External)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Circuit Breaker Layer                     │
│          (Adaptive Rate Limiting & Failure Detection)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  noggin_processor.py                        │
│              (Main Processing Script)                       │
│                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  Hash Manager  │  │  API Requests  │  │  Attachments │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│                PostgreSQL Database                         │
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ noggin_data  │  │ attachments  │  │ entity_hashes    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                            │
│  ┌──────────────────┐  ┌─────────────────────────────────┐ │
│  │ unknown_hashes   │  │ processing_errors               │ │
│  └──────────────────┘  └─────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│               File System (Attachments)                    │
│                                                            │
│  /mnt/data/noggin/output/YYYY/MM/YYYY-MM-DD LCD-XXXXXX/    │
│      ├── LCD-XXXXXX_inspection_data.txt                    │
│      ├── LCD-XXXXXX_YYYYMMDD_photo_001.jpg                 │
│      └── LCD-XXXXXX_YYYYMMDD_photo_002.jpg                 │
└────────────────────────────────────────────────────────────┘
```

---

## Features

### Core Functionality
- API data extraction with exponential backoff retry
- Attachment download with validation and MD5 hashing
- Hierarchical folder structure by year/month/date
- Formatted text file generation for each inspection
- Hash resolution for vehicles, trailers, departments, teams

### Data Management
- PostgreSQL database with full schema
- CSV batch import with duplicate detection
- Unknown hash tracking and resolution workflow
- Comprehensive error logging and audit trail

### Resilience & Recovery
- Circuit breaker pattern for API protection
- Automatic retry with exponential backoff
- Incomplete download resumption
- Graceful shutdown (Ctrl+C handling)
- Processing state persistence

### Operations
- Continuous processing mode (daemon)
- Systemd service integration
- Real-time progress tracking
- Service management scripts
- Status dashboard

---

## Prerequisites

### System Requirements
- Ubuntu 20.04 LTS or later
- PostgreSQL 12 or later
- Python 3.9 or later
- 1000GB+ free disk space for attachments

### Network Requirements
- Access to Noggin API endpoints
- Stable internet connection
- API authentication token

---

## Installation

### 1. Install System Dependencies
```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib python3-pip python3-venv git
```

### 2. Set Up PostgreSQL
```bash
# Switch to postgres user
sudo -i -u postgres

# Create database and user
psql << EOF
CREATE DATABASE noggin_db;
CREATE USER noggin_admin WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE noggin_db TO noggin_admin;
\c noggin_db
CREATE SCHEMA noggin_schema;
GRANT ALL ON SCHEMA noggin_schema TO noggin_admin;
ALTER DATABASE noggin_db SET search_path TO noggin_schema,public;
EOF

exit
```

### 3. Clone/Copy Project Files
```bash
mkdir -p ~/scripts
cd ~/scripts
# Copy all project files here
```

### 4. Create Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Create Directory Structure
```bash
mkdir -p /mnt/data/noggin/{output,input,input/processed,input/error,log}
```

### 6. Initialize Database Schema
```bash
python setup_database.py
```

### 7. Configure Application

Edit configuration files:
- `config/base_config.ini` - Database, API, paths
- `config/load_compliance_check_config.ini` - Object-specific settings

### 8. Import Entity Hashes
```bash
# Place CSV files in config/hashes/
python manage_hashes.py import vehicle config/hashes/vehicles.csv
python manage_hashes.py import trailer config/hashes/trailers.csv
python manage_hashes.py import department config/hashes/departments.csv
python manage_hashes.py import team config/hashes/teams.csv
```

---

## Configuration

### Database Configuration (`config/base_config.ini`)
```ini
[database]
host = localhost
port = 5432
database = noggin_db
username = noggin_admin
password = your_secure_password
schema = noggin_schema
```

### API Configuration
```ini
[api]
base_url = https://services.apse2.elasticnoggin.com/rest/object/
media_service_url = https://services.apse2.elasticnoggin.com/media/
namespace = your_namespace_hash
bearer_token = your_bearer_token_here
timeout = 30
```

### Processing Configuration
```ini
[processing]
too_many_requests_sleep_time = 60
attachment_pause = 1
max_api_retries = 5
api_backoff_factor = 2
api_max_backoff = 60
```

### Circuit Breaker Configuration
```ini
[circuit_breaker]
failure_threshold_percent = 50
recovery_threshold_percent = 10
circuit_open_duration_seconds = 300
sample_size = 10
```

### Retry Configuration
```ini
[retry]
max_retry_attempts = 5
retry_backoff_multiplier = 2
tips_per_batch = 50
```

### Continuous Processing Configuration
```ini
[continuous]
cycle_sleep_seconds = 300
import_csv_every_n_cycles = 3
```

---

## Usage

### One-Time Processing (CSV File)
```bash
# Create tip.csv with TIPs to process
cat > tip.csv << EOF
tip
abc123def456ghi789
xyz987uvw654rst321
EOF

# Run processor
python noggin_processor.py
```

### Batch CSV Import
```bash
# Place CSV files in /mnt/data/noggin/input/
python -c "from common import *; \
    config = ConfigLoader('config/base_config.ini', 'config/load_compliance_check_config.ini'); \
    db = DatabaseConnectionManager(config); \
    importer = CSVImporter(config, db); \
    importer.scan_and_import_csv_files()"
```

### Continuous Processing (Background Service)
```bash
# Start service
./manage_service.sh start

# Check status
./manage_service.sh status

# View logs
./manage_service.sh logs

# Follow logs in real-time
./manage_service.sh follow

# Stop service
./manage_service.sh stop
```

### Hash Management
```bash
# Import hashes from CSV
python manage_hashes.py import vehicle vehicles.csv

# Export unknown hashes
python manage_hashes.py export-unknown vehicle unknown_vehicles.csv

# Resolve unknown hashes
# 1. Edit CSV with correct names
# 2. Re-import:
python manage_hashes.py import vehicle unknown_vehicles_resolved.csv

# List all hashes
python manage_hashes.py list vehicle
```

### Status Dashboard
```bash
python service_dashboard.py
```

---

## Database Schema

### Main Tables

#### `noggin_data`
Primary table storing inspection records.

**Key Columns:**
- `tip` (PK) - Unique TIP identifier
- `object_type` - Type of inspection
- `processing_status` - Current processing state
- `lcd_inspection_id` - Human-readable inspection ID
- `inspection_date` - Date of inspection
- `vehicle`, `trailer`, `department`, `team` - Resolved entity names
- `retry_count`, `next_retry_at` - Retry tracking
- `permanently_failed` - Flagged after max retries

#### `attachments`
Tracks downloaded attachment files.

**Key Columns:**
- `record_tip`, `attachment_tip` (Composite PK)
- `filename`, `file_path` - File location
- `attachment_status` - Download status
- `file_size_bytes`, `file_hash_md5` - Validation data
- `download_started_at`, `download_completed_at` - Timing

#### `entity_hashes`
Maps entity hashes to human-readable names.

**Key Columns:**
- `hash_value` (PK) - Hash from API
- `entity_type` - vehicle, trailer, department, team
- `entity_name` - Resolved name
- `source` - How it was obtained

#### `unknown_hashes`
Tracks unresolved hashes for manual resolution.

#### `processing_errors`
Comprehensive error logging for debugging.

### Processing Status Values

| Status | Description |
|--------|-------------|
| `pending` | Imported from CSV, not yet processed |
| `api_success` | API call succeeded, attachments pending |
| `complete` | All attachments downloaded successfully |
| `partial` | Some attachments failed |
| `failed` | All attachments failed |
| `interrupted` | Processing stopped mid-way (Ctrl+C) |
| `api_failed` | API request failed |

---

## Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -h localhost -U noggin_admin -d noggin_db

# Check credentials in config/base_config.ini
```

#### API Authentication Failures (401)
```
Error: Authentication failed for TIP...
```

**Solution:** Update bearer token in `config/base_config.ini`

#### Circuit Breaker Opening
```
WARNING: Circuit breaker OPEN (failure threshold exceeded)
```

**Solution:** Wait 5 minutes (default) for circuit to reset, or investigate API issues

#### Unknown Hashes
```bash
# Export unknown hashes
python manage_hashes.py export-unknown vehicle unknown_vehicles.csv

# Manually edit CSV with correct names
# Re-import resolved hashes
python manage_hashes.py import vehicle unknown_vehicles.csv
```

#### Service Won't Start
```bash
# Check service logs
./manage_service.sh logs

# Common causes:
# - Wrong paths in service file
# - Python virtual environment not activated
# - Database not accessible
```

---

## Maintenance

### Daily Tasks
```bash
# Check service status
python service_dashboard.py

# Review any errors
./manage_service.sh logs
```

### Weekly Tasks
```bash
# Export and resolve unknown hashes
python manage_hashes.py export-unknown vehicle unknown_vehicles.csv
python manage_hashes.py export-unknown trailer unknown_trailers.csv

# Review processing errors
psql -U noggin_admin -d noggin_db -c \
  "SELECT * FROM processing_errors WHERE created_at > CURRENT_DATE - INTERVAL '7 days';"
```

### Monthly Tasks
```bash
# Database backup
pg_dump -U noggin_admin noggin_db > backup_$(date +%Y%m%d).sql

# Disk space check
df -h /mnt/data/noggin/

# Review permanently failed TIPs
psql -U noggin_admin -d noggin_db -c \
  "SELECT tip, last_error_message FROM noggin_data WHERE permanently_failed = TRUE;"
```

### Log Rotation

Logs are stored in `/mnt/data/noggin/log/`. Consider setting up logrotate:
```bash
sudo nano /etc/logrotate.d/noggin
```

Add:
```
/mnt/data/noggin/log/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0640 noggin_admin noggin_admin
}
```

---

## File Structure
```
~/scripts/
├── noggin_processor.py              # Main processing script
├── noggin_continuous_processor.py   # Continuous daemon
├── setup_database.py                # Database schema setup
├── manage_hashes.py                 # Hash management CLI
├── service_dashboard.py             # Status dashboard
├── manage_service.sh                # Service management
├── test_systemd_service.sh          # Service testing
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
│
├── common/                          # Shared library modules
│   ├── __init__.py
│   ├── config.py                    # Configuration loader
│   ├── logger.py                    # Logging manager
│   ├── database.py                  # Database connection
│   ├── hash_manager.py              # Hash resolution
│   ├── csv_importer.py              # CSV import
│   └── rate_limiter.py              # Circuit breaker
│
├── config/                          # Configuration files
│   ├── base_config.ini              # Base configuration
│   ├── load_compliance_check_config.ini
│   └── hashes/                      # Entity hash CSVs
│       ├── vehicles.csv
│       ├── trailers.csv
│       ├── departments.csv
│       └── teams.csv
│
└── .venv/                           # Python virtual environment

/mnt/data/noggin/
├── output/                          # Downloaded data
│   └── YYYY/MM/YYYY-MM-DD LCD-XXXXX/
│       ├── LCD-XXXXX_inspection_data.txt
│       └── LCD-XXXXX_YYYYMMDD_photo_NNN.jpg
├── input/                           # CSV import folder
│   ├── processed/                   # Successfully imported
│   └── error/                       # Failed imports
└── log/                             # Application logs
```

---

## Support & Contact

For issues, questions, or enhancements, contact your system administrator.

---

## Version History

- **v1.0** - Initial release with PostgreSQL integration
  - Database-driven architecture
  - Circuit breaker pattern
  - Retry logic with exponential backoff
  - Continuous processing mode
  - Systemd service integration