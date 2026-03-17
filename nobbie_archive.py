"""
Monthly Archive Script for SFTP Processed Files

Compresses processed CSV files from previous month into tar.gz archive.
Intended to run on the first day of each month via cron.

Cron entry example (runs at 2 AM on 1st of each month):
0 2 1 * * /path/to/venv/bin/python /path/to/archive_monthly_sftp.py

Usage:
    python archive_monthly_sftp.py                    # Archive previous month
    python archive_monthly_sftp.py --month 2024-12   # Archive specific month
    python archive_monthly_sftp.py --dry-run         # Preview without changes
"""

from __future__ import annotations
import argparse
import gzip
import logging
import shutil
import sys
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

logger: logging.Logger = logging.getLogger(__name__)


def setup_logging(log_path: Optional[Path] = None) -> None:
    """Configure basic logging for standalone execution"""
    log_format = '%(asctime)s | %(levelname)-8s | %(message)s'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_path:
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / f"archive_monthly_{datetime.now().strftime('%Y%m%d')}.log"
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers
    )


def get_previous_month(reference_date: Optional[datetime] = None) -> Tuple[int, int]:
    """Get year and month for previous month"""
    if reference_date is None:
        reference_date = datetime.now()
    
    first_of_current = reference_date.replace(day=1)
    last_of_previous = first_of_current - timedelta(days=1)
    
    return last_of_previous.year, last_of_previous.month


def parse_month_arg(month_str: str) -> Tuple[int, int]:
    """Parse YYYY-MM string to year, month tuple"""
    try:
        parts = month_str.split('-')
        if len(parts) != 2:
            raise ValueError("Expected YYYY-MM format")
        
        year = int(parts[0])
        month = int(parts[1])
        
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 1 and 12")
        if not (2000 <= year <= 2100):
            raise ValueError("Year must be between 2000 and 2100")
        
        return year, month
        
    except Exception as e:
        raise ValueError(f"Invalid month format '{month_str}': {e}")


def find_files_for_month(processed_dir: Path, year: int, month: int) -> List[Path]:
    """
    Find all CSV files in processed directory for specified month
    
    Files are named: {ABBREV}_{YYYY-MM-DD}_{HHMMSS}_{uuid}.csv
    """
    month_prefix = f"{year}-{month:02d}-"
    matching_files = []
    
    for csv_file in processed_dir.glob('*.csv'):
        # Extract date portion from filename (second part after first underscore)
        parts = csv_file.stem.split('_')
        if len(parts) >= 2:
            date_part = parts[1]
            if date_part.startswith(month_prefix):
                matching_files.append(csv_file)
    
    # Sort by filename for consistent archive ordering
    matching_files.sort(key=lambda p: p.name)
    
    return matching_files


def create_monthly_archive(
    files: List[Path],
    archive_dir: Path,
    year: int,
    month: int,
    dry_run: bool = False
) -> Optional[Path]:
    """
    Create compressed tar archive of files for specified month
    
    Archive naming: YYYY-MM.tar.gz
    """
    if not files:
        logger.info(f"No files found for {year}-{month:02d}")
        return None
    
    archive_name = f"{year}-{month:02d}.tar.gz"
    archive_path = archive_dir / archive_name
    
    if archive_path.exists():
        logger.warning(f"Archive already exists: {archive_path}")
        logger.warning("Skipping to avoid overwriting existing archive")
        return None
    
    total_size = sum(f.stat().st_size for f in files)
    total_size_mb = total_size / (1024 * 1024)
    
    logger.info(f"Creating archive: {archive_name}")
    logger.info(f"Files to archive: {len(files)}")
    logger.info(f"Total size before compression: {total_size_mb:.2f} MB")
    
    if dry_run:
        logger.info("[DRY RUN] Would create archive with following files:")
        for f in files[:10]:
            logger.info(f"  - {f.name}")
        if len(files) > 10:
            logger.info(f"  ... and {len(files) - 10} more files")
        return None
    
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with tarfile.open(archive_path, 'w:gz') as tar:
            for file_path in files:
                tar.add(file_path, arcname=file_path.name)
                logger.debug(f"Added to archive: {file_path.name}")
        
        archive_size = archive_path.stat().st_size
        archive_size_mb = archive_size / (1024 * 1024)
        compression_ratio = (1 - archive_size / total_size) * 100 if total_size > 0 else 0
        
        logger.info(f"Archive created: {archive_path}")
        logger.info(f"Archive size: {archive_size_mb:.2f} MB")
        logger.info(f"Compression ratio: {compression_ratio:.1f}%")
        
        return archive_path
        
    except Exception as e:
        logger.error(f"Failed to create archive: {e}")
        if archive_path.exists():
            archive_path.unlink()
        raise


def delete_archived_files(files: List[Path], dry_run: bool = False) -> int:
    """Delete files that have been archived"""
    if dry_run:
        logger.info(f"[DRY RUN] Would delete {len(files)} files")
        return 0
    
    deleted = 0
    for file_path in files:
        try:
            file_path.unlink()
            deleted += 1
            logger.debug(f"Deleted: {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to delete {file_path.name}: {e}")
    
    logger.info(f"Deleted {deleted} archived files")
    return deleted


