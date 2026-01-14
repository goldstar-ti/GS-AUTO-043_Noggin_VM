from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, CSVImporter
from common import UNKNOWN_TEXT
import logging
from typing import Dict, Any
import sys

config: ConfigLoader = ConfigLoader(
    'config/base_config.ini',
    'config/load_compliance_check_driver_loader_config.ini'
)

logger_manager: LoggerManager = LoggerManager(config, script_name='test_csv_importer')
logger_manager.configure_application_logger()

logger: logging.Logger = logging.getLogger(__name__)

try:
    logger.info("Initialising CSV importer...")
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)

    print("\n" + "="*60)
    print(" DATABASE CLEANUP OPTIONS")
    print("="*60)
    print("Tables to be truncated:")
    print(" - noggin_schema.noggin_data")
    print(" - noggin_schema.attachments")
    print(" - noggin_schema.processing_errors")
    print(" - noggin_schema.session_log")
    print(" - noggin_schema.unknown_hashes")
    print("-" * 60)
    
    user_response = input(">>> Do you want to TRUNCATE these tables before importing? (y/n): ").strip().lower()
    
    if user_response == 'y':
        logger.warning("User requested table truncation...")
        try:
            # Construct the query with all tables
            tables = [
                'noggin_data',
                'attachments',
                'processing_errors',
                'session_log',
                'unknown_hashes'
            ]
            # Add schema prefix
            fq_tables = [f"noggin_schema.{t}" for t in tables]
            
            # TRUNCATE ... CASCADE handles foreign keys; RESTART IDENTITY resets ID counters
            query = f"TRUNCATE TABLE {', '.join(fq_tables)} CASCADE;"
            
            db_manager.execute_update(query)
            logger.info("Truncation complete.")
            print("✓ SUCCESS: All specified tables have been truncated.")
        except Exception as e:
            logger.error(f"Truncation failed: {e}")
            print(f"✗ FAILED: Could not truncate tables. Error: {e}")
            sys.exit(1)
    else:
        print("... Skipping truncation. Appending to existing data.")
    print("="*60 + "\n")
    # --- TRUNCATION PROMPT END ---

    csv_importer: CSVImporter = CSVImporter(config, db_manager)

    logger.info(f"Input folder path: {csv_importer.input_folder}")
    logger.info(f"Input folder exists: {csv_importer.input_folder.exists()}")
   
    csv_files = list(csv_importer.input_folder.glob('*.csv'))
    logger.info(f"CSV files found: {csv_files}")

    print("\n")
    
    logger.info("Scanning for CSV files in input folder...")
    summary: Dict[str, Any] = csv_importer.scan_and_import()
    
    logger.info("CSV Import Summary:")
    logger.info(f"  Files processed: {summary['files_processed']}")
    logger.info(f"  TIPs imported:   {summary['total_imported']}")
    logger.info(f"  Duplicates:      {summary['total_duplicates']}")
    logger.info(f"  Errors:          {summary['total_errors']}")
    
    print(f"\n✓ CSV Import Summary:")
    print(f"  Files processed: {summary['files_processed']}")
    print(f"  TIPs imported:   {summary['total_imported']}")
    print(f"  Duplicates:      {summary['total_duplicates']}")
    print(f"  Errors:          {summary['total_errors']}")
    print()
    
except KeyboardInterrupt:
    print("\nOperation cancelled by user.")
except Exception as e:
    logger.error(f"Test failed: {e}", exc_info=True)
    print(f"✗ Error: {e}")
finally:
    if 'db_manager' in locals():
        db_manager.close_all()