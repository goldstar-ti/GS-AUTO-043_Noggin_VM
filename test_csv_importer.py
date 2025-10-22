from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, CSVImporter
import logging
from typing import Dict, Any

config: ConfigLoader = ConfigLoader(
    'config/base_config.ini',
    'config/load_compliance_check_config.ini'
)

logger_manager: LoggerManager = LoggerManager(config, script_name='test_csv_importer')
logger_manager.configure_application_logger()

logger: logging.Logger = logging.getLogger(__name__)

try:
    logger.info("Initialising CSV importer...")
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
    csv_importer: CSVImporter = CSVImporter(config, db_manager)
    
    logger.info("Scanning for CSV files in input folder...")
    summary: Dict[str, Any] = csv_importer.scan_and_import_csv_files()
    
    logger.info("CSV Import Summary:")
    logger.info(f"  Files processed: {summary['files_processed']}")
    logger.info(f"  TIPs imported: {summary['total_imported']}")
    logger.info(f"  Duplicates: {summary['total_duplicates']}")
    logger.info(f"  Errors: {summary['total_errors']}")
    
    print(f"\n✓ CSV Import Summary:")
    print(f"  Files processed: {summary['files_processed']}")
    print(f"  TIPs imported: {summary['total_imported']}")
    print(f"  Duplicates: {summary['total_duplicates']}")
    print(f"  Errors: {summary['total_errors']}")
    
except Exception as e:
    logger.error(f"Test failed: {e}", exc_info=True)
    print(f"✗ Error: {e}")
finally:
    if 'db_manager' in locals():
        db_manager.close_all()