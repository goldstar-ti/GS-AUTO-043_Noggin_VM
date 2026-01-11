import logging
import sys
import os
from pathlib import Path

# Add the current directory to path so we can import 'common' if running directly
sys.path.append(str(Path(__file__).parent.parent))

try:
    from common.logger import LoggerManager
except ImportError:
    # Fallback if testing locally without the package structure
    from logger import LoggerManager

class MaintenanceConfig:
    """
    Simple config wrapper to match ConfigLoader interface.
    Hardcodes paths based on your environment logs.
    """
    def get(self, section, key, fallback=None):
        if key == 'base_log_path':
            return '/mnt/data/noggin/log'
        if key == 'log_filename_pattern':
            return 'maintenance_{date}.log'
        return fallback

    def getint(self, section, key, fallback=None):
        if key == 'log_retention_days':
            return 30
        return fallback

def run_maintenance():
    """
    Runs daily log maintenance:
    1. Compresses logs older than 7 days.
    2. Deletes logs older than 30 days.
    """
    try:
        config = MaintenanceConfig()
        
        # Initialize manager
        manager = LoggerManager(config, script_name='maintenance')
        manager.configure_application_logger()
        
        logger = logging.getLogger("maintenance")
        logger.info("Starting log maintenance task...")
        
        # 1. Compress logs older than 7 days
        compressed = manager.compress_old_logs(days_before_compress=7)
        
        # 2. Delete logs older than 30 days
        cleaned = manager.cleanup_old_logs(days_to_keep=30)
        
        logger.info(f"Maintenance complete. Files Compressed: {compressed}, Files Deleted: {cleaned}")
        
    except Exception as e:
        # Fallback print if logger fails
        print(f"CRITICAL: Maintenance script failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_maintenance()