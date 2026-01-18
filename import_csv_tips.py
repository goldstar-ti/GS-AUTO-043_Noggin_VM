import argparse
import logging
import sys
from datetime import datetime
from typing import Dict, Any

from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, CSVImporter

config: ConfigLoader = ConfigLoader('config/base_config.ini')

logger_manager: LoggerManager = LoggerManager(config, script_name='import_csv_tips')
logger_manager.configure_application_logger()

logger: logging.Logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Import or update TIP records from Noggin CSV exports'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Update mode: fill in missing expected_inspection_id and expected_inspection_date '
             'for existing records. Skips records with processing_status=complete. '
             'Inserts new TIPs not found in database.'
    )
    return parser.parse_args()


def prompt_truncation(db_manager: DatabaseConnectionManager) -> bool:
    """Prompt user for table truncation. Returns True if truncation succeeded or was skipped."""
    print("\n" + "="*100)
    print(" DATABASE CLEANUP OPTIONS")
    print("="*100)
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
            tables = [
                'noggin_data',
                'attachments',
                'processing_errors',
                'session_log',
                'unknown_hashes'
            ]
            fq_tables = [f"noggin_schema.{t}" for t in tables]
            query = f"TRUNCATE TABLE {', '.join(fq_tables)} CASCADE;"

            db_manager.execute_update(query)
            logger.info("Truncation complete.")
            print("[OK] All specified tables have been truncated.")
        except Exception as e:
            logger.error(f"Truncation failed: {e}")
            print(f"[FAILED] Could not truncate tables. Error: {e}")
            return False
    else:
        print("... Skipping truncation. Appending to existing data.")

    print("="*100 + "\n")
    return True


def preview_csv_files(csv_importer: CSVImporter) -> None:
    """Preview CSV files in input folder"""
    csv_files = sorted(list(csv_importer.input_folder.glob('*.csv')))

    if csv_files:
        file_details = []
        for f in csv_files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')

            header_preview = "<Unable to read>"
            bom_warning = ""

            try:
                with open(f, 'r', encoding='utf-8') as f_obj:
                    raw_line = f_obj.readline()

                    if raw_line.startswith('\ufeff'):
                        bom_warning = "    [!] WARNING: BOM (Byte Order Mark) Detected\n"
                        header_preview = raw_line.lstrip('\ufeff').strip()
                    else:
                        header_preview = raw_line.strip()

                    if not header_preview:
                        header_preview = "<Empty File>"

            except Exception as e:
                header_preview = f"<Error: {e}>"

            file_details.append(
                f"  - File:     {f.name}\n"
                f"    Modified: {mtime}\n"
                f"{bom_warning}"
                f"    Header:   {header_preview}"
            )

        files_formatted = "\n\n".join(file_details)
        logger.info(f"Found {len(csv_files)} CSV files to process:\n{files_formatted}")
    else:
        logger.info(f"No CSV files found in: {csv_importer.input_folder}")

    print("\n")


def run_import(csv_importer: CSVImporter) -> None:
    """Run standard import mode"""
    logger.info("Scanning for CSV files in input folder...")
    summary: Dict[str, Any] = csv_importer.scan_and_import()

    logger.info("CSV Import Summary:")
    logger.info(f"  Files processed: {summary['files_processed']}")
    logger.info(f"  TIPs imported:   {summary['total_imported']}")
    logger.info(f"  Duplicates:      {summary['total_duplicates']}")
    logger.info(f"  Errors:          {summary['total_errors']}")

    print(f"\n[OK] CSV Import Summary:")
    print(f"  Files processed: {summary['files_processed']}")
    print(f"  TIPs imported:   {summary['total_imported']}")
    print(f"  Duplicates:      {summary['total_duplicates']}")
    print(f"  Errors:          {summary['total_errors']}")
    print()


def run_update(csv_importer: CSVImporter) -> None:
    """Run update mode - fill missing fields only"""
    logger.info("Scanning for CSV files in input folder (update mode)...")
    summary: Dict[str, Any] = csv_importer.scan_and_update()

    logger.info("CSV Update Summary:")
    logger.info(f"  Files processed:       {summary['files_processed']}")
    logger.info(f"  Records updated:       {summary['total_updated']}")
    logger.info(f"  New TIPs inserted:     {summary['total_inserted']}")
    logger.info(f"  Skipped (complete):    {summary['total_skipped_complete']}")
    logger.info(f"  Skipped (no change):   {summary['total_skipped_no_change']}")
    logger.info(f"  Errors:                {summary['total_errors']}")

    print(f"\n[OK] CSV Update Summary:")
    print(f"  Files processed:       {summary['files_processed']}")
    print(f"  Records updated:       {summary['total_updated']}")
    print(f"  New TIPs inserted:     {summary['total_inserted']}")
    print(f"  Skipped (complete):    {summary['total_skipped_complete']}")
    print(f"  Skipped (no change):   {summary['total_skipped_no_change']}")
    print(f"  Errors:                {summary['total_errors']}")
    print()


def main() -> None:
    args = parse_args()

    try:
        if args.update:
            logger.info("Initialising CSV importer (Update Mode)...")
            print("\n" + "="*100)
            print(" UPDATE MODE")
            print("="*100)
            print("This mode will:")
            print(" - Fill in NULL expected_inspection_id and expected_inspection_date columns")
            print(" - Skip records with processing_status = 'complete'")
            print(" - Insert new TIPs not found in database")
            print("="*100 + "\n")
        else:
            logger.info("Initialising CSV importer (Manual Mode)...")

        db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)

        # Only prompt for truncation in import mode (not update mode)
        if not args.update:
            if not prompt_truncation(db_manager):
                sys.exit(1)

        csv_importer: CSVImporter = CSVImporter(config, db_manager)

        logger.info(f"Input folder path: {csv_importer.input_folder}")
        logger.info(f"Input folder exists: {csv_importer.input_folder.exists()}")

        preview_csv_files(csv_importer)

        if args.update:
            run_update(csv_importer)
        else:
            run_import(csv_importer)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        print(f"[ERROR] {e}")
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()


if __name__ == '__main__':
    main()