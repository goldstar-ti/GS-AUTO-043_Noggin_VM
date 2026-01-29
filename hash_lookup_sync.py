"""
Hash Lookup Sync - Synchronise hash_lookup table from Noggin exports

Reads asset and site CSV exports from Noggin and populates the hash_lookup table.
Supports local file processing, pending folder scanning, and SFTP download.

Additionally provides functionality to resolve unknown hash values in the database
by looking them up in the updated hash_lookup table and regenerating text files.

Usage:
    python hash_lookup_sync.py --process-pending
    python hash_lookup_sync.py --asset-file /path/to/asset.csv --site-file /path/to/site.csv
    python hash_lookup_sync.py --sftp
    python hash_lookup_sync.py --stats
    python hash_lookup_sync.py --process-pending --resolve-unknown-hashes
"""

from __future__ import annotations
import argparse
import json
import logging
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import pandas as pd

logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class SyncStatistics:
    """Statistics from a sync operation"""
    assets_processed: int = 0
    assets_skipped: int = 0
    sites_processed: int = 0
    sites_skipped: int = 0
    total_inserted: int = 0
    errors: list = field(default_factory=list)


# Mapping from Noggin assetType to lookup_type
ASSET_TYPE_MAPPING: dict[str, str] = {
    'PRIME MOVER': 'vehicle',
    'RIGID': 'vehicle',
    'VEHICLE': 'vehicle',
    'LIGHT VEHICLE': 'vehicle',
    'FORKLIFT': 'vehicle',
    'TRAILER': 'trailer',
    'DROPDECK': 'trailer',
    'DOLLY': 'trailer',
    'UHF': 'uhf',
}

# Site name patterns that indicate department vs team
DEPARTMENT_PATTERNS: tuple[str, ...] = (
    '- Drivers',
    '- Admin',
    'Transport',
    'Workshop',
    'Distribution',
)


def get_default_paths() -> dict[str, Path]:
    """
    Get default paths based on script location.
    Assumes script is in /home/noggin_admin/scripts/ and etl folder is a sibling.
    """
    script_dir = Path(__file__).parent.resolve()
    etl_dir = Path('/mnt/data/noggin/etl')
    
    return {
        'hash_sync_pending': etl_dir / 'hash_sync' / 'pending',
        'hash_sync_processed': etl_dir / 'hash_sync' / 'processed',
        'hash_sync_error': etl_dir / 'hash_sync' / 'error',
        'sftp_downloads': etl_dir / 'sftp' / 'downloads',
        'sftp_archive': etl_dir / 'sftp' / 'archive',
        'log': etl_dir / 'log',
    }


def determine_asset_lookup_type(asset_type: Optional[str]) -> str:
    """
    Determine lookup_type from Noggin assetType.
    
    The asset_type parameter comes directly from Noggin's export and can be values
    like 'PRIME MOVER', 'TRAILER', 'uhf', etc. This function normalises these to
    broader categories used for filtering: vehicle, trailer, uhf, or unknown.
    """
    if not asset_type or pd.isna(asset_type):
        return 'unknown'
    
    asset_type_upper = str(asset_type).strip().upper()
    return ASSET_TYPE_MAPPING.get(asset_type_upper, 'unknown')


def format_source_type(raw_type: Optional[str]) -> str:
    """
    Format source_type as CamelCase.
    
    Converts Noggin's raw type values (e.g., 'PRIME MOVER', 'businessUnit') into
    consistent CamelCase format (e.g., 'PrimeMover', 'BusinessUnit') for storage.
    """
    if not raw_type or pd.isna(raw_type):
        return 'Unknown'
    
    raw_str = str(raw_type).strip()
    
    # Handle already camelCase values (e.g., businessUnit, virtualForReporting)
    if ' ' not in raw_str and raw_str[0].islower():
        return raw_str[0].upper() + raw_str[1:]
    
    # Convert UPPER CASE or Title Case to CamelCase
    words = raw_str.replace('_', ' ').split()
    return ''.join(word.capitalize() for word in words)


