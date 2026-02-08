"""
SCRIPT: util_import.py
DATE:   2026-02-08

DESCRIPTION:
    Unified data ingestion utility.

    Consolidates the functionality of previous CSV and SFTP import tools
    into a single entry point. It handles the ingestion of TIP
    records via two primary methods:

    1. Local Directory Import (--from-dir):
       Scans a local directory for CSV files, validates headers, and upserts data
       into the PostgreSQL database. Supports an --update mode to fill missing
       fields in existing records without creating duplicates.

    2. SFTP Download & Import (--from-sftp):
       Connects to a remote SFTP server, downloads available CSV files, processes
       them immediately, and archives them locally. Successfully processed files
       are deleted from the remote server to maintain hygiene.

USAGE:
    1. Interactive Menu (Default):
       $ python util_import.py

    2. CLI - Local Directory Mode:
       $ python util_import.py --from-dir

    3. CLI - Local Directory Update Mode (Fill missing fields only):
       $ python util_import.py --from-dir --update

    4. CLI - SFTP Mode:
       $ python util_import.py --from-sftp

DEPENDENCIES:
    - paramiko (for SFTP connections)
    - common.ConfigLoader
    - common.LoggerManager
    - common.DatabaseConnectionManager
    - common.CSVImporter
"""

from __future__ import annotations
import argparse
import csv
import logging
import shutil
import sys
import time
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set

import paramiko

from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, CSVImporter

try:
    from common.object_types import (
        detect_object_type_from_headers,
        ObjectTypeConfig,
        find_column_index as shared_find_column_index
    )
    USE_SHARED_OBJECT_TYPES = True
except ImportError:
    USE_SHARED_OBJECT_TYPES = False

config: ConfigLoader = ConfigLoader('config/base_config.ini')

logger_manager: LoggerManager = LoggerManager(config, script_name='import_tips_combined')
logger_manager.configure_application_logger()
logger: logging.Logger = logging.getLogger(__name__)

DEFAULT_DIR_PATH = config.get('paths', 'input_folder_path', fallback="/mnt/data/noggin/etl/in/pending")
DEFAULT_SFTP_HOST = config.get('sftp', 'host', fallback="ssh.noggin-sftp.goldstartransport.com.au")
DEFAULT_SFTP_USER = config.get('sftp', 'username', fallback="u824-zdigcggtoza6")
DEFAULT_SFTP_PORT = config.get('sftp', 'port', fallback="18765")

class SFTPDownloaderError(Exception):
    pass

class SFTPConnectionError(SFTPDownloaderError):
    pass

class ObjectTypeDetectionError(SFTPDownloaderError):
    pass

OBJECT_TYPE_SIGNATURES: Dict[str, Dict[str, str]] = {
    'couplingId': {'abbreviation': 'CCC', 'full_name': 'Coupling Compliance Check', 'id_prefix': 'C - '},
    'forkliftPrestartInspectionId': {'abbreviation': 'FPI', 'full_name': 'Forklift Prestart Inspection', 'id_prefix': 'FL - Inspection - '},
    'lcsInspectionId': {'abbreviation': 'LCS', 'full_name': 'Load Compliance Check Supervisor/Manager', 'id_prefix': 'LCS - '},
    'lcdInspectionId': {'abbreviation': 'LCC', 'full_name': 'Load Compliance Check Driver/Loader', 'id_prefix': 'LCD - '},
    'siteObservationId': {'abbreviation': 'SO', 'full_name': 'Site Observations', 'id_prefix': 'SO - '},
    'trailerAuditId': {'abbreviation': 'TA', 'full_name': 'Trailer Audits', 'id_prefix': 'TA - '}
}