def cleanup_old_archives(archive_dir: Path, retention_months: int = 24,
                         dry_run: bool = False) -> int:
    """
    Remove archives older than retention period
    
    Default: Keep 24 months (2 years) of archives
    """
    if retention_months <= 0:
        return 0
    
    cutoff_date = datetime.now() - timedelta(days=retention_months * 30)
    deleted = 0
    
    for archive_file in archive_dir.glob('*.tar.gz'):
        try:
            # Parse year-month from filename
            stem = archive_file.stem.replace('.tar', '')
            year, month = map(int, stem.split('-'))
            archive_date = datetime(year, month, 1)
            
            if archive_date < cutoff_date:
                if dry_run:
                    logger.info(f"[DRY RUN] Would delete old archive: {archive_file.name}")
                else:
                    archive_file.unlink()
                    logger.info(f"Deleted old archive: {archive_file.name}")
                deleted += 1
                
        except (ValueError, IndexError):
            logger.warning(f"Could not parse archive date from: {archive_file.name}")
            continue
    
    if deleted > 0:
        logger.info(f"Cleaned up {deleted} archives older than {retention_months} months")
    
    return deleted


def run_monthly_archive(
    processed_dir: Path,
    archive_dir: Path,
    year: Optional[int] = None,
    month: Optional[int] = None,
    dry_run: bool = False,
    delete_after_archive: bool = True,
    retention_months: int = 24
) -> dict:
    """
    Main archive function
    
    Args:
        processed_dir: Directory containing processed CSV files
        archive_dir: Directory for compressed archives
        year: Target year (default: previous month's year)
        month: Target month (default: previous month)
        dry_run: Preview without making changes
        delete_after_archive: Delete original files after archiving
        retention_months: How many months of archives to keep
        
    Returns:
        Summary dictionary with operation results
    """
    summary = {
        'year': year,
        'month': month,
        'files_found': 0,
        'archive_created': False,
        'archive_path': None,
        'files_deleted': 0,
        'old_archives_cleaned': 0,
        'status': 'unknown'
    }
    
    if year is None or month is None:
        year, month = get_previous_month()
    
    summary['year'] = year
    summary['month'] = month
    
    logger.info("=" * 60)
    logger.info("MONTHLY ARCHIVE PROCESS")
    logger.info("=" * 60)
    logger.info(f"Target month: {year}-{month:02d}")
    logger.info(f"Processed directory: {processed_dir}")
    logger.info(f"Archive directory: {archive_dir}")
    logger.info(f"Dry run: {dry_run}")
    
    if not processed_dir.exists():
        logger.error(f"Processed directory does not exist: {processed_dir}")
        summary['status'] = 'error'
        return summary
    
    files = find_files_for_month(processed_dir, year, month)
    summary['files_found'] = len(files)
    
    logger.info(f"Files found for {year}-{month:02d}: {len(files)}")
    
    if not files:
        summary['status'] = 'no_files'
        return summary
    
    archive_path = create_monthly_archive(files, archive_dir, year, month, dry_run)
    
    if archive_path:
        summary['archive_created'] = True
        summary['archive_path'] = str(archive_path)
        
        if delete_after_archive:
            deleted = delete_archived_files(files, dry_run)
            summary['files_deleted'] = deleted
    
    cleaned = cleanup_old_archives(archive_dir, retention_months, dry_run)
    summary['old_archives_cleaned'] = cleaned
    
    summary['status'] = 'success' if not dry_run else 'dry_run'
    
    logger.info("=" * 60)
    logger.info("ARCHIVE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Month archived: {year}-{month:02d}")
    logger.info(f"Files found: {summary['files_found']}")
    logger.info(f"Archive created: {summary['archive_created']}")
    logger.info(f"Files deleted: {summary['files_deleted']}")
    logger.info(f"Old archives cleaned: {summary['old_archives_cleaned']}")
    logger.info("=" * 60)
    
    return summary


def main() -> int:
    """Command line entry point"""
    parser = argparse.ArgumentParser(
        description='Archive processed SFTP files by month',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          Archive previous month
  %(prog)s --month 2024-12          Archive December 2024
  %(prog)s --dry-run                Preview without changes
  %(prog)s --no-delete              Archive but keep original files
        """
    )
    
    parser.add_argument(
        '--month',
        type=str,
        help='Month to archive in YYYY-MM format (default: previous month)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview actions without making changes'
    )
    
    parser.add_argument(
        '--no-delete',
        action='store_true',
        help='Keep original files after archiving'
    )
    
    parser.add_argument(
        '--processed-dir',
        type=str,
        default='/mnt/data/noggin/sftp/processed',
        help='Directory containing processed files'
    )
    
    parser.add_argument(
        '--archive-dir',
        type=str,
        default='/mnt/data/noggin/sftp/monthly_archives',
        help='Directory for compressed archives'
    )
    
    parser.add_argument(
        '--log-dir',
        type=str,
        default='/mnt/data/noggin/log',
        help='Directory for log files'
    )
    
    parser.add_argument(
        '--retention-months',
        type=int,
        default=24,
        help='Number of months of archives to retain (default: 24)'
    )
    
    args = parser.parse_args()
    
    setup_logging(Path(args.log_dir) if args.log_dir else None)
    
    year = None
    month = None
    
    if args.month:
        try:
            year, month = parse_month_arg(args.month)
        except ValueError as e:
            logger.error(str(e))
            return 1
    
    try:
        result = run_monthly_archive(
            processed_dir=Path(args.processed_dir),
            archive_dir=Path(args.archive_dir),
            year=year,
            month=month,
            dry_run=args.dry_run,
            delete_after_archive=not args.no_delete,
            retention_months=args.retention_months
        )
        
        if result['status'] in ('success', 'dry_run', 'no_files'):
            return 0
        else:
            return 1
            
    except Exception as e:
        logger.error(f"Archive failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
