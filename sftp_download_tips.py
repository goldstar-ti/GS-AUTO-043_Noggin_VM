"""
SFTP TIP Downloader for Noggin Data Extraction System

Downloads CSV files from SFTP server, identifies object types,
extracts TIPs, and inserts them into the database for processing.

Can be run standalone or called from noggin_continuous_processor.py
"""

from __future__ import annotations
import csv
import logging
import shutil
import sys
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import paramiko

from common import ConfigLoader, LoggerManager, DatabaseConnectionManager

# Try to import shared object types module, fall back to inline if not available
try:
    from common.object_types import (
        detect_object_type_from_headers,
        ObjectTypeConfig,
        find_column_index as shared_find_column_index
    )
    USE_SHARED_OBJECT_TYPES = True
except ImportError:
    USE_SHARED_OBJECT_TYPES = False

logger: logging.Logger = logging.getLogger(__name__)

# Fallback object type detection signatures (used if shared module not available)
OBJECT_TYPE_SIGNATURES: Dict[str, Dict[str, str]] = {
    'couplingId': {
        'abbreviation': 'CCC',
        'full_name': 'Coupling Compliance Check',
        'id_prefix': 'C - '
    },
    'forkliftPrestartInspectionId': {
        'abbreviation': 'FPI',
        'full_name': 'Forklift Prestart Inspection',
        'id_prefix': 'FL - Inspection - '
    },
    'lcsInspectionId': {
        'abbreviation': 'LCS',
        'full_name': 'Load Compliance Check Supervisor/Manager',
        'id_prefix': 'LCS - '
    },
    'lcdInspectionId': {
        'abbreviation': 'LCC',
        'full_name': 'Load Compliance Check Driver/Loader',
        'id_prefix': 'LCD - '
    },
    'siteObservationId': {
        'abbreviation': 'SO',
        'full_name': 'Site Observations',
        'id_prefix': 'SO - '
    },
    'trailerAuditId': {
        'abbreviation': 'TA',
        'full_name': 'Trailer Audits',
        'id_prefix': 'TA - '
    }
}


class SFTPDownloaderError(Exception):
    """Base exception for SFTP downloader errors"""
    pass


class SFTPConnectionError(SFTPDownloaderError):
    """SFTP connection failed"""
    pass


class ObjectTypeDetectionError(SFTPDownloaderError):
    """Could not identify object type from CSV"""
    pass


class SFTPLoggerManager:
    """Manages multiple log files for SFTP operations"""
    
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
        """Configure separate error and warning loggers"""
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        error_pattern = self.config.get('logging', 'error_log_pattern', 
                                        fallback='sftp_downloader_errors_{date}.log')
        error_filename = self._build_log_filename(error_pattern)
        error_file = self.log_path / error_filename
        
        self._error_logger = logging.getLogger('sftp_errors')
        self._error_logger.setLevel(logging.ERROR)
        self._error_logger.handlers.clear()
        
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self._error_logger.addHandler(error_handler)
        
        warning_pattern = self.config.get('logging', 'warning_log_pattern',
                                          fallback='sftp_downloader_warnings_{date}.log')
        warning_filename = self._build_log_filename(warning_pattern)
        warning_file = self.log_path / warning_filename
        
        self._warning_logger = logging.getLogger('sftp_warnings')
        self._warning_logger.setLevel(logging.WARNING)
        self._warning_logger.handlers.clear()
        
        warning_handler = logging.FileHandler(warning_file, encoding='utf-8')
        warning_handler.setLevel(logging.WARNING)
        warning_handler.setFormatter(formatter)
        self._warning_logger.addHandler(warning_handler)
        
        logger.info(f"Error log: {error_file}")
        logger.info(f"Warning log: {warning_file}")
    
    @property
    def error_logger(self) -> logging.Logger:
        if self._error_logger is None:
            raise RuntimeError("Loggers not configured. Call configure_sftp_loggers() first.")
        return self._error_logger
    
    @property
    def warning_logger(self) -> logging.Logger:
        if self._warning_logger is None:
            raise RuntimeError("Loggers not configured. Call configure_sftp_loggers() first.")
        return self._warning_logger