class SFTPLoggerManager:
    def __init__(self, config: ConfigParser, log_path: Path) -> None:
        self.config = config
        self.log_path = log_path
        self.log_path.mkdir(parents=True, exist_ok=True)
        self._error_logger: Optional[logging.Logger] = None
        self._warning_logger: Optional[logging.Logger] = None

    def _build_log_filename(self, pattern: str) -> str:
        now = datetime.now()
        return pattern.format(date=now.strftime('%Y%m%d'))

    def configure_sftp_loggers(self) -> None:
        formatter = logging.Formatter(fmt='%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        error_pattern = self.config.get('logging', 'error_log_pattern', fallback='sftp_downloader_errors_{date}.log')
        error_file = self.log_path / self._build_log_filename(error_pattern)
        self._error_logger = logging.getLogger('sftp_errors')
        self._error_logger.setLevel(logging.ERROR)
        self._error_logger.handlers.clear()
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setFormatter(formatter)
        self._error_logger.addHandler(error_handler)

        warning_pattern = self.config.get('logging', 'warning_log_pattern', fallback='sftp_downloader_warnings_{date}.log')
        warning_file = self.log_path / self._build_log_filename(warning_pattern)
        self._warning_logger = logging.getLogger('sftp_warnings')
        self._warning_logger.setLevel(logging.WARNING)
        self._warning_logger.handlers.clear()
        warning_handler = logging.FileHandler(warning_file, encoding='utf-8')
        warning_handler.setFormatter(formatter)
        self._warning_logger.addHandler(warning_handler)

    @property
    def error_logger(self) -> logging.Logger:
        if self._error_logger is None: raise RuntimeError("Loggers not configured.")
        return self._error_logger

    @property
    def warning_logger(self) -> logging.Logger:
        if self._warning_logger is None: raise RuntimeError("Loggers not configured.")
        return self._warning_logger

def prompt_truncation(db_manager: DatabaseConnectionManager) -> bool:
    print("\n" + "="*100)
    print(" DATABASE CLEANUP OPTIONS")
    print("="*100)
    print("Tables to be truncated:")
    print(" - noggin_schema.noggin_data")
    print(" - noggin_schema.attachments")
    print(" - noggin_schema.processing_errors")
    print(" - noggin_schema.session_log")
    print(" - noggin_schema.unknown_hashes")
    print("-" * 100)

    user_response = input(">>> Do you want to TRUNCATE these tables before importing? (y/n): ").strip().lower()

    if user_response == 'y':
        logger.warning("User requested table truncation...")
        try:
            tables = ['noggin_data', 'attachments', 'processing_errors', 'session_log', 'unknown_hashes']
            fq_tables = [f"noggin_schema.{t}" for t in tables]
            query = f"TRUNCATE TABLE {', '.join(fq_tables)} CASCADE;"

            db_manager.execute_update(query)
            logger.info("Truncation complete.")
            print("[OK] All specified tables have been truncated.")
        except Exception as e:
            logger.error(f"Truncation failed: {e}")
            print(f"[FAILED] Could not truncate tables. Error: {e}")
            return False
    else:
        print("... Skipping truncation. Appending to existing data.")

    print("="*100 + "\n")
    return True

def preview_csv_files(csv_importer: CSVImporter) -> None:
    csv_files = sorted(list(csv_importer.input_folder.glob('*.csv')))

    if csv_files:
        file_details = []
        for f in csv_files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            header_preview = "<Unable to read>"
            bom_warning = ""
            try:
                with open(f, 'r', encoding='utf-8') as f_obj:
                    raw_line = f_obj.readline()
                    if raw_line.startswith('\ufeff'):
                        bom_warning = "    [!] WARNING: BOM (Byte Order Mark) Detected\n"
                        header_preview = raw_line.lstrip('\ufeff').strip()
                    else:
                        header_preview = raw_line.strip()
                    if not header_preview:
                        header_preview = "<Empty File>"
            except Exception as e:
                header_preview = f"<Error: {e}>"

            file_details.append(
                f"  - File:     {f.name}\n"
                f"    Modified: {mtime}\n"
                f"{bom_warning}"
                f"    Header:   {header_preview}"
            )

        files_formatted = "\n\n".join(file_details)
        logger.info(f"Found {len(csv_files)} CSV files to process:\n{files_formatted}")
    else:
        logger.info(f"No CSV files found in: {csv_importer.input_folder}")
    print("\n")

def load_sftp_config(config_path: str = 'config/sftp_config.ini') -> ConfigParser:
    config = ConfigParser()
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"SFTP config not found: {config_path}")
    config.read(config_file)
    return config