def determine_site_lookup_type(site_name: str, site_type: Optional[str]) -> str:
    """
    Determine lookup_type from site name patterns and siteType.
    
    Sites with names containing patterns like '- Drivers' or '- Admin' are classified
    as departments. Sites with siteType 'team' that don't match department patterns
    are classified as teams. Everything else (businessUnit, virtualForReporting) 
    becomes department.
    """
    site_name_str = str(site_name) if site_name else ''
    
    # Check for department patterns in site name
    for pattern in DEPARTMENT_PATTERNS:
        if pattern in site_name_str:
            return 'department'
    
    # siteType 'team' maps to lookup_type 'team' unless name suggests department
    if site_type and str(site_type).strip().lower() == 'team':
        if any(p in site_name_str for p in DEPARTMENT_PATTERNS):
            return 'department'
        return 'team'
    
    # Everything else (businessUnit, virtualForReporting) is department
    return 'department'


def format_site_resolved_value(goldstar_id: Optional[str], site_name: Optional[str]) -> str:
    """
    Format resolved_value for sites as '<goldstarId> - <siteName>'.
    
    If goldstar_id is missing or empty, returns just the site name.
    """
    name = str(site_name).strip() if site_name and not pd.isna(site_name) else 'Unknown'
    
    if goldstar_id and not pd.isna(goldstar_id):
        gid = str(goldstar_id).strip()
        return f"{gid} - {name}"
    
    return name


def detect_file_type(csv_path: Path) -> Optional[str]:
    """
    Detect whether a CSV file is an asset export or site export.
    
    Reads the header row and looks for distinctive columns:
    - 'assetType' or 'assetName' indicates asset export
    - 'siteType' or 'siteName' indicates site export
    
    Returns 'asset', 'site', or None if indeterminate.
    """
    try:
        df = pd.read_csv(csv_path, nrows=0, encoding='utf-8-sig')
        columns = set(df.columns)
        
        # Asset exports have assetType and/or assetName columns
        if 'assetType' in columns or 'assetName' in columns:
            return 'asset'
        
        # Site exports have siteType and/or siteName columns
        if 'siteType' in columns or 'siteName' in columns:
            return 'site'
        
        logger.warning(f"Could not determine file type for {csv_path.name}. Columns: {columns}")
        return None
        
    except Exception as e:
        logger.error(f"Error reading {csv_path}: {e}")
        return None


def load_asset_export(csv_path: Path) -> pd.DataFrame:
    """
    Load and validate asset export CSV.
    
    Expects columns: nogginId, assetName, assetType (at minimum).
    """
    logger.info(f"Loading asset export from {csv_path}")
    
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    required_columns = ['nogginId', 'assetName', 'assetType']
    missing = [col for col in required_columns if col not in df.columns]
    
    if missing:
        raise ValueError(f"Asset CSV missing required columns: {missing}")
    
    logger.info(f"Loaded {len(df)} asset records")
    return df


def load_site_export(csv_path: Path) -> pd.DataFrame:
    """
    Load and validate site export CSV.
    
    Expects columns: nogginId, siteName, goldstarId, siteType (at minimum).
    """
    logger.info(f"Loading site export from {csv_path}")
    
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    required_columns = ['nogginId', 'siteName', 'goldstarId', 'siteType']
    missing = [col for col in required_columns if col not in df.columns]
    
    if missing:
        raise ValueError(f"Site CSV missing required columns: {missing}")
    
    logger.info(f"Loaded {len(df)} site records")
    return df


def process_assets(df: pd.DataFrame) -> list[tuple[str, str, str, str]]:
    """
    Process asset DataFrame into hash_lookup records.
    
    Returns list of (tip_hash, lookup_type, resolved_value, source_type) tuples.
    """
    records = []
    skipped = 0
    
    for _, row in df.iterrows():
        tip_hash = row.get('nogginId')
        asset_name = row.get('assetName')
        asset_type = row.get('assetType')
        
        if not tip_hash or pd.isna(tip_hash):
            skipped += 1
            continue
        
        tip_hash = str(tip_hash).strip()
        
        # Keep expired/empty name records with 'Unknown' as resolved value
        if not asset_name or pd.isna(asset_name):
            asset_name = 'Unknown'
            logger.debug(f"Asset {tip_hash[:16]}... has no name, using 'Unknown'")
        
        resolved_value = str(asset_name).strip()
        lookup_type = determine_asset_lookup_type(asset_type)
        source_type = format_source_type(asset_type)
        
        if lookup_type == 'unknown':
            logger.warning(f"Unknown asset type '{asset_type}' for {resolved_value} ({tip_hash[:16]}...)")
        
        records.append((tip_hash, lookup_type, resolved_value, source_type))
    
    logger.info(f"Processed {len(records)} assets, skipped {skipped}")
    return records