def load_sftp_config(config_path: str = 'config/sftp_config.ini') -> ConfigParser:
    """Load SFTP configuration from INI file"""
    config = ConfigParser()
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"SFTP config not found: {config_path}")
    
    config.read(config_file)
    return config


def create_directories(config: ConfigParser) -> Dict[str, Path]:
    """Create required directories and return paths"""
    paths = {
        'incoming': Path(config.get('paths', 'incoming_directory')),
        'processed': Path(config.get('paths', 'processed_directory')),
        'quarantine': Path(config.get('paths', 'quarantine_directory')),
        'monthly_archive': Path(config.get('paths', 'monthly_archive_directory')),
        'tip_audit': Path(config.get('paths', 'tip_audit_directory'))
    }
    
    for name, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ready: {name} -> {path}")
    
    return paths


def connect_sftp(config: ConfigParser) -> Tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    """Establish SFTP connection using private key authentication"""
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
        
        ssh_client.connect(
            hostname=hostname,
            port=port,
            username=username,
            pkey=private_key,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False
        )
        
        sftp_client = ssh_client.open_sftp()
        logger.info("SFTP connection established")
        
        return ssh_client, sftp_client
        
    except paramiko.AuthenticationException as e:
        raise SFTPConnectionError(f"Authentication failed: {e}")
    except paramiko.SSHException as e:
        raise SFTPConnectionError(f"SSH error: {e}")
    except Exception as e:
        raise SFTPConnectionError(f"Connection failed: {e}")


def list_csv_files(sftp: paramiko.SFTPClient, remote_dir: str) -> List[Tuple[str, int]]:
    """
    List CSV files on SFTP server sorted by modification time (oldest first)
    
    Returns list of tuples: (filename, mtime)
    """
    try:
        sftp.chdir(remote_dir)
        files = []
        
        for entry in sftp.listdir_attr():
            if entry.filename.endswith('.csv'):
                files.append((entry.filename, entry.st_mtime))
        
        # Sort by modification time (oldest first for FIFO processing)
        files.sort(key=lambda x: x[1])
        
        logger.info(f"Found {len(files)} CSV files on SFTP server")
        return files
        
    except Exception as e:
        raise SFTPDownloaderError(f"Failed to list remote directory: {e}")


def download_file(sftp: paramiko.SFTPClient, remote_filename: str, 
                  local_path: Path) -> Path:
    """Download single file from SFTP to local path"""
    local_file = local_path / remote_filename
    
    try:
        sftp.get(remote_filename, str(local_file))
        logger.debug(f"Downloaded: {remote_filename}")
        return local_file
        
    except Exception as e:
        raise SFTPDownloaderError(f"Failed to download {remote_filename}: {e}")


def detect_object_type(csv_path: Path) -> Tuple[str, Dict[str, str]]:
    """
    Detect object type by examining CSV headers
    
    Returns tuple of (id_column_name, object_type_metadata)
    Raises ObjectTypeDetectionError if type cannot be determined
    """
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
        
        headers = [h.strip() for h in headers]
        
        # Use shared module if available
        if USE_SHARED_OBJECT_TYPES:
            config = detect_object_type_from_headers(headers)
            if config:
                metadata = {
                    'abbreviation': config.abbreviation,
                    'full_name': config.full_name,
                    'id_prefix': config.id_prefix
                }
                logger.debug(f"Detected object type: {config.abbreviation} via column '{config.id_column}'")
                return config.id_column, metadata
        else:
            # Fallback to inline detection
            for id_column, metadata in OBJECT_TYPE_SIGNATURES.items():
                if id_column in headers:
                    logger.debug(f"Detected object type: {metadata['abbreviation']} via column '{id_column}'")
                    return id_column, metadata
        
        raise ObjectTypeDetectionError(
            f"No known ID column found in headers: {headers[:10]}..."
        )
        
    except ObjectTypeDetectionError:
        raise
    except Exception as e:
        raise ObjectTypeDetectionError(f"Failed to read CSV headers: {e}")


def find_column_index(headers: List[str], column_name: str) -> int:
    """
    Find column index by name (case-insensitive, handles whitespace)
    Returns -1 if not found
    """
    clean_headers = [h.strip().lower() for h in headers]
    target = column_name.strip().lower()
    
    try:
        return clean_headers.index(target)
    except ValueError:
        return -1