def connect_sftp(config: ConfigParser) -> Tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    hostname = config.get('sftp', 'hostname')
    port = config.getint('sftp', 'port')
    username = config.get('sftp', 'username')
    key_path = config.get('sftp', 'private_key_path')
    timeout = config.getint('sftp', 'connection_timeout', fallback=30)

    logger.info(f"Connecting to SFTP: {hostname}:{port} as {username}")

    if not Path(key_path).exists():
        raise SFTPConnectionError(f"Private key not found: {key_path}")

    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        private_key = paramiko.RSAKey.from_private_key_file(key_path)
        ssh_client.connect(hostname=hostname, port=port, username=username, pkey=private_key, timeout=timeout, allow_agent=False, look_for_keys=False)
        sftp_client = ssh_client.open_sftp()
        return ssh_client, sftp_client
    except Exception as e:
        raise SFTPConnectionError(f"Connection failed: {e}")

def detect_object_type(csv_path: Path) -> Tuple[str, Dict[str, str]]:
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
        headers = [h.strip() for h in headers]

        if USE_SHARED_OBJECT_TYPES:
            config = detect_object_type_from_headers(headers)
            if config:
                metadata = {'abbreviation': config.abbreviation, 'full_name': config.full_name, 'id_prefix': config.id_prefix}
                return config.api_id_field, metadata
        else:
            for api_id_field, metadata in OBJECT_TYPE_SIGNATURES.items():
                if api_id_field in headers:
                    return api_id_field, metadata
        raise ObjectTypeDetectionError(f"No known ID column found in headers: {headers[:10]}...")
    except Exception as e:
        raise ObjectTypeDetectionError(f"Failed to read CSV headers or detect type: {e}")

def find_column_index(headers: List[str], column_name: str) -> int:
    clean_headers = [h.strip().lower() for h in headers]
    target = column_name.strip().lower()
    try:
        return clean_headers.index(target)
    except ValueError:
        return -1