def process_sites(df: pd.DataFrame) -> list[tuple[str, str, str, str]]:
    """
    Process site DataFrame into hash_lookup records.
    
    Returns list of (tip_hash, lookup_type, resolved_value, source_type) tuples.
    """
    records = []
    skipped = 0
    
    for _, row in df.iterrows():
        tip_hash = row.get('nogginId')
        site_name = row.get('siteName')
        goldstar_id = row.get('goldstarId')
        site_type = row.get('siteType')
        
        if not tip_hash or pd.isna(tip_hash):
            skipped += 1
            continue
        
        tip_hash = str(tip_hash).strip()
        
        if not site_name or pd.isna(site_name):
            skipped += 1
            logger.debug(f"Site {tip_hash[:16]}... has no name, skipping")
            continue
        
        resolved_value = format_site_resolved_value(goldstar_id, site_name)
        lookup_type = determine_site_lookup_type(site_name, site_type)
        source_type = format_source_type(site_type)
        
        records.append((tip_hash, lookup_type, resolved_value, source_type))
    
    logger.info(f"Processed {len(records)} sites, skipped {skipped}")
    return records


def sync_to_database(
    db_manager: 'DatabaseConnectionManager',
    records: list[tuple[str, str, str, str]],
    truncate_first: bool = True
) -> int:
    """
    Sync records to hash_lookup table.
    
    When truncate_first is True (default), clears the table before inserting.
    This ensures the table exactly matches the authoritative source files.
    """
    if truncate_first:
        logger.info("Truncating hash_lookup table")
        db_manager.execute_update("TRUNCATE TABLE hash_lookup")
    
    if not records:
        logger.warning("No records to insert")
        return 0
    
    logger.info(f"Inserting {len(records)} records into hash_lookup")
    
    insert_query = """
        INSERT INTO hash_lookup (tip_hash, lookup_type, resolved_value, source_type, created_at, updated_at)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (tip_hash) DO UPDATE SET
            lookup_type = EXCLUDED.lookup_type,
            resolved_value = EXCLUDED.resolved_value,
            source_type = EXCLUDED.source_type,
            updated_at = CURRENT_TIMESTAMP
    """
    
    inserted = 0
    for tip_hash, lookup_type, resolved_value, source_type in records:
        try:
            db_manager.execute_update(insert_query, (tip_hash, lookup_type, resolved_value, source_type))
            inserted += 1
        except Exception as e:
            logger.error(f"Failed to insert {tip_hash[:16]}...: {e}")
    
    logger.info(f"Successfully inserted {inserted} records")
    return inserted


def scan_pending_folder(pending_path: Path) -> tuple[Optional[Path], Optional[Path]]:
    """
    Scan pending folder for asset and site CSV files.
    
    Auto-detects file types by examining headers. Returns tuple of 
    (asset_file, site_file). Either or both may be None if not found.
    """
    if not pending_path.exists():
        logger.warning(f"Pending folder does not exist: {pending_path}")
        return None, None
    
    csv_files = list(pending_path.glob('*.csv'))
    
    if not csv_files:
        logger.info(f"No CSV files found in {pending_path}")
        return None, None
    
    logger.info(f"Found {len(csv_files)} CSV file(s) in pending folder")
    
    asset_file: Optional[Path] = None
    site_file: Optional[Path] = None
    
    for csv_path in csv_files:
        file_type = detect_file_type(csv_path)
        
        if file_type == 'asset':
            if asset_file:
                logger.warning(f"Multiple asset files found. Using {asset_file.name}, ignoring {csv_path.name}")
            else:
                asset_file = csv_path
                logger.info(f"Detected asset file: {csv_path.name}")
                
        elif file_type == 'site':
            if site_file:
                logger.warning(f"Multiple site files found. Using {site_file.name}, ignoring {csv_path.name}")
            else:
                site_file = csv_path
                logger.info(f"Detected site file: {csv_path.name}")
                
        else:
            logger.warning(f"Unknown file type, skipping: {csv_path.name}")
    
    return asset_file, site_file


