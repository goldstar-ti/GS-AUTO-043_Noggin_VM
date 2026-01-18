# Noggin Processor - Quick Start Guide

Get up and running in 10 minutes.

## Prerequisites

- Ubuntu 20.04+
- PostgreSQL installed
- Python 3.9+ with pip
- API bearer token

---

## Installation Steps

### 1. Database Setup (2 minutes)
```bash
sudo -i -u postgres
psql << 'EOF'
CREATE DATABASE noggin_db;
CREATE USER noggin_admin WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE noggin_db TO noggin_admin;
\c noggin_db
CREATE SCHEMA noggin_schema;
GRANT ALL ON SCHEMA noggin_schema TO noggin_admin;
EOF
exit
```

### 2. Project Setup (3 minutes)
```bash
cd ~/scripts
python3 -m venv .venv
source .venv/bin/activate
pip install psycopg2-binary requests configparser

mkdir -p /mnt/data/noggin/{output,input,log}
```

### 3. Configure (2 minutes)

Edit `config/base_config.ini`:
```ini
[database]
password = your_password

[api]
bearer_token = your_token_here
```

### 4. Initialize Database (1 minute)
```bash
python setup_database.py
```

### 5. Import Entity Hashes (2 minutes)
```bash
python manage_hashes.py import vehicle config/hashes/vehicles.csv
python manage_hashes.py import trailer config/hashes/trailers.csv
python manage_hashes.py import department config/hashes/departments.csv
python manage_hashes.py import team config/hashes/teams.csv
```

---

## First Run

### Process a Single TIP
```bash
# Create test file
echo "tip" > tip.csv
echo "your_test_tip_here" >> tip.csv

# Run processor
python noggin_processor.py
```

### Start Continuous Processing
```bash
# Start as background service
./manage_service.sh start

# Check status
python service_dashboard.py
```

---

## Verify Installation
```bash
# 1. Check database
psql -U noggin_admin -d noggin_db -c "SELECT COUNT(*) FROM noggin_data;"

# 2. Check service
./manage_service.sh status

# 3. Check logs
./manage_service.sh logs
```

---

## Next Steps

1. Review [README.md](README.md) for detailed documentation
2. Configure additional settings in `config/base_config.ini`
3. Set up CSV import workflow
4. Configure systemd service for auto-start

---

## Common First-Run Issues

**Database connection fails:**
```bash
# Check PostgreSQL running
sudo systemctl status postgresql
```

**401 Authentication error:**
- Update bearer_token in config/base_config.ini
- Token must be on single line, no spaces

**Import path not found:**
```bash
# Check Python can find common module
python -c "from common import ConfigLoader; print('OK')"
```