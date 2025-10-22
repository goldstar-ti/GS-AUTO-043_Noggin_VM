from __future__ import annotations
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import signal
import sys

from common import (
    ConfigLoader, 
    LoggerManager, 
    DatabaseConnectionManager, 
    HashManager, 
    CircuitBreaker,
    CSVImporter
)

logger: logging.Logger = logging.getLogger(__name__)

shutdown_requested: bool = False


class ContinuousProcessorShutdownHandler:
    """Handles graceful shutdown for continuous processor"""
    
    def __init__(self, logger_instance: logging.Logger) -> None:
        self.logger: logging.Logger = logger_instance
        self.shutdown_requested: bool = False
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Continuous processor shutdown handler initialised")
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        global shutdown_requested
        signal_name: str = "SIGINT (Ctrl+C)" if signum == signal.SIGINT else f"Signal {signum}"
        
        if not self.shutdown_requested:
            self.shutdown_requested = True
            shutdown_requested = True
            print()
            self.logger.warning(f"\n{signal_name} received. Finishing current cycle then shutting down...")
            print()
            self.logger.warning("Press Ctrl+C again to force immediate exit")
        else:
            self.logger.error("Second shutdown signal - forcing immediate exit")
            sys.exit(1)
    
    def should_continue(self) -> bool:
        return not self.shutdown_requested


def run_single_processing_cycle(config: ConfigLoader, db_manager: DatabaseConnectionManager) -> Dict[str, int]:
    """
    Run a single processing cycle
    
    Returns:
        Dictionary with processing statistics
    """
    import subprocess
    
    logger.info("="*80)
    logger.info("Starting processing cycle")
    logger.info("="*80)
    
    cycle_start_time: float = time.perf_counter()
    
    try:
        result = subprocess.run(
            ['python', 'noggin_processor.py'],
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        cycle_duration: float = time.perf_counter() - cycle_start_time
        
        if result.returncode == 0:
            logger.info(f"Processing cycle completed successfully in {cycle_duration:.1f}s")
            return {'status': 'success', 'duration': cycle_duration}
        else:
            logger.error(f"Processing cycle failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return {'status': 'failed', 'duration': cycle_duration}
    
    except subprocess.TimeoutExpired:
        logger.error("Processing cycle timed out after 3600s")
        return {'status': 'timeout', 'duration': 3600}
    
    except Exception as e:
        logger.error(f"Error running processing cycle: {e}", exc_info=True)
        return {'status': 'error', 'duration': 0}


def get_processing_statistics(db_manager: DatabaseConnectionManager) -> Dict[str, int]:
    """Get current processing statistics from database"""
    query: str = """
        SELECT 
            processing_status,
            COUNT(*) as count
        FROM noggin_data
        GROUP BY processing_status
    """
    
    results = db_manager.execute_query_dict(query)
    
    stats: Dict[str, int] = {}
    for row in results:
        stats[row['processing_status']] = row['count']
    
    return stats


def log_cycle_summary(cycle_num: int, stats: Dict[str, int], cycle_result: Dict[str, Any]) -> None:
    """Log summary of processing cycle"""
    logger.info("="*80)
    logger.info(f"CYCLE {cycle_num} SUMMARY")
    logger.info("="*80)
    logger.info(f"Status: {cycle_result.get('status', 'unknown')}")
    logger.info(f"Duration: {cycle_result.get('duration', 0):.1f}s")
    logger.info("")
    logger.info("Database Statistics:")
    logger.info(f"  Complete:          {stats.get('complete', 0):,}")
    logger.info(f"  Pending:           {stats.get('pending', 0):,}")
    logger.info(f"  Failed:            {stats.get('failed', 0):,}")
    logger.info(f"  Partial:           {stats.get('partial', 0):,}")
    logger.info(f"  Interrupted:       {stats.get('interrupted', 0):,}")
    logger.info(f"  API Failed:        {stats.get('api_failed', 0):,}")
    logger.info(f"  Permanently Failed: {stats.get('permanently_failed', 0):,}")
    logger.info("="*80)


def main() -> int:
    """Main continuous processing loop"""
    global shutdown_requested
    
    config: ConfigLoader = ConfigLoader(
        'config/base_config.ini',
        'config/load_compliance_check_config.ini'
    )
    
    logger_manager: LoggerManager = LoggerManager(config, script_name='noggin_continuous_processor')
    logger_manager.configure_application_logger()
    
    logger.info("="*80)
    logger.info("NOGGIN CONTINUOUS PROCESSOR")
    logger.info("="*80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)
    
    shutdown_handler: ContinuousProcessorShutdownHandler = ContinuousProcessorShutdownHandler(logger)
    
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
    csv_importer: CSVImporter = CSVImporter(config, db_manager)
    
    cycle_sleep_seconds: int = config.getint('continuous', 'cycle_sleep_seconds')
    import_csv_every_n_cycles: int = config.getint('continuous', 'import_csv_every_n_cycles')
    
    logger.info(f"Cycle sleep time: {cycle_sleep_seconds}s")
    logger.info(f"CSV import frequency: every {import_csv_every_n_cycles} cycles")
    
    cycle_count: int = 0
    
    try:
        while shutdown_handler.should_continue():
            cycle_count += 1
            cycle_start_time: float = time.perf_counter()
            
            logger.info(f"\n{'='*80}")
            logger.info(f"CYCLE {cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*80}\n")
            
            if cycle_count % import_csv_every_n_cycles == 0:
                logger.info("Scanning for new CSV files...")
                try:
                    csv_summary: Dict[str, Any] = csv_importer.scan_and_import_csv_files()
                    if csv_summary['files_processed'] > 0:
                        logger.info(f"Imported {csv_summary['total_imported']} new TIPs from "
                                   f"{csv_summary['files_processed']} CSV file(s)")
                except Exception as e:
                    logger.error(f"CSV import failed: {e}", exc_info=True)
            
            cycle_result: Dict[str, Any] = run_single_processing_cycle(config, db_manager)
            
            stats: Dict[str, int] = get_processing_statistics(db_manager)
            log_cycle_summary(cycle_count, stats, cycle_result)
            
            pending_count: int = stats.get('pending', 0)
            failed_count: int = stats.get('failed', 0)
            partial_count: int = stats.get('partial', 0)
            interrupted_count: int = stats.get('interrupted', 0)
            api_failed_count: int = stats.get('api_failed', 0)
            
            work_remaining: int = pending_count + failed_count + partial_count + interrupted_count + api_failed_count
            
            if work_remaining == 0:
                logger.info("No work remaining. Waiting for new CSVs...")
            else:
                logger.info(f"{work_remaining:,} TIPs require processing")
            
            if shutdown_handler.should_continue():
                logger.info(f"Sleeping {cycle_sleep_seconds}s before next cycle...")
                time.sleep(cycle_sleep_seconds)
        
        logger.info("\nShutdown signal received. Exiting gracefully...")
        return 0
    
    except KeyboardInterrupt:
        logger.warning("\nForced shutdown via KeyboardInterrupt")
        return 1
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1
    
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()
        
        logger.info("="*80)
        logger.info(f"CONTINUOUS PROCESSOR STOPPED")
        logger.info(f"Total cycles completed: {cycle_count}")
        logger.info(f"Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)


if __name__ == "__main__":
    sys.exit(main())