def extract_tips_from_csv(csv_path: Path, id_column: str, 
                          object_type_meta: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Extract TIP data from CSV file
    
    Returns list of dicts with keys: tip, object_type, inspection_id, inspection_date
    """
    tips = []
    
    with open(csv_path, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = [h.strip() for h in next(reader)]
        
        # First column is always nogginId (TIP), regardless of header name
        tip_index = 0
        
        id_index = find_column_index(headers, id_column)
        date_index = find_column_index(headers, 'date')
        
        if id_index == -1:
            logger.warning(f"ID column '{id_column}' not found in headers")
            id_index = None
        
        if date_index == -1:
            logger.warning("Date column not found in headers")
            date_index = None
        
        for row_num, row in enumerate(reader, start=2):
            if not row or not row[tip_index].strip():
                continue
            
            tip_value = row[tip_index].strip()
            
            inspection_id = None
            if id_index is not None and len(row) > id_index:
                inspection_id = row[id_index].strip() or None
            
            inspection_date = None
            if date_index is not None and len(row) > date_index:
                date_str = row[date_index].strip()
                if date_str:
                    inspection_date = parse_date(date_str)
            
            tips.append({
                'tip': tip_value,
                'object_type': object_type_meta['full_name'],
                'abbreviation': object_type_meta['abbreviation'],
                'inspection_id': inspection_id,
                'inspection_date': inspection_date,
                'row_number': row_num
            })
    
    logger.info(f"Extracted {len(tips)} TIPs from {csv_path.name}")
    return tips


def parse_date(date_str: str) -> Optional[str]:
    """
    Parse date string to ISO format (YYYY-MM-DD)
    Handles multiple formats commonly found in Noggin exports
    """
    formats = [
        '%d-%b-%y',      # 16-Jun-25
        '%d-%b-%Y',      # 16-Jun-2025
        '%d/%m/%Y',      # 16/06/2025
        '%d/%m/%y',      # 16/06/25
        '%Y-%m-%d',      # 2025-06-16
        '%d-%m-%Y',      # 16-06-2025
        '%d-%m-%y',      # 16-06-25
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    logger.debug(f"Could not parse date: {date_str}")
    return None


def check_existing_tips(db_manager: DatabaseConnectionManager, 
                        tips: List[str]) -> set:
    """Check which TIPs already exist in database"""
    if not tips:
        return set()
    
    placeholders = ', '.join(['%s'] * len(tips))
    query = f"SELECT tip FROM noggin_data WHERE tip IN ({placeholders})"
    
    results = db_manager.execute_query_dict(query, tuple(tips))
    return {row['tip'] for row in results}


def insert_tips_to_database(db_manager: DatabaseConnectionManager,
                            tips_data: List[Dict[str, Any]],
                            source_file: str,
                            warning_logger: logging.Logger) -> Dict[str, int]:
    """
    Insert new TIPs into database with pending status
    
    Uses individual inserts with transaction for rollback on failure.
    Skips existing TIPs and logs to warning file.
    Falls back to basic insert if new columns don't exist yet.
    
    Returns dict with counts: inserted, duplicates, errors
    """
    if not tips_data:
        return {'inserted': 0, 'duplicates': 0, 'errors': 0}
    
    tip_values = [t['tip'] for t in tips_data]
    existing_tips = check_existing_tips(db_manager, tip_values)
    
    inserted = 0
    duplicates = 0
    errors = 0
    
    # Try full insert first, fall back to basic if columns missing
    insert_query_full = """
        INSERT INTO noggin_data (
            tip, object_type, processing_status,
            expected_inspection_id, expected_inspection_date,
            csv_imported_at, source_filename
        )
        VALUES (%s, %s, 'pending', %s, %s, CURRENT_TIMESTAMP, %s)
    """
    
    insert_query_basic = """
        INSERT INTO noggin_data (
            tip, object_type, processing_status, csv_imported_at
        )
        VALUES (%s, %s, 'pending', CURRENT_TIMESTAMP)
    """
    
    use_full_insert = True
    
    for tip_data in tips_data:
        tip_value = tip_data['tip']
        
        if tip_value in existing_tips:
            duplicates += 1
            warning_logger.warning(
                f"DUPLICATE TIP skipped | "
                f"tip={tip_value[:16]}... | "
                f"object_type={tip_data['abbreviation']} | "
                f"inspection_id={tip_data['inspection_id']} | "
                f"source={source_file}"
            )
            continue
        
        try:
            if use_full_insert:
                db_manager.execute_update(
                    insert_query_full,
                    (
                        tip_value,
                        tip_data['object_type'],
                        tip_data['inspection_id'],
                        tip_data['inspection_date'],
                        source_file
                    )
                )
            else:
                db_manager.execute_update(
                    insert_query_basic,
                    (tip_value, tip_data['object_type'])
                )
            inserted += 1
            logger.debug(f"Inserted TIP: {tip_value[:16]}... ({tip_data['abbreviation']})")
            
        except Exception as e:
            error_str = str(e).lower()
            # Check if error is due to missing columns
            if 'column' in error_str and ('expected_inspection' in error_str or 'source_filename' in error_str):
                logger.warning("New columns not found, falling back to basic insert")
                use_full_insert = False
                # Retry with basic insert
                try:
                    db_manager.execute_update(
                        insert_query_basic,
                        (tip_value, tip_data['object_type'])
                    )
                    inserted += 1
                    logger.debug(f"Inserted TIP (basic): {tip_value[:16]}... ({tip_data['abbreviation']})")
                except Exception as e2:
                    errors += 1
                    logger.error(f"Failed to insert TIP {tip_value[:16]}...: {e2}")
            else:
                errors += 1
                logger.error(f"Failed to insert TIP {tip_value[:16]}...: {e}")
            
        except Exception as e:
            errors += 1
            logger.error(f"Failed to insert TIP {tip_value[:16]}...: {e}")
    
    logger.info(
        f"Database insert complete: {inserted} inserted, "
        f"{duplicates} duplicates, {errors} errors"
    )
    
    return {'inserted': inserted, 'duplicates': duplicates, 'errors': errors}


def write_audit_csv(tips_data: List[Dict[str, Any]], audit_dir: Path,
                    source_file: str) -> Path:
    """
    Write extracted TIPs to audit CSV file as fallback
    
    Returns path to created audit file
    """
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    audit_filename = f"tips_{timestamp}_{Path(source_file).stem}.csv"
    audit_path = audit_dir / audit_filename
    
    with open(audit_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['tip', 'object_type', 'inspection_id', 'date', 'source_file'])
        
        for tip_data in tips_data:
            writer.writerow([
                tip_data['tip'],
                tip_data['abbreviation'],
                tip_data['inspection_id'] or '',
                tip_data['inspection_date'] or '',
                source_file
            ])
    
    logger.info(f"Audit CSV written: {audit_path}")
    return audit_path


def archive_file(source_path: Path, processed_dir: Path, 
                 object_type_abbrev: str) -> Path:
    """
    Move file to processed directory with timestamp prefix
    
    Filename format: {ABBREV}_{YYYY-MM-DD}_{HHMMSS}_{original_uuid}.csv
    """
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    
    # Extract UUID portion from original filename (e.g., "exported-file-3a2c1734-37c7-4569-8859-2d5e17e8fe6e.csv")
    original_stem = source_path.stem
    if original_stem.startswith('exported-file-'):
        uuid_part = original_stem.replace('exported-file-', '')
    else:
        uuid_part = original_stem
    
    archive_filename = f"{object_type_abbrev}_{timestamp}_{uuid_part}.csv"
    archive_path = processed_dir / archive_filename
    
    shutil.move(str(source_path), str(archive_path))
    logger.debug(f"Archived: {source_path.name} -> {archive_filename}")
    
    return archive_path


def quarantine_file(source_path: Path, quarantine_dir: Path, 
                    reason: str, error_logger: logging.Logger) -> Path:
    """Move unidentified file to quarantine directory"""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    quarantine_filename = f"QUARANTINE_{timestamp}_{source_path.name}"
    quarantine_path = quarantine_dir / quarantine_filename
    
    shutil.move(str(source_path), str(quarantine_path))
    
    error_logger.error(
        f"FILE QUARANTINED | "
        f"original={source_path.name} | "
        f"reason={reason} | "
        f"quarantine_path={quarantine_path}"
    )
    
    logger.warning(f"File quarantined: {source_path.name} - {reason}")
    
    return quarantine_path


def delete_remote_file(sftp: paramiko.SFTPClient, filename: str,
                       files_to_delete: List[str]) -> None:
    """Add file to deletion queue (actual deletion happens after all processing)"""
    files_to_delete.append(filename)
    logger.debug(f"Queued for deletion: {filename}")


def execute_remote_deletions(sftp: paramiko.SFTPClient, 
                             files_to_delete: List[str]) -> int:
    """Delete all queued files from SFTP server"""
    deleted = 0
    
    for filename in files_to_delete:
        try:
            sftp.remove(filename)
            deleted += 1
            logger.debug(f"Deleted from SFTP: {filename}")
        except Exception as e:
            logger.error(f"Failed to delete {filename} from SFTP: {e}")
    
    if deleted > 0:
        logger.info(f"Deleted {deleted} files from SFTP server")
    
    return deleted


def process_single_file(
    sftp: paramiko.SFTPClient,
    remote_filename: str,
    paths: Dict[str, Path],
    db_manager: Optional[DatabaseConnectionManager],
    sftp_logger: SFTPLoggerManager,
    config: ConfigParser,
    files_to_delete: List[str]
) -> Dict[str, Any]:
    """
    Process a single CSV file from SFTP
    
    Returns dict with processing results
    """
    result = {
        'filename': remote_filename,
        'status': 'unknown',
        'object_type': None,
        'tips_found': 0,
        'inserted': 0,
        'duplicates': 0,
        'errors': 0
    }
    
    local_file = None
    
    try:
        local_file = download_file(sftp, remote_filename, paths['incoming'])
        
        try:
            id_column, object_meta = detect_object_type(local_file)
            result['object_type'] = object_meta['abbreviation']
        except ObjectTypeDetectionError as e:
            quarantine_file(local_file, paths['quarantine'], str(e), 
                           sftp_logger.error_logger)
            result['status'] = 'quarantined'
            return result
        
        tips_data = extract_tips_from_csv(local_file, id_column, object_meta)
        result['tips_found'] = len(tips_data)
        
        if not tips_data:
            logger.warning(f"No TIPs found in {remote_filename}")
            result['status'] = 'empty'
        
        write_audit = config.getboolean('processing', 'write_audit_csv', fallback=True)
        if write_audit and tips_data:
            write_audit_csv(tips_data, paths['tip_audit'], remote_filename)
        
        insert_to_db = config.getboolean('processing', 'insert_to_database', fallback=True)
        if insert_to_db and db_manager and tips_data:
            db_result = insert_tips_to_database(
                db_manager, tips_data, remote_filename, 
                sftp_logger.warning_logger
            )
            result.update(db_result)
        
        archive_file(local_file, paths['processed'], object_meta['abbreviation'])
        local_file = None
        
        delete_after = config.getboolean('processing', 'delete_from_sftp_after_archive', 
                                         fallback=True)
        if delete_after:
            delete_remote_file(sftp, remote_filename, files_to_delete)
        
        result['status'] = 'success'
        
    except Exception as e:
        logger.error(f"Error processing {remote_filename}: {e}", exc_info=True)
        sftp_logger.error_logger.error(
            f"PROCESSING FAILED | file={remote_filename} | error={e}"
        )
        result['status'] = 'error'
        result['errors'] = 1
        
        if local_file and local_file.exists():
            quarantine_file(local_file, paths['quarantine'], 
                           f"Processing error: {e}", sftp_logger.error_logger)
    
    return result


def run_sftp_download(
    sftp_config_path: str = 'config/sftp_config.ini',
    base_config: Optional[ConfigLoader] = None,
    db_manager: Optional[DatabaseConnectionManager] = None
) -> Dict[str, Any]:
    """
    Main entry point for SFTP download process
    
    Can be called standalone or from continuous processor.
    
    Args:
        sftp_config_path: Path to SFTP configuration file
        base_config: Optional existing ConfigLoader (for logging paths)
        db_manager: Optional existing database connection
        
    Returns:
        Summary dict with processing statistics
    """
    summary = {
        'start_time': datetime.now().isoformat(),
        'files_processed': 0,
        'total_tips_found': 0,
        'total_inserted': 0,
        'total_duplicates': 0,
        'total_errors': 0,
        'files_quarantined': 0,
        'files_deleted_from_sftp': 0,
        'status': 'unknown'
    }
    
    ssh_client = None
    sftp_client = None
    own_db_manager = False
    
    try:
        sftp_config = load_sftp_config(sftp_config_path)
        paths = create_directories(sftp_config)
        
        if base_config:
            log_path = Path(base_config.get('paths', 'base_log_path'))
        else:
            log_path = Path('/mnt/data/noggin/log')
        
        sftp_logger = SFTPLoggerManager(sftp_config, log_path)
        sftp_logger.configure_sftp_loggers()
        
        if db_manager is None:
            if base_config is None:
                base_config = ConfigLoader(
                    'config/base_config.ini',
                    'config/load_compliance_check_driver_loader_config.ini'
                )
            db_manager = DatabaseConnectionManager(base_config)
            own_db_manager = True
        
        ssh_client, sftp_client = connect_sftp(sftp_config)
        
        remote_dir = sftp_config.get('sftp', 'remote_directory')
        csv_files = list_csv_files(sftp_client, remote_dir)
        
        if not csv_files:
            logger.info("No CSV files found on SFTP server")
            summary['status'] = 'no_files'
            return summary
        
        files_to_delete: List[str] = []
        
        for filename, mtime in csv_files:
            logger.info(f"Processing: {filename}")
            
            result = process_single_file(
                sftp_client, filename, paths, db_manager,
                sftp_logger, sftp_config, files_to_delete
            )
            
            summary['files_processed'] += 1
            summary['total_tips_found'] += result.get('tips_found', 0)
            summary['total_inserted'] += result.get('inserted', 0)
            summary['total_duplicates'] += result.get('duplicates', 0)
            summary['total_errors'] += result.get('errors', 0)
            
            if result['status'] == 'quarantined':
                summary['files_quarantined'] += 1
        
        deleted_count = execute_remote_deletions(sftp_client, files_to_delete)
        summary['files_deleted_from_sftp'] = deleted_count
        
        summary['status'] = 'success'
        summary['end_time'] = datetime.now().isoformat()
        
        logger.info("=" * 60)
        logger.info("SFTP DOWNLOAD SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Files processed:     {summary['files_processed']}")
        logger.info(f"TIPs found:          {summary['total_tips_found']}")
        logger.info(f"TIPs inserted:       {summary['total_inserted']}")
        logger.info(f"Duplicates skipped:  {summary['total_duplicates']}")
        logger.info(f"Errors:              {summary['total_errors']}")
        logger.info(f"Files quarantined:   {summary['files_quarantined']}")
        logger.info(f"Deleted from SFTP:   {summary['files_deleted_from_sftp']}")
        logger.info("=" * 60)
        
        return summary
        
    except SFTPConnectionError as e:
        logger.error(f"SFTP connection error: {e}")
        summary['status'] = 'connection_error'
        summary['error'] = str(e)
        return summary
        
    except Exception as e:
        logger.error(f"SFTP download failed: {e}", exc_info=True)
        summary['status'] = 'error'
        summary['error'] = str(e)
        return summary
        
    finally:
        if sftp_client:
            sftp_client.close()
        if ssh_client:
            ssh_client.close()
        if own_db_manager and db_manager:
            db_manager.close_all()
        
        logger.info("SFTP connection closed")


def main() -> int:
    """Standalone entry point"""
    try:
        base_config = ConfigLoader(
            'config/base_config.ini',
            'config/load_compliance_check_driver_loader_config.ini'
        )
        
        logger_manager = LoggerManager(base_config, script_name='sftp_download_tips')
        logger_manager.configure_application_logger()
        
        logger.info("=" * 80)
        logger.info("SFTP TIP DOWNLOADER - STANDALONE MODE")
        logger.info("=" * 80)
        
        result = run_sftp_download(base_config=base_config)
        
        if result['status'] == 'success':
            return 0
        else:
            return 1
            
    except KeyboardInterrupt:
        logger.warning("Download interrupted by user")
        return 1
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
