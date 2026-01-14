from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, CSVImporter
import logging
from typing import Dict, Any
import sys
from datetime import datetime

config: ConfigLoader = ConfigLoader('config/base_config.ini')

logger_manager: LoggerManager = LoggerManager(config, script_name='import_csv_tips')
logger_manager.configure_application_logger()

logger: logging.Logger = logging.getLogger(__name__)

try:
    logger.info("Initialising CSV importer (Manual Mode)...")
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)

    # --- TRUNCATION PROMPT START ---
    print("\n" + "="*100)
    print(" DATABASE CLEANUP OPTIONS")
    print("="*60)
    print("Tables to be truncated:")
    print(" - noggin_schema.noggin_data")
    print(" - noggin_schema.attachments")
    print(" - noggin_schema.processing_errors")
    print(" - noggin_schema.session_log")
    print(" - noggin_schema.unknown_hashes")
    print("-" * 100)
    
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
   
    csv_files = sorted(list(csv_importer.input_folder.glob('*.csv')))

    if csv_files:
        file_details = []
        for f in csv_files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') # modification time
            
            header_preview = "<Unable to read>"
            bom_warning = ""
            
            try:
                # Read as standard UTF-8 so we can SEE the BOM
                with open(f, 'r', encoding='utf-8') as f_obj:
                    raw_line = f_obj.readline()
                    
                    if raw_line.startswith('\ufeff'):
                        bom_warning = "    [!] WARNING: BOM (Byte Order Mark) Detected\n"
                        # Strip it for the display so the header text is clean
                        header_preview = raw_line.lstrip('\ufeff').strip()
                    else:
                        header_preview = raw_line.strip()
                        
                    if not header_preview:
                        header_preview = "<Empty File>"
                        
            except Exception as e:
                header_preview = f"<Error: {e}>"

            # Format the entry
            file_details.append(f"  - File:     {f.name}\n    Modified: {mtime}\n{bom_warning}    Header:   {header_preview}")
            
        files_formatted = "\n\n".join(file_details)
        logger.info(f"Found {len(csv_files)} CSV files to process:\n{files_formatted}")
    else:
        else:
            logger.info(f"No CSV files found in: {csv_importer.input_folder}")
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
    logger.error(f"Import failed: {e}", exc_info=True)
    print(f"✗ Error: {e}")
finally:
    if 'db_manager' in locals():
        db_manager.close_all()