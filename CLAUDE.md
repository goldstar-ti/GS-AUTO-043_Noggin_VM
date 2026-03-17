# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Noggin Object Binary Backup Ingestion Engine (NOBBIE)** — a Python-based system for extracting, processing, and storing inspection data from the Noggin API into PostgreSQL. Supports six inspection object types: LCD, LCS, CCC, FPI, SO, TA.

## Common Commands

### Running the Processor
```bash
# Process by object type (reads from pending input folder by default)
python nobbie_process.py LCD
python nobbie_process.py CCC --csv tips.csv    # specific CSV
python nobbie_process.py FPI --database        # from DB queue
python nobbie_process.py TA --tip <TIP_ID>     # single record

# Continuous daemon
./nobbie-daemon.sh start|stop|status|logs
```

### Data Import
```bash
python nobbie_import.py                    # interactive menu
python nobbie_import.py --from-dir         # local CSV files
python nobbie_import.py --from-sftp        # download + import via SFTP
```

### Web Interface
```bash
./nobbie-web.sh start|stop|status|logs
# Access: http://localhost:5000  (auth: tifunction / hseq)
```

### Utilities
```bash
python nobbie_hashes.py import vehicle vehicles.csv
python nobbie_hashes.py export-unknown vehicle unknown.csv
python nobbie_stats.py
```

### Tests
```bash
python test/test_circuit_breaker.py
python test/test_database.py
python test/test_hash_manager.py
python test/validate_nobbie_data.py
```

### Install Dependencies
```bash
pip install -r docs/requirements.txt
```

## Architecture

### Entry Points
| Script | Purpose |
|---|---|
| `nobbie_process.py` | Main CLI — orchestrates processing for any object type |
| `nobbie_daemon.py` | Daemon — runs processing + import cycles in a loop |
| `nobbie_import.py` | Import TIP records from local CSV or remote SFTP |
| `web/app.py` | Flask dashboard (records, attachments, hash management) |
| `nobbie_hashes.py` | CLI for managing entity hash lookups |

### Processing Pipeline
`nobbie_process.py` → `processors/object_processor.py` (orchestrator) which coordinates:
- **`processors/base_processor.py`** — `APIClient` (HTTP + retry/backoff), `AttachmentDownloader` (download + MD5 validate), `FolderManager`, `GracefulShutdownHandler`
- **`processors/field_processor.py`** — config-driven field extraction + type conversion + hash resolution
- **`processors/report_generator.py`** — Jinja2-style template rendering from config
- **`processors/attachment_extractor.py`** — multi-pattern attachment detection (differs per object type)

### Configuration System
All behaviour is config-driven via INI files in `config/`:
- `base.ini` — database, API credentials, paths, circuit breaker, retry, SFTP, continuous cycle settings
- One config per object type (e.g. `CCC.ini`) — defines API endpoint, field mappings (API → DB column), folder/file naming patterns, report templates, attachment extraction patterns

`common/config.py` (`ConfigLoader`) merges base + object-type config. **Case-sensitivity is preserved** — critical because API field names are camelCase.

### Object Types (`common/object_types.py`)
Central registry mapping abbreviation → full name, ID field name, and config filename. Always consult this when adding a new object type.

### Database Layer (`common/database.py`)
Thread-safe connection pool via psycopg2. Schema: `noggin_schema` in database `noggin_db`.

Key tables:
- **`noggin_data`** — all inspection records (89 cols); PK is `tip`; tracks `processing_status`, retry counts, hashes, raw JSON payloads
- **`attachments`** — file download tracking with MD5 validation and timing
- **`entity_hashes`** — hash → name resolution (vehicle, trailer, department, team)
- **`unknown_hashes`** — unresolved hashes for manual lookup
- **`processing_errors`** — error audit log

### API Resilience (`common/rate_limiter.py`)
`CircuitBreaker` with CLOSED/OPEN/HALF_OPEN states. Configured via `[circuit_breaker]` in `base.ini`. Wraps all outbound API calls.

### Hash Resolution (`common/hash_manager.py`)
In-memory cached lookups backed by the `entity_hashes` table. Unresolved hashes are recorded in `unknown_hashes` as `"UNKNOWN"` placeholders until imported.

### Import Pipeline (`nobbie_import.py` + `common/csv_importer.py`)
CSV files land in `input_folder_path` → validated → upserted into `noggin_data` → moved to `processed/` or `error/`. Object type is auto-detected from CSV headers.

### Continuous Processor Cycle (`nobbie_daemon.py`)
Runs a configurable loop: every N cycles it triggers CSV import, hash resolution, and SFTP download, interspersed with API processing cycles. Cycle timing controlled by `[continuous]` in `base.ini`.

## Key Paths (from `base.ini`)
```
Logs:      /mnt/data/noggin/log
Output:    /mnt/data/noggin/out
ETL In:    /mnt/data/noggin/etl/in/pending
Processed: /mnt/data/noggin/etl/in/processed
Error:     /mnt/data/noggin/etl/in/error
```

## Reference Documentation
- `docs/noggin_schema.md` — full database schema
- `docs/swagger.json` — Noggin API specification
- `.scrap/README.md` — legacy comprehensive system docs
- `.scrap/OPERATIONS.md` — daily/weekly/monthly operations guide