def download_from_sftp(config: 'ConfigLoader', paths: dict[str, Path]) -> tuple[Optional[Path], Optional[Path]]:
    """
    Download latest export files from SFTP.
    
    Connects to Noggin's SFTP server, downloads the two most recent CSV files,
    and returns paths to the downloaded asset and site files.
    """
    try:
        import paramiko
    except ImportError:
        logger.error("paramiko not installed. Run: pip install paramiko")
        return None, None
    
    host = config.get('sftp', 'host')
    port = config.getint('sftp', 'port')
    username = config.get('sftp', 'username')
    key_path = config.get('sftp', 'private_key_path')
    remote_path = config.get('sftp', 'remote_path')
    local_path = paths['sftp_downloads']
    
    local_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Connecting to SFTP {host}:{port}")
    
    try:
        key = paramiko.RSAKey.from_private_key_file(key_path)
    except Exception as e:
        logger.error(f"Failed to load private key from {key_path}: {e}")
        return None, None
    
    transport = paramiko.Transport((host, port))
    
    try:
        transport.connect(username=username, pkey=key)
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        files = sftp.listdir(remote_path)
        csv_files = [f for f in files if f.startswith('exported-file-') and f.endswith('.csv')]
        
        if len(csv_files) < 2:
            logger.error(f"Expected at least 2 CSV files, found {len(csv_files)}")
            return None, None
        
        # Sort by modification time (newest first)
        csv_files_with_time = []
        for f in csv_files:
            stat = sftp.stat(f"{remote_path}/{f}")
            csv_files_with_time.append((f, stat.st_mtime))
        
        csv_files_with_time.sort(key=lambda x: x[1], reverse=True)
        
        downloaded = []
        for filename, _ in csv_files_with_time[:2]:
            remote_file = f"{remote_path}/{filename}"
            local_file = local_path / filename
            
            logger.info(f"Downloading {filename}")
            sftp.get(remote_file, str(local_file))
            downloaded.append(local_file)
        
        sftp.close()
        
        # Detect file types
        asset_file = None
        site_file = None
        
        for file_path in downloaded:
            file_type = detect_file_type(file_path)
            if file_type == 'asset':
                asset_file = file_path
            elif file_type == 'site':
                site_file = file_path
        
        if not asset_file or not site_file:
            logger.error("Could not identify asset and site files from downloaded CSVs")
            return None, None
        
        logger.info(f"Asset file: {asset_file.name}")
        logger.info(f"Site file: {site_file.name}")
        
        return asset_file, site_file
        
    except Exception as e:
        logger.error(f"SFTP operation failed: {e}")
        return None, None
    
    finally:
        transport.close()


def archive_file(file_path: Path, archive_folder: Path) -> Path:
    """
    Move processed file to archive folder with timestamp suffix.
    """
    archive_folder.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    dest_path = archive_folder / new_name
    
    shutil.move(str(file_path), str(dest_path))
    logger.info(f"Archived {file_path.name} to {dest_path}")
    
    return dest_path


def move_to_error(file_path: Path, error_folder: Path) -> Path:
    """
    Move failed file to error folder with timestamp suffix.
    """
    error_folder.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    dest_path = error_folder / new_name
    
    shutil.move(str(file_path), str(dest_path))
    logger.warning(f"Moved {file_path.name} to error folder: {dest_path}")
    
    return dest_path


def get_statistics(db_manager: 'DatabaseConnectionManager') -> dict:
    """
    Get current hash_lookup statistics.
    """
    stats = {}
    
    type_counts = db_manager.execute_query_dict("""
        SELECT lookup_type, COUNT(*) as count
        FROM hash_lookup
        GROUP BY lookup_type
        ORDER BY lookup_type
    """)
    
    for row in type_counts:
        stats[row['lookup_type']] = row['count']
    
    source_counts = db_manager.execute_query_dict("""
        SELECT source_type, COUNT(*) as count
        FROM hash_lookup
        WHERE source_type IS NOT NULL
        GROUP BY source_type
        ORDER BY source_type
    """)
    
    stats['by_source_type'] = {row['source_type']: row['count'] for row in source_counts}
    
    total = db_manager.execute_query_dict("SELECT COUNT(*) as count FROM hash_lookup")
    stats['total'] = total[0]['count'] if total else 0
    
    return stats