def parse_date(date_str: str) -> Optional[str]:
    formats = ['%d-%b-%y', '%d-%b-%Y', '%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%d-%m-%Y', '%d-%m-%y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError: continue
    return None

def extract_tips_from_csv(csv_path: Path, api_id_field: str, object_type_meta: Dict[str, str]) -> List[Dict[str, Any]]:
    tips = []
    with open(csv_path, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = [h.strip() for h in next(reader)]
        tip_index = 0
        id_index = find_column_index(headers, api_id_field)
        date_index = find_column_index(headers, 'date')

        for row_num, row in enumerate(reader, start=2):
            if not row or not row[tip_index].strip(): continue
            tip_value = row[tip_index].strip()
            inspection_id = row[id_index].strip() or None if id_index is not None and len(row) > id_index else None
            inspection_date = parse_date(row[date_index].strip()) if date_index is not None and len(row) > date_index and row[date_index].strip() else None

            tips.append({
                'tip': tip_value,
                'object_type': object_type_meta['full_name'],
                'abbreviation': object_type_meta['abbreviation'],
                'inspection_id': inspection_id,
                'inspection_date': inspection_date,
                'row_number': row_num
            })
    return tips

def insert_tips_to_database_sftp_mode(db_manager: DatabaseConnectionManager, tips_data: List[Dict[str, Any]], source_file: str, warning_logger: logging.Logger) -> Dict[str, int]:
    if not tips_data: return {'inserted': 0, 'duplicates': 0, 'errors': 0}

    tip_values = [t['tip'] for t in tips_data]
    placeholders = ', '.join(['%s'] * len(tip_values))
    query = f"SELECT tip FROM noggin_data WHERE tip IN ({placeholders})"
    results = db_manager.execute_query_dict(query, tuple(tip_values))
    existing_tips = {row['tip'] for row in results}

    inserted = 0
    duplicates = 0
    errors = 0

    insert_query_full = "INSERT INTO noggin_data (tip, object_type, processing_status, expected_inspection_id, expected_inspection_date, csv_imported_at, source_filename) VALUES (%s, %s, 'pending', %s, %s, CURRENT_TIMESTAMP, %s)"
    insert_query_basic = "INSERT INTO noggin_data (tip, object_type, processing_status, csv_imported_at) VALUES (%s, %s, 'pending', CURRENT_TIMESTAMP)"

    use_full_insert = True

    for tip_data in tips_data:
        tip_value = tip_data['tip']
        if tip_value in existing_tips:
            duplicates += 1
            warning_logger.warning(f"DUPLICATE TIP skipped | tip={tip_value} | object_type={tip_data['abbreviation']}")
            continue

        try:
            if use_full_insert:
                db_manager.execute_update(insert_query_full, (tip_value, tip_data['object_type'], tip_data['inspection_id'], tip_data['inspection_date'], source_file))
            else:
                db_manager.execute_update(insert_query_basic, (tip_value, tip_data['object_type']))
            inserted += 1
        except Exception as e:
            if use_full_insert:
                use_full_insert = False
                try:
                    db_manager.execute_update(insert_query_basic, (tip_value, tip_data['object_type']))
                    inserted += 1
                    continue
                except Exception: pass
            errors += 1
            logger.error(f"Failed to insert TIP {tip_value}: {e}")

    return {'inserted': inserted, 'duplicates': duplicates, 'errors': errors}

def run_local_csv_process(db_manager: DatabaseConnectionManager, update_mode: bool) -> None:
    logger.info("Starting Local CSV Import Mode...")
    if update_mode:
        logger.info("UPDATE MODE ACTIVE: Will fill missing fields and skip completed records.")
    else:
        if not prompt_truncation(db_manager):
            logger.info("Truncation declined or failed. Aborting.")
            return

    csv_importer: CSVImporter = CSVImporter(config, db_manager)
    logger.info(f"Input folder path: {csv_importer.input_folder}")
    preview_csv_files(csv_importer)

    if update_mode:
        logger.info("Scanning for CSV files (update mode)...")
        summary = csv_importer.scan_and_update()
        print(f"\n[OK] Update Summary: Processed={summary['files_processed']}, Updated={summary['total_updated']}, Inserted={summary['total_inserted']}, Errors={summary['total_errors']}")
    else:
        logger.info("Scanning for CSV files (standard mode)...")
        summary = csv_importer.scan_and_import()
        print(f"\n[OK] Import Summary: Processed={summary['files_processed']}, Imported={summary['total_imported']}, Duplicates={summary['total_duplicates']}, Errors={summary['total_errors']}")


def run_sftp_process(db_manager: DatabaseConnectionManager) -> None:
    logger.info("Starting SFTP Download & Import Mode...")

    try:
        sftp_config = load_sftp_config('config/sftp_config.ini')

        sftp_logger = SFTPLoggerManager(sftp_config, Path(config.get('paths', 'base_log_path')))
        sftp_logger.configure_sftp_loggers()

        incoming_dir = Path(sftp_config.get('paths', 'incoming_directory'))
        incoming_dir.mkdir(parents=True, exist_ok=True)
        processed_dir = Path(sftp_config.get('paths', 'processed_directory'))
        processed_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir = Path(sftp_config.get('paths', 'quarantine_directory'))
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        ssh_client, sftp_client = connect_sftp(sftp_config)
        remote_dir = sftp_config.get('sftp', 'remote_directory')

        sftp_client.chdir(remote_dir)
        files = [(entry.filename, entry.st_mtime) for entry in sftp_client.listdir_attr() if entry.filename.endswith('.csv')]
        files.sort(key=lambda x: x[1])

        if not files:
            logger.info("No CSV files found on SFTP server.")
            print("\n[INFO] No files found on SFTP.")
            return

        logger.info(f"Found {len(files)} files on SFTP.")
        print(f"\n[INFO] Found {len(files)} files. Processing...")

        files_to_delete = []

        for filename, _ in files:
            logger.info(f"Processing remote file: {filename}")
            local_file = incoming_dir / filename

            try:
                sftp_client.get(filename, str(local_file))

                try:
                    api_id_field, object_meta = detect_object_type(local_file)
                except ObjectTypeDetectionError as e:
                    q_path = quarantine_dir / f"QUARANTINE_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                    shutil.move(str(local_file), str(q_path))
                    sftp_logger.error_logger.error(f"QUARANTINED {filename}: {e}")
                    continue

                tips_data = extract_tips_from_csv(local_file, api_id_field, object_meta)

                if tips_data:
                    insert_tips_to_database_sftp_mode(db_manager, tips_data, filename, sftp_logger.warning_logger)

                timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
                archive_name = f"{object_meta['abbreviation']}_{timestamp}_{filename}"
                shutil.move(str(local_file), str(processed_dir / archive_name))

                files_to_delete.append(filename)

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}", exc_info=True)

        if files_to_delete:
            logger.info(f"Deleting {len(files_to_delete)} processed files from SFTP...")
            for f in files_to_delete:
                try:
                    sftp_client.remove(f)
                except Exception as e:
                    logger.error(f"Failed to delete {f}: {e}")
            print(f"[OK] Processed and deleted {len(files_to_delete)} files.")

    except Exception as e:
        logger.error(f"SFTP Process Failed: {e}", exc_info=True)
        print(f"[ERROR] SFTP Process Failed: {e}")
    finally:
        if 'sftp_client' in locals() and sftp_client: sftp_client.close()
        if 'ssh_client' in locals() and ssh_client: ssh_client.close()

def show_menu() -> str:
    print("\n" + "="*80)
    print(" NOGGIN IMPORT UTILITY SELECTION")
    print("="*80)
    print(f"1. directory ({DEFAULT_DIR_PATH})")
    print(f"2. sftp      ({DEFAULT_SFTP_USER}@{DEFAULT_SFTP_HOST}:{DEFAULT_SFTP_PORT})")
    print("-" * 80)

    while True:
        choice = input(">>> Select option (1/2): ").strip()
        if choice in ['1', '2']:
            return choice
        print("Invalid selection. Please enter 1 or 2.")

def main() -> None:
    parser = argparse.ArgumentParser(description='Import or update TIP records from Local Directory or SFTP')
    parser.add_argument('--from-dir', action='store_true', help='Import from local pending directory')
    parser.add_argument('--from-sftp', action='store_true', help='Download and import from SFTP')
    parser.add_argument('--update', action='store_true', help='Update mode (Local Directory only): fill missing fields')

    if len(sys.argv) == 1:
        choice = show_menu()
        if choice == '1':
            mode = 'dir'
        else:
            mode = 'sftp'
        update_mode = False
    else:
        args = parser.parse_args()
        if args.from_dir and args.from_sftp:
            print("[ERROR] Cannot specify both --from-dir and --from-sftp")
            sys.exit(1)

        if args.from_sftp:
            mode = 'sftp'
        elif args.from_dir:
            mode = 'dir'
        else:
            mode = 'dir'

        update_mode = args.update

    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)

    try:
        if mode == 'sftp':
            if update_mode:
                print("[WARNING] --update flag is ignored in SFTP mode. Performing standard import.")
            run_sftp_process(db_manager)
        else:
            run_local_csv_process(db_manager, update_mode)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"[ERROR] {e}")
    finally:
        db_manager.close_all()

if __name__ == '__main__':
    main()