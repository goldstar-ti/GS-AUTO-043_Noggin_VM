#!/usr/bin/env python3
"""
Noggin Continuous Processor

Runs noggin_processor.py in a continuous loop with configurable sleep intervals.
Includes CSV import and hash resolution cycles.
"""

from __future__ import annotations
import sys
import time
import signal
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, CSVImporter, HashManager
from sftp_download_tips import run_sftp_download

logger: logging.Logger = logging.getLogger(__name__)

shutdown_requested: bool = False


def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_requested = True


def run_single_processing_cycle(config: ConfigLoader, db_manager: DatabaseConnectionManager) -> Dict[str, int]:
    """
    Execute one processing cycle by running noggin_processor.py
    
    Args:
        config: ConfigLoader instance
        db_manager: DatabaseConnectionManager instance
        
    Returns:
        Dictionary with cycle status and duration
    """
    cycle_start = datetime.now()
    
    logger.info("=" * 80)
    logger.info(f"Starting processing cycle at {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    try:
        script_dir = Path(__file__).parent
        processor_script = script_dir / 'noggin_processor.py'
        
        if not processor_script.exists():
            logger.error(f"Processor script not found: {processor_script}")
            return {'status': 'error', 'duration_seconds': 0}
        
        result = subprocess.run(
            [sys.executable, str(processor_script)],
            cwd=str(script_dir),
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        cycle_end = datetime.now()
        duration = (cycle_end - cycle_start).total_seconds()
        
        if result.returncode == 0:
            logger.info(f"Processing cycle completed successfully in {duration:.1f} seconds")
            return {'status': 'success', 'duration_seconds': duration}
        else:
            logger.error(f"Processing cycle failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Error output: {result.stderr[:500]}")
            return {'status': 'failed', 'duration_seconds': duration}
            
    except subprocess.TimeoutExpired:
        logger.error("Processing cycle timed out after 3600 seconds")
        return {'status': 'timeout', 'duration_seconds': 3600}
    except Exception as e:
        logger.error(f"Processing cycle error: {e}", exc_info=True)
        return {'status': 'error', 'duration_seconds': 0}


def run_csv_import_cycle(config: ConfigLoader, db_manager: DatabaseConnectionManager) -> Dict[str, int]:
    """
    Execute CSV import cycle
    
    Args:
        config: ConfigLoader instance
        db_manager: DatabaseConnectionManager instance
        
    Returns:
        Dictionary with import statistics
    """
    logger.info("Starting CSV import cycle...")
    
    try:
        csv_importer = CSVImporter(config, db_manager)
        result = csv_importer.scan_and_import_csv_files()
        
        logger.info(f"CSV import cycle complete: {result['total_imported']} TIPs imported")
        return result
        
    except Exception as e:
        logger.error(f"CSV import cycle failed: {e}", exc_info=True)
        return {
            'files_processed': 0,
            'total_imported': 0,
            'total_duplicates': 0,
            'total_errors': 1
        }


def run_hash_resolution_cycle(config: ConfigLoader, db_manager: DatabaseConnectionManager) -> int:
    """
    Run automatic hash resolution cycle
    
    Resolves any unknown hashes that now have entries in hash_lookup table.
    
    Args:
        config: ConfigLoader instance
        db_manager: DatabaseConnectionManager instance
        
    Returns:
        Number of hashes resolved
    """
    logger.info("Starting hash resolution cycle...")
    
    try:
        hash_manager = HashManager(config, db_manager)
        resolved = hash_manager.auto_resolve_unknown_hashes()
        
        if resolved > 0:
            logger.info(f"Hash resolution cycle complete: {resolved} hashes resolved")
        else:
            logger.debug("Hash resolution cycle complete: no hashes needed resolution")
        
        return resolved
        
    except Exception as e:
        logger.error(f"Hash resolution cycle failed: {e}", exc_info=True)
        return 0


def get_processing_statistics(db_manager: DatabaseConnectionManager) -> Dict[str, int]:
    """
    Get current processing statistics from database
    
    Args:
        db_manager: DatabaseConnectionManager instance
        
    Returns:
        Dictionary with counts by processing_status
    """
    try:
        stats_query = """
            SELECT 
                processing_status,
                COUNT(*) as count
            FROM noggin_data
            GROUP BY processing_status
        """
        results = db_manager.execute_query_dict(stats_query)
        
        stats = {row['processing_status']: row['count'] for row in results}
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get processing statistics: {e}")
        return {}

def run_sftp_download_cycle(config, db_manager) -> dict:
    """
    Execute SFTP download cycle
    
    Args:
        config: ConfigLoader instance
        db_manager: DatabaseConnectionManager instance
        
    Returns:
        Dictionary with download statistics
    """
    from sftp_download_tips import run_sftp_download
    
    logger.info("Starting SFTP download cycle...")
    
    try:
        result = run_sftp_download(
            sftp_config_path='config/sftp_config.ini',
            base_config=config,
            db_manager=db_manager
        )
        
        if result['status'] == 'success':
            logger.info(
                f"SFTP download cycle complete: "
                f"{result['total_inserted']} TIPs inserted, "
                f"{result['total_duplicates']} duplicates skipped"
            )
        elif result['status'] == 'no_files':
            logger.info("SFTP download cycle complete: no new files on server")
        else:
            logger.warning(f"SFTP download cycle completed with status: {result['status']}")
        
        return result
        
    except Exception as e:
        logger.error(f"SFTP download cycle failed: {e}", exc_info=True)
        return {'status': 'error', 'total_inserted': 0, 'total_duplicates': 0, 'total_errors': 1}

def main() -> int:
    """Main entry point for continuous processor"""

    global shutdown_requested
    shutdown_requested = False

    def signal_handler(signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully"""
        nonlocal shutdown_requested
        logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        shutdown_requested = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        config = ConfigLoader(
            'config/base_config.ini',
            'config/load_compliance_check_driver_loader_config.ini'
        )
        
        logger_manager = LoggerManager(config, script_name='noggin_continuous_processor')
        logger_manager.configure_application_logger()
        
        cycle_sleep = config.getint('continuous', 'cycle_sleep_seconds')
        csv_import_frequency = config.getint('continuous', 'import_csv_every_n_cycles')
        sftp_download_frequency = config.getint('continuous', 'sftp_download_every_n_cycles', fallback=6)
        
        # New configuration for hash resolution
        hash_resolution_frequency = config.getint('continuous', 'resolve_hashes_every_n_cycles', fallback=10)
        
        logger.info("Noggin Continuous Processor started")
        logger.info(f"Configuration:")
        logger.info(f"  - Cycle sleep: {cycle_sleep} seconds")
        logger.info(f"  - CSV import frequency: every {csv_import_frequency} cycles")
        logger.info(f"  - Hash resolution frequency: every {hash_resolution_frequency} cycles")
        logger.info(f"  - SFTP download frequency: every {sftp_download_frequency} cycles")
        
        db_manager = DatabaseConnectionManager(config)
        
        cycle_count = 0
        total_processed = 0
        
        while not shutdown_requested:
            cycle_count += 1
            
            logger.info(f"\n{'='*80}")
            logger.info(f"CYCLE {cycle_count}")
            logger.info(f"{'='*80}")

            # Run SFTP download cycle (every N cycles)
            if cycle_count % sftp_download_frequency == 0:
                sftp_result = run_sftp_download_cycle(config, db_manager)
                # Optionally track statistics
                if sftp_result.get('total_inserted', 0) > 0:
                    logger.info(f"SFTP: Added {sftp_result['total_inserted']} new TIPs to queue")
            
            # Run CSV import cycle (every N cycles)
            if cycle_count % csv_import_frequency == 0:
                import_result = run_csv_import_cycle(config, db_manager)
                total_processed += import_result['total_imported']
            
            # Run hash resolution cycle (every N cycles)
            if cycle_count % hash_resolution_frequency == 0:
                resolved = run_hash_resolution_cycle(config, db_manager)
                if resolved > 0:
                    logger.info(f"Resolved {resolved} previously unknown hashes")

            
            # Run main processing cycle
            cycle_result = run_single_processing_cycle(config, db_manager)
            
            # Get current statistics
            stats = get_processing_statistics(db_manager)
            logger.info(f"\nCurrent Statistics:")
            for status, count in sorted(stats.items()):
                logger.info(f"  {status}: {count}")
            
            # Check for shutdown before sleeping
            if shutdown_requested:
                logger.info("Shutdown requested, exiting...")
                break
            
            logger.info(f"\nSleeping for {cycle_sleep} seconds...")
            
            # Sleep in 1-second intervals to allow responsive shutdown
            for _ in range(cycle_sleep):
                if shutdown_requested:
                    break
                time.sleep(1)
        
        logger.info("="*80)
        logger.info("Continuous processor shutdown complete")
        logger.info(f"Total cycles executed: {cycle_count}")
        logger.info(f"Total records processed: {total_processed}")
        logger.info("="*80)

        # Sleep before next cycle
        if not shutdown_requested:
            logger.info(f"Sleeping {cycle_sleep}s before next cycle...")
            import time
            time.sleep(cycle_sleep)        
            
        return 0
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        return 0
    except Exception as e:
        logger.error(f"Fatal error in continuous processor: {e}", exc_info=True)
        return 1
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()


if __name__ == "__main__":
    sys.exit(main())