def print_statistics(stats: dict) -> None:
    """Print formatted statistics to console."""
    print("\n" + "=" * 60)
    print("HASH LOOKUP STATISTICS")
    print("=" * 60)
    
    print("\nBy Lookup Type:")
    print("-" * 40)
    for lookup_type in ['vehicle', 'trailer', 'team', 'department', 'uhf', 'unknown']:
        count = stats.get(lookup_type, 0)
        if count > 0:
            print(f"  {lookup_type:<15} {count:>6}")
    
    print(f"\n  {'TOTAL':<15} {stats.get('total', 0):>6}")
    
    if 'by_source_type' in stats and stats['by_source_type']:
        print("\nBy Source Type (Noggin assetType/siteType):")
        print("-" * 40)
        for source_type, count in sorted(stats['by_source_type'].items()):
            print(f"  {source_type:<20} {count:>6}")
    
    print("=" * 60 + "\n")


def extract_hash_from_unknown(value: str) -> Optional[str]:
    """
    Extract hash from 'Unknown (hash...)' format.
    
    Args:
        value: String like "Unknown (103814bcd3232967...)" or just a hash
        
    Returns:
        Extracted hash or None if not in expected format
    """
    if not value or not isinstance(value, str):
        return None
    
    # Check if it starts with "Unknown"
    if value.startswith('Unknown'):
        # Pattern: Unknown (hash...) or Unknown
        match = re.search(r'Unknown \(([a-f0-9]+)\.\.\.?\)', value)
        if match:
            return match.group(1)
        return None
    
    # If it's just a plain hash, return as-is
    if re.match(r'^[a-f0-9]{64}$', value):
        return value
    
    return None


