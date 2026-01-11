"""
Noggin Continuous Processor (Modular Version)

Runs all object type processors in a round-robin fashion with configurable intervals.
Includes CSV import, hash resolution, and SFTP download cycles.

Uses the new modular processors package instead of subprocess calls.
"""

from __future__ import annotations
import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, CSVImporter, HashManager
from common.object_types import get_all_object_types, load_object_types

logger: logging.Logger = logging.getLogger(__name__)

shutdown_requested: bool = False


def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_requested = True


# Map abbreviations to config files
OBJECT_TYPE_CONFIGS = {
    'LCD': 'config/load_compliance_check_driver_loader_config.ini',
    'LCS': 'config/load_compliance_check_supervisor_manager_config.ini',
    'CCC': 'config/coupling_compliance_check_config.ini',
    'FPI': 'config/forklift_prestart_inspection_config.ini',
    'SO': 'config/site_observations_config.ini',
    'TA': 'config/trailer_audits_config.ini',
}


class ContinuousProcessor:
    """Manages continuous processing of all object types"""
    
    def __init__(self, base_config_path: str = 'config/base_config.ini') -> None:
        self.base_config_path = base_config_path
        
        self.config = ConfigLoader(base_config_path)
        
        self.logger_manager = LoggerManager(self.config, script_name='noggin_continuous')
        self.logger_manager.configure_application_logger()
        
        self.db_manager = DatabaseConnectionManager(self.config)
        
        self.hash_manager = HashManager(self.config, self.db_manager)
        
        self.sleep_interval = self.config.getint('continuous', 'sleep_between_cycles', fallback=60)
        self.tips_per_type = self.config.getint('continuous', 'tips_per_type_per_cycle', fallback=10)
        self.csv_import_frequency = self.config.getint('continuous', 'csv_import_every_n_cycles', fallback=5)
        self.sftp_download_frequency = self.config.getint('continuous', 'sftp_download_every_n_cycles', fallback=6)
        self.sftp_enabled = self.config.getboolean('sftp', 'enabled', fallback=False)
        
        self.enabled_types = self._get_enabled_types()
        
        self.cycle_count = 0
        self.stats: Dict[str, Dict[str, int]] = {
            abbrev: {'processed': 0, 'errors': 0}
            for abbrev in self.enabled_types
        }
        
        logger.info(f"ContinuousProcessor initialised with {len(self.enabled_types)} object types")
        logger.info(f"Enabled types: {', '.join(self.enabled_types)}")
    
    def _get_enabled_types(self) -> List[str]:
        """Get list of enabled object types from config or defaults"""
        enabled_str = self.config.get('continuous', 'enabled_object_types', fallback='')
        
        if enabled_str:
            return [t.strip().upper() for t in enabled_str.split(',') if t.strip()]
        
        enabled = []
        for abbrev, config_path in OBJECT_TYPE_CONFIGS.items():
            if Path(config_path).exists():
                enabled.append(abbrev)
        
        return enabled
    
    def run(self) -> None:
        """Main continuous processing loop"""
        global shutdown_requested
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("=" * 80)
        logger.info("NOGGIN CONTINUOUS PROCESSOR STARTED")
        logger.info(f"Sleep interval: {self.sleep_interval} seconds")
        logger.info(f"TIPs per type per cycle: {self.tips_per_type}")
        logger.info(f"CSV import every {self.csv_import_frequency} cycles")
        if self.sftp_enabled:
            logger.info(f"SFTP download every {self.sftp_download_frequency} cycles")
        logger.info("=" * 80)
        
        while not shutdown_requested:
            try:
                self.cycle_count += 1
                cycle_start = datetime.now()
                
                logger.info(f"\n{'='*60}")
                logger.info(f"CYCLE {self.cycle_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*60}")
                
                if self.sftp_enabled and self.cycle_count % self.sftp_download_frequency == 0:
                    self._run_sftp_download()
                
                if self.cycle_count % self.csv_import_frequency == 0:
                    self._run_csv_import()
                
                for abbrev in self.enabled_types:
                    if shutdown_requested:
                        break
                    
                    self._process_object_type(abbrev)
                
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                logger.info(f"Cycle {self.cycle_count} completed in {cycle_duration:.1f} seconds")
                
                if not shutdown_requested:
                    logger.info(f"Sleeping {self.sleep_interval} seconds before next cycle...")
                    self._interruptible_sleep(self.sleep_interval)
                
            except Exception as e:
                logger.error(f"Error in cycle {self.cycle_count}: {e}", exc_info=True)
                if not shutdown_requested:
                    self._interruptible_sleep(30)
        
        self._log_final_summary()
    
    def _process_object_type(self, abbrev: str) -> int:
        """
        Process TIPs for a single object type
        
        Returns:
            Number of TIPs processed
        """
        config_path = OBJECT_TYPE_CONFIGS.get(abbrev)
        
        if not config_path or not Path(config_path).exists():
            logger.warning(f"Config not found for {abbrev}: {config_path}")
            return 0
        
        try:
            from processors import ObjectProcessor
            
            processor = ObjectProcessor(
                base_config_path=self.base_config_path,
                specific_config_path=config_path
            )
            
            processed = processor.run(
                from_database=True,
                batch_size=self.tips_per_type
            )
            
            self.stats[abbrev]['processed'] += processed
            
            if processed > 0:
                logger.info(f"{abbrev}: Processed {processed} TIPs")
            else:
                logger.debug(f"{abbrev}: No TIPs to process")
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing {abbrev}: {e}", exc_info=True)
            self.stats[abbrev]['errors'] += 1
            return 0
    
    def _run_csv_import(self) -> None:
        """Run CSV import for all object types"""
        logger.info("Running CSV import cycle...")
        
        try:
            csv_importer = CSVImporter(self.config, self.db_manager)
            
            summary = csv_importer.scan_and_import()
            
            if summary['files_processed'] > 0:
                logger.info(
                    f"CSV import: {summary['files_processed']} files, "
                    f"{summary['total_imported']} imported, "
                    f"{summary['total_duplicates']} duplicates"
                )
            
        except Exception as e:
            logger.error(f"CSV import cycle failed: {e}", exc_info=True)
    
    def _run_sftp_download(self) -> None:
        """Run SFTP download cycle"""
        logger.info("Running SFTP download cycle...")
        
        try:
            sftp_script = Path(__file__).parent / 'sftp_download_tips.py'
            
            if not sftp_script.exists():
                logger.warning(f"SFTP script not found: {sftp_script}")
                return
            
            import subprocess
            
            result = subprocess.run(
                [sys.executable, str(sftp_script)],
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                logger.info("SFTP download completed successfully")
            else:
                logger.error(f"SFTP download failed: {result.stderr[:500] if result.stderr else 'No error output'}")
                
        except subprocess.TimeoutExpired:
            logger.error("SFTP download timed out after 600 seconds")
        except Exception as e:
            logger.error(f"SFTP download failed: {e}", exc_info=True)
    
    def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep that can be interrupted by shutdown signal"""
        global shutdown_requested
        
        for _ in range(seconds):
            if shutdown_requested:
                return
            time.sleep(1)
    
    def _log_final_summary(self) -> None:
        """Log final processing summary"""
        logger.info("\n" + "=" * 80)
        logger.info("CONTINUOUS PROCESSOR SHUTDOWN")
        logger.info("=" * 80)
        logger.info(f"Total cycles completed: {self.cycle_count}")
        logger.info("")
        logger.info("Processing summary by object type:")
        
        total_processed = 0
        total_errors = 0
        
        for abbrev, stats in self.stats.items():
            logger.info(f"  {abbrev}: {stats['processed']} processed, {stats['errors']} errors")
            total_processed += stats['processed']
            total_errors += stats['errors']
        
        logger.info("")
        logger.info(f"Total TIPs processed: {total_processed}")
        logger.info(f"Total errors: {total_errors}")
        logger.info("=" * 80)
        
        try:
            self.db_manager.close_all()
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")


def main() -> int:
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Noggin Continuous Processor (Modular Version)'
    )
    parser.add_argument(
        '--config',
        default='config/base_config.ini',
        help='Path to base config file'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run one cycle and exit'
    )
    
    args = parser.parse_args()
    
    try:
        processor = ContinuousProcessor(args.config)
        
        if args.once:
            processor.cycle_count = 1
            for abbrev in processor.enabled_types:
                processor._process_object_type(abbrev)
            processor._log_final_summary()
        else:
            processor.run()
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
