"""
Hash Lookup Sync - Synchronise hash_lookup table from Noggin exports

Reads asset and site CSV exports from Noggin and populates the hash_lookup table.
Supports both local file processing and SFTP download.

Usage:
    python hash_lookup_sync.py --asset-file /path/to/asset.csv --site-file /path/to/site.csv
    python hash_lookup_sync.py --sftp
    python hash_lookup_sync.py --stats
"""

from __future__ import annotations
import argparse
import logging
import shutil
import sys
from dataclasses import dataclass
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
    errors: list = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


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
    'uhf': 'uhf',
}

# Site name patterns that indicate department vs team
DEPARTMENT_PATTERNS: tuple[str, ...] = (
    '- Drivers',
    '- Admin',
    'Transport',
    'Workshop',
    'Distribution',
)


def determine_asset_lookup_type(asset_type: Optional[str]) -> str:
    """
    Determine lookup_type from Noggin assetType
    
    Args:
        asset_type: The assetType value from Noggin export
        
    Returns:
        Normalised lookup_type (vehicle, trailer, uhf, or unknown)
    """
    if not asset_type or pd.isna(asset_type):
        return 'unknown'
    
    asset_type_clean = str(asset_type).strip().upper()
    
    # Handle UHF special case (lowercase in source)
    if asset_type.strip().lower() == 'uhf':
        return 'uhf'
    
    return ASSET_TYPE_MAPPING.get(asset_type_clean, 'unknown')


def format_source_type(raw_type: Optional[str]) -> str:
    """
    Format source_type as CamelCase
    
    Args:
        raw_type: Raw type value from Noggin (e.g., 'PRIME MOVER', 'businessUnit')
        
    Returns:
        CamelCase formatted string (e.g., 'PrimeMover', 'BusinessUnit')
    """
    if not raw_type or pd.isna(raw_type):
        return 'Unknown'
    
    raw_str = str(raw_type).strip()
    
    # Handle already CamelCase values (e.g., businessUnit, virtualForReporting)
    if ' ' not in raw_str and raw_str[0].islower():
        return raw_str[0].upper() + raw_str[1:]
    
    # Convert UPPER CASE or Title Case to CamelCase
    words = raw_str.replace('_', ' ').split()
    return ''.join(word.capitalize() for word in words)


def determine_site_lookup_type(site_name: str, site_type: Optional[str]) -> str:
    """
    Determine lookup_type from site name patterns and siteType
    
    Args:
        site_name: The siteName value from Noggin export
        site_type: The siteType value from Noggin export
        
    Returns:
        Either 'team' or 'department'
    """
    site_name_str = str(site_name) if site_name else ''
    
    # Check for department patterns in site name
    for pattern in DEPARTMENT_PATTERNS:
        if pattern in site_name_str:
            return 'department'
    
    # siteType 'team' maps to lookup_type 'team'
    if site_type and str(site_type).strip().lower() == 'team':
        # But check name patterns first (some 'team' siteTypes are actually departments)
        if any(p in site_name_str for p in DEPARTMENT_PATTERNS):
            return 'department'
        return 'team'
    
    # Everything else (businessUnit, virtualForReporting) is department
    return 'department'


def format_site_resolved_value(goldstar_id: Optional[str], site_name: Optional[str]) -> str:
    """
    Format resolved_value for sites as '<goldstarId> - <siteName>'
    
    Args:
        goldstar_id: The goldstarId value from Noggin export
        site_name: The siteName value from Noggin export
        
    Returns:
        Formatted string or just site_name if goldstar_id is missing
    """
    name = str(site_name).strip() if site_name and not pd.isna(site_name) else 'Unknown'
    
    if goldstar_id and not pd.isna(goldstar_id):
        gid = str(goldstar_id).strip()
        return f"{gid} - {name}"
    
    return name