def resolve_unknown_hashes(db_manager: 'DatabaseConnectionManager', 
                          config: 'ConfigLoader',
                          paths: dict,
                          config_file_path: Path) -> Dict[str, int]:
    """
    Resolve unknown hash values in database and regenerate text files
    
    Queries noggin_data for records with 'Unknown' values in vehicle, trailer,
    department, or team fields. Attempts to resolve using hash columns and 
    updated hash_lookup table. Updates database and regenerates text files.
    
    Args:
        db_manager: Database connection manager
        config: Configuration loader
        paths: Dictionary of paths including log directory
        
    Returns:
        Dictionary with resolution statistics
    """
    import common
    from datetime import datetime
    from processors.report_generator import create_report_generator
    
    logger.info("Starting unknown hash resolution")

    CONFIG_PATH = '../config/base_config.ini'
    config = ConfigLoader(CONFIG_PATH)    

    LOG_DIR = Path(config.get('paths', 'base_log_path', fallback='/mnt/data/noggin/log'))
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_filename = f"web_app_{datetime.now().strftime('%Y%m%d')}.log"
    log_file_path = LOG_DIR / log_filename

    # Setup log files
    log_path = paths.get('log', Path('/mnt/data/noggin/log'))
    log_path.mkdir(parents=True, exist_ok=True)
    
    date_stamp = datetime.now().strftime('%Y%m%d')
    audit_log_file = log_path / f'hash_resolution_audit_{date_stamp}.log'
    manual_review_file = log_path / f'manual_hash_review_{date_stamp}.log'
    
    stats = {
        'records_checked': 0,
        'fields_resolved': 0,
        'fields_unresolved': 0,
        'reports_regenerated': 0,
        'errors': 0
    }
    
    # Query for records with Unknown values (excluding csv_imported)
    query = """
        SELECT tip, object_type, inspection_date, noggin_reference,
               vehicle_hash, vehicle, trailer_hash, trailer, 
               trailer2_hash, trailer2, trailer3_hash, trailer3,
               department_hash, department, team_hash, team,
               raw_json, source_filename
        FROM noggin_schema.noggin_data
        WHERE processing_status != 'csv_imported'
          AND (vehicle LIKE 'Unknown%' 
               OR trailer LIKE 'Unknown%'
               OR trailer2 LIKE 'Unknown%' 
               OR trailer3 LIKE 'Unknown%'
               OR department LIKE 'Unknown%' 
               OR team LIKE 'Unknown%')
        ORDER BY inspection_date DESC
    """
    
    try:
        records = db_manager.execute_query_dict(query)
        logger.info(f"Found {len(records)} records with unknown hash values")
        
        if not records:
            logger.info("No records to process")
            return stats
        
        # Initialize hash manager
        hash_manager = common.HashManager(config, db_manager)
        hash_manager.invalidate_cache()  # Force reload from updated hash_lookup table
        
        # Process each record
        for record in records:
            stats['records_checked'] += 1
            tip = record['tip']
            object_type = record['object_type']
            inspection_id = record['noggin_reference']
            
            logger.info(f"Processing {object_type} {inspection_id} (TIP: {tip[:16]}...)")
            
            updates = {}
            fields_resolved_this_record = []
            fields_unresolved_this_record = []
            
            # Check each hash field
            hash_fields = [
                ('vehicle_hash', 'vehicle', 'vehicle'),
                ('trailer_hash', 'trailer', 'trailer'),
                ('trailer2_hash', 'trailer2', 'trailer'),
                ('trailer3_hash', 'trailer3', 'trailer'),
                ('department_hash', 'department', 'department'),
                ('team_hash', 'team', 'team')
            ]
            
            for hash_col, text_col, lookup_type in hash_fields:
                text_value = record.get(text_col)
                hash_value = record.get(hash_col)
                
                # Skip if text field doesn't start with Unknown or hash is missing
                if not text_value or not hash_value:
                    continue
                if not text_value.startswith('Unknown'):
                    continue
                
                # Try to resolve hash
                resolved = hash_manager.lookup_hash(
                    lookup_type, 
                    hash_value, 
                    tip, 
                    inspection_id
                )
                
                # Check if resolution succeeded (not "Unknown (...)")
                if not resolved.startswith('Unknown'):
                    updates[text_col] = resolved
                    fields_resolved_this_record.append(f"{text_col}={resolved}")
                    stats['fields_resolved'] += 1
                    
                    # Log to audit file
                    with open(audit_log_file, 'a', encoding='utf-8') as f:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f"{timestamp} | {object_type} | {inspection_id} | "
                               f"{text_col}: '{text_value}' -> '{resolved}'\n")
                else:
                    fields_unresolved_this_record.append(f"{text_col}={hash_value[:16]}...")
                    stats['fields_unresolved'] += 1
                    
                    # Log to manual review file
                    with open(manual_review_file, 'a', encoding='utf-8') as f:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f"{timestamp} | {object_type} | {inspection_id} | "
                               f"{text_col} | {lookup_type} | {hash_value}\n")
            
            # Update database if any fields resolved
            if updates:
                update_fields = ', '.join([f"{col} = %s" for col in updates.keys()])
                update_query = f"""
                    UPDATE noggin_schema.noggin_data
                    SET {update_fields}
                    WHERE tip = %s
                """
                values = list(updates.values()) + [tip]
                
                try:
                    db_manager.execute_update(update_query, values)
                    logger.info(f"Updated {len(updates)} fields for {inspection_id}")
                    
                    # Regenerate text file
                    if record.get('raw_json'):
                        try:
                            regenerate_text_file(
                                record, updates, config, hash_manager, config_file_path
                            )
                            stats['reports_regenerated'] += 1
                            logger.info(f"Regenerated report for {inspection_id}")
                        except Exception as e:
                            logger.error(f"Failed to regenerate report for {inspection_id}: {e}")
                            stats['errors'] += 1
                    
                    logger.info(f"Resolved: {', '.join(fields_resolved_this_record)}")
                    
                except Exception as e:
                    logger.error(f"Failed to update database for {inspection_id}: {e}")
                    stats['errors'] += 1
            
            if fields_unresolved_this_record:
                logger.warning(f"Unresolved: {', '.join(fields_unresolved_this_record)}")
        
        # Summary
        logger.info("=" * 60)
        logger.info("HASH RESOLUTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Records checked:      {stats['records_checked']}")
        logger.info(f"Fields resolved:      {stats['fields_resolved']}")
        logger.info(f"Fields unresolved:    {stats['fields_unresolved']}")
        logger.info(f"Reports regenerated:  {stats['reports_regenerated']}")
        logger.info(f"Errors:               {stats['errors']}")
        logger.info("=" * 60)
        
        if stats['fields_resolved'] > 0:
            logger.info(f"Audit log: {audit_log_file}")
        if stats['fields_unresolved'] > 0:
            logger.info(f"Manual review log: {manual_review_file}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Hash resolution failed: {e}", exc_info=True)
        stats['errors'] += 1
        return stats


