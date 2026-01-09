"""
Hash Lookup Sync - Synchronise hash_lookup table from Noggin exports

Reads asset and site CSV exports from Noggin and populates the hash_lookup table.
Supports local file processing, pending folder scanning, and SFTP download.

Usage:
    python hash_lookup_sync.py --process-pending
    python hash_lookup_sync.py --asset-file /path/to/asset.csv --site-file /path/to/site.csv
    python hash_lookup_sync.py --sftp
    python hash_lookup_sync.py --stats
"""

from __future__ import annotations
import argparse
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    'SKEL': 'trailer',
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
    etl_dir = script_dir / 'etl'
    
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
        
        return 0
        
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        print(f"\nError: {e}")
        return 1
    
    finally:
        db_manager.close_all()


if __name__ == "__main__":
    sys.exit(main())