def load_asset_export(csv_path: Path) -> pd.DataFrame:
    """
    Load and validate asset export CSV
    
    Args:
        csv_path: Path to asset export CSV
        
    Returns:
        DataFrame with asset data
        
    Raises:
        ValueError if required columns are missing
    """
    logger.info(f"Loading asset export from {csv_path}")
    
    df = pd.read_csv(csv_path, encoding='utf-8-sig')  # utf-8-sig handles BOM
    
    required_columns = ['nogginId', 'assetName', 'assetType']
    missing = [col for col in required_columns if col not in df.columns]
    
    if missing:
        raise ValueError(f"Asset CSV missing required columns: {missing}")
    
    logger.info(f"Loaded {len(df)} asset records")
    return df


def load_site_export(csv_path: Path) -> pd.DataFrame:
    """
    Load and validate site export CSV
    
    Args:
        csv_path: Path to site export CSV
        
    Returns:
        DataFrame with site data
        
    Raises:
        ValueError if required columns are missing
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
    Process asset DataFrame into hash_lookup records
    
    Args:
        df: Asset DataFrame
        
    Returns:
        List of (tip_hash, lookup_type, resolved_value, source_type) tuples
    """
    records = []
    skipped = 0
    
    for _, row in df.iterrows():
        tip_hash = row.get('nogginId')
        asset_name = row.get('assetName')
        asset_type = row.get('assetType')
        
        # Skip if no hash
        if not tip_hash or pd.isna(tip_hash):
            skipped += 1
            continue
        
        tip_hash = str(tip_hash).strip()
        
        # Skip if no asset name (but keep expired status records)
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
    Process site DataFrame into hash_lookup records
    
    Args:
        df: Site DataFrame
        
    Returns:
        List of (tip_hash, lookup_type, resolved_value, source_type) tuples
    """
    records = []
    skipped = 0
    
    for _, row in df.iterrows():
        tip_hash = row.get('nogginId')
        site_name = row.get('siteName')
        goldstar_id = row.get('goldstarId')
        site_type = row.get('siteType')
        
        # Skip if no hash
        if not tip_hash or pd.isna(tip_hash):
            skipped += 1
            continue
        
        tip_hash = str(tip_hash).strip()
        
        # Skip if no site name
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
    Sync records to hash_lookup table
    
    Args:
        db_manager: Database connection manager
        records: List of (tip_hash, lookup_type, resolved_value, source_type) tuples
        truncate_first: If True, truncate table before insert
        
    Returns:
        Number of records inserted
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


def download_from_sftp(config: 'ConfigLoader') -> tuple[Optional[Path], Optional[Path]]:
    """
    Download latest export files from SFTP
    
    Args:
        config: Configuration loader
        
    Returns:
        Tuple of (asset_file_path, site_file_path) or (None, None) on failure
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
    local_path = Path(config.get('sftp', 'local_download_path'))
    file_pattern = config.get('sftp', 'file_pattern', fallback='exported-file-*.csv')
    
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
        
        # List files in remote directory
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
        
        # Download the two most recent files
        downloaded = []
        for filename, _ in csv_files_with_time[:2]:
            remote_file = f"{remote_path}/{filename}"
            local_file = local_path / filename
            
            logger.info(f"Downloading {filename}")
            sftp.get(remote_file, str(local_file))
            downloaded.append(local_file)
        
        sftp.close()
        
        # Determine which file is asset vs site by checking headers
        asset_file = None
        site_file = None
        
        for file_path in downloaded:
            df = pd.read_csv(file_path, nrows=0, encoding='utf-8-sig')
            if 'assetType' in df.columns:
                asset_file = file_path
            elif 'siteType' in df.columns:
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
    Move processed file to archive folder with timestamp
    
    Args:
        file_path: File to archive
        archive_folder: Destination folder
        
    Returns:
        New path of archived file
    """
    archive_folder.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    dest_path = archive_folder / new_name
    
    shutil.move(str(file_path), str(dest_path))
    logger.info(f"Archived {file_path.name} to {dest_path}")
    
    return dest_path


def get_statistics(db_manager: 'DatabaseConnectionManager') -> dict:
    """
    Get current hash_lookup statistics
    
    Args:
        db_manager: Database connection manager
        
    Returns:
        Dictionary of statistics
    """
    stats = {}
    
    # Count by lookup_type
    type_counts = db_manager.execute_query_dict("""
        SELECT lookup_type, COUNT(*) as count
        FROM hash_lookup
        GROUP BY lookup_type
        ORDER BY lookup_type
    """)
    
    for row in type_counts:
        stats[row['lookup_type']] = row['count']
    
    # Count by source_type
    source_counts = db_manager.execute_query_dict("""
        SELECT source_type, COUNT(*) as count
        FROM hash_lookup
        WHERE source_type IS NOT NULL
        GROUP BY source_type
        ORDER BY source_type
    """)
    
    stats['by_source_type'] = {row['source_type']: row['count'] for row in source_counts}
    
    # Total count
    total = db_manager.execute_query_dict("SELECT COUNT(*) as count FROM hash_lookup")
    stats['total'] = total[0]['count'] if total else 0
    
    return stats


def print_statistics(stats: dict) -> None:
    """Print formatted statistics"""
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
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Synchronise hash_lookup table from Noggin exports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Sync from local files
    python hash_lookup_sync.py --asset-file assets.csv --site-file sites.csv
    
    # Sync from SFTP
    python hash_lookup_sync.py --sftp
    
    # Show current statistics
    python hash_lookup_sync.py --stats
    
    # Dry run (no database changes)
    python hash_lookup_sync.py --asset-file assets.csv --site-file sites.csv --dry-run
        """
    )
    
    parser.add_argument('--asset-file', type=Path, help='Path to asset export CSV')
    parser.add_argument('--site-file', type=Path, help='Path to site export CSV')
    parser.add_argument('--sftp', action='store_true', help='Download files from SFTP')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--dry-run', action='store_true', help='Process files without database changes')
    parser.add_argument('--no-archive', action='store_true', help='Do not archive processed files')
    parser.add_argument('--config', type=Path, default=Path('config/base_config.ini'),
                       help='Path to base config file')
    
    args = parser.parse_args()
    
    # Import here to avoid circular imports and allow --help without deps
    sys.path.insert(0, str(Path(__file__).parent))
    from common import ConfigLoader, LoggerManager, DatabaseConnectionManager
    
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
        
        if args.sftp:
            asset_file, site_file = download_from_sftp(config)
            if not asset_file or not site_file:
                logger.error("Failed to download files from SFTP")
                return 1
        elif args.asset_file and args.site_file:
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
            print("\nError: Specify either --sftp or both --asset-file and --site-file")
            return 1
        
        # Load and process files
        logger.info("Starting hash lookup sync")
        
        asset_df = load_asset_export(asset_file)
        site_df = load_site_export(site_file)
        
        asset_records = process_assets(asset_df)
        site_records = process_sites(site_df)
        
        all_records = asset_records + site_records
        
        logger.info(f"Total records to sync: {len(all_records)}")
        
        # Sync to database
        if args.dry_run:
            logger.info("Dry run mode - no database changes")
            print(f"\nDry run complete:")
            print(f"  Assets: {len(asset_records)}")
            print(f"  Sites: {len(site_records)}")
            print(f"  Total: {len(all_records)}")
        else:
            inserted = sync_to_database(db_manager, all_records, truncate_first=True)
            
            print(f"\nSync complete:")
            print(f"  Assets processed: {len(asset_records)}")
            print(f"  Sites processed: {len(site_records)}")
            print(f"  Total inserted: {inserted}")
        
        # Archive files
        if not args.no_archive and not args.dry_run:
            archive_path = Path(config.get('sftp', 'archive_path', 
                                          fallback='/mnt/data/noggin/sftp_archive'))
            archive_file(asset_file, archive_path)
            archive_file(site_file, archive_path)
        
        # Show final statistics
        if not args.dry_run:
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