def regenerate_text_file(record: Dict[str, Any], 
                         updates: Dict[str, str],
                         config: 'ConfigLoader',
                         hash_manager: 'HashManager',
                         config_file_path: Path) -> None:
    """
    Regenerate text file for a record with updated hash resolutions
    
    Args:
        record: Database record with raw_json field
        updates: Dictionary of field updates
        config: Configuration loader
        hash_manager: Hash manager instance
        config_file_path: Path to base config file for deriving other config paths
    """
    import common
    import json
    from pathlib import Path
    from processors.report_generator import create_report_generator
    
    # Parse raw JSON
    try:
        response_data = json.loads(record['raw_json'])
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Invalid JSON in raw_json field: {e}")
    
    # Update response_data with resolved values
    # The hash fields stay the same, but we need to ensure the report
    # generator will use the resolved values from the database
    # Actually, we should reload the config for the specific object type
    
    object_type = record['object_type']
    inspection_id = record['noggin_reference']
    inspection_date = record['inspection_date']
    
    # Load object-specific config
    object_configs = {
        'LCD': 'load_compliance_check_driver_loader_config.ini',
        'LCS': 'load_compliance_check_supervisor_manager_config.ini',
        'CC': 'coupling_compliance_check_config.ini',
        'TA': 'trailer_audits_config.ini',
        'SO': 'site_observations_config.ini',
        'FPI': 'forklift_prestart_inspection_config.ini'
    }
    
    config_filename = object_configs.get(object_type)
    if not config_filename:
        raise ValueError(f"Unknown object type: {object_type}")
    
    # Determine config directory from base config path
    config_dir = config_file_path.parent
    obj_config_path = config_dir / config_filename
    
    # Load config for this object type
    obj_config = common.ConfigLoader(str(obj_config_path))
    
    # Create report generator
    report_gen = create_report_generator(obj_config, hash_manager)
    
    # Generate report
    report = report_gen.generate_report(response_data, inspection_id)
    
    # Calculate output path
    base_output_path = Path(config.get('paths', 'base_output_path', 
                                       fallback='/mnt/data/noggin/out'))
    
    if inspection_date:
        year = inspection_date.strftime('%Y')
        month = inspection_date.strftime('%m')
    else:
        year = 'unknown'
        month = 'unknown'
    
    # Build folder path: base/object_type/year/month/date_inspection_id
    date_str = inspection_date.strftime('%Y-%m-%d') if inspection_date else 'unknown_date'
    folder_name = f"{date_str} {inspection_id}"
    
    inspection_folder = base_output_path / object_type / year / month / folder_name
    inspection_folder.mkdir(parents=True, exist_ok=True)
    
    # Save report (this will overwrite existing file)
    date_iso = inspection_date.isoformat() if inspection_date else None
    report_gen.save_report(report, inspection_folder, inspection_id, date_iso)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Synchronise hash_lookup table from Noggin exports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process files from pending folder (auto-detects asset vs site)
    python hash_lookup_sync.py --process-pending
    
    # Sync from specific files
    python hash_lookup_sync.py --asset-file assets.csv --site-file sites.csv
    
    # Download and sync from SFTP
    python hash_lookup_sync.py --sftp
    
    # Sync and then resolve unknown hashes in database
    python hash_lookup_sync.py --process-pending --resolve-unknown-hashes
    
    # Show current statistics only
    python hash_lookup_sync.py --stats
    
    # Dry run (no database changes)
    python hash_lookup_sync.py --process-pending --dry-run
        """
    )
    
    parser.add_argument('--process-pending', action='store_true',
                       help='Process files from pending folder with auto-detection')
    parser.add_argument('--asset-file', type=Path, help='Path to asset export CSV')
    parser.add_argument('--site-file', type=Path, help='Path to site export CSV')
    parser.add_argument('--sftp', action='store_true', help='Download files from SFTP')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--dry-run', action='store_true', help='Process files without database changes')
    parser.add_argument('--no-archive', action='store_true', help='Do not archive processed files')
    parser.add_argument('--resolve-unknown-hashes', action='store_true',
                       help='After sync, attempt to resolve unknown hashes in database and regenerate reports')
    parser.add_argument('--config', type=Path, default=Path('config/base_config.ini'),
                       help='Path to base config file')
    
    args = parser.parse_args()
    
    # Import dependencies here to allow --help without loading modules
    sys.path.insert(0, str(Path(__file__).parent))
    from common import ConfigLoader, LoggerManager, DatabaseConnectionManager
    
    # Get default paths based on script location
    paths = get_default_paths()
    
    # Load configuration
    config = ConfigLoader(str(args.config))
    
    # Configure logging
    logger_manager = LoggerManager(config, script_name='hash_lookup_sync')
    logger_manager.configure_application_logger()
    
    # Connect to database
    db_manager = DatabaseConnectionManager(config)
    
    try:
        # Stats only mode
        if args.stats:
            stats = get_statistics(db_manager)
            print_statistics(stats)
            return 0
        
        # Determine file sources
        asset_file: Optional[Path] = None
        site_file: Optional[Path] = None
        source_mode: str = ''
        
        # Track records separately for reporting
        asset_records: list = []
        site_records: list = []
        
        if args.process_pending:
            source_mode = 'pending'
            asset_file, site_file = scan_pending_folder(paths['hash_sync_pending'])
            
            if not asset_file and not site_file:
                print("\nNo files found in pending folder")
                print(f"  Location: {paths['hash_sync_pending']}")
                print("\nPlace asset and site export CSVs in the pending folder and run again.")
                return 0
                
        elif args.sftp:
            source_mode = 'sftp'
            asset_file, site_file = download_from_sftp(config, paths)
            if not asset_file or not site_file:
                logger.error("Failed to download files from SFTP")
                return 1
                
        elif args.asset_file and args.site_file:
            source_mode = 'manual'
            asset_file = args.asset_file
            site_file = args.site_file
            
            if not asset_file.exists():
                logger.error(f"Asset file not found: {asset_file}")
                return 1
            if not site_file.exists():
                logger.error(f"Site file not found: {site_file}")
                return 1
        else:
            parser.print_help()
            print("\nError: Specify --process-pending, --sftp, or both --asset-file and --site-file")
            return 1
        
        # Validate we have at least one file
        if not asset_file and not site_file:
            logger.error("No valid files to process")
            return 1
        
        # Load and process files
        logger.info("Starting hash lookup sync")
        
        all_records = []
        processed_files = []
        
        if asset_file:
            try:
                asset_df = load_asset_export(asset_file)
                asset_records = process_assets(asset_df)
                all_records.extend(asset_records)
                processed_files.append(('asset', asset_file, True))
                logger.info(f"Asset records: {len(asset_records)}")
            except Exception as e:
                logger.error(f"Failed to process asset file: {e}")
                processed_files.append(('asset', asset_file, False))
        
        if site_file:
            try:
                site_df = load_site_export(site_file)
                site_records = process_sites(site_df)
                all_records.extend(site_records)
                processed_files.append(('site', site_file, True))
                logger.info(f"Site records: {len(site_records)}")
            except Exception as e:
                logger.error(f"Failed to process site file: {e}")
                processed_files.append(('site', site_file, False))
        
        logger.info(f"Total records to sync: {len(all_records)}")
        
        # Sync to database
        if args.dry_run:
            logger.info("Dry run mode - no database changes")
            print(f"\nDry run complete:")
            print(f"  Assets: {len(asset_records)}")
            print(f"  Sites: {len(site_records)}")
            print(f"  Total: {len(all_records)}")
        else:
            if all_records:
                inserted = sync_to_database(db_manager, all_records, truncate_first=True)
                
                print(f"\nSync complete:")
                print(f"  Assets processed: {len(asset_records)}")
                print(f"  Sites processed: {len(site_records)}")
                print(f"  Total inserted: {inserted}")
            else:
                print("\nNo records to sync")
        
        # Move processed files to appropriate folders
        if not args.no_archive and not args.dry_run:
            for file_type, file_path, success in processed_files:
                if success:
                    archive_file(file_path, paths['hash_sync_processed'])
                else:
                    move_to_error(file_path, paths['hash_sync_error'])
        
        # Show final statistics
        if not args.dry_run and all_records:
            stats = get_statistics(db_manager)
            print_statistics(stats)
        
        # Resolve unknown hashes if requested
        if args.resolve_unknown_hashes and not args.dry_run:
            logger.info("Starting unknown hash resolution process")
            resolution_stats = resolve_unknown_hashes(db_manager, config, paths, args.config)
            
            print("\nHash Resolution Summary:")
            print(f"  Records checked:      {resolution_stats['records_checked']}")
            print(f"  Fields resolved:      {resolution_stats['fields_resolved']}")
            print(f"  Fields unresolved:    {resolution_stats['fields_unresolved']}")
            print(f"  Reports regenerated:  {resolution_stats['reports_regenerated']}")
            print(f"  Errors:               {resolution_stats['errors']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        print(f"\nError: {e}")
        return 1
    
    finally:
        db_manager.close_all()


if __name__ == "__main__":
    sys.exit(main())