from __future__ import annotations
import logging
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List

logger: logging.Logger = logging.getLogger(__name__)


class CSVImportError(Exception):
    """Raised when CSV import operations fail"""
    pass


class CSVImporter:
    """Imports TIP IDs from CSV files into PostgreSQL database"""
    
    def __init__(self, config: 'ConfigLoader', db_manager: 'DatabaseConnectionManager') -> None:
        """
        Initialise CSV importer
        
        Args:
            config: ConfigLoader instance
            db_manager: DatabaseConnectionManager instance
        """
        self.config: 'ConfigLoader' = config
        self.db_manager: 'DatabaseConnectionManager' = db_manager
        
        self.input_folder: Path = Path(config.get('paths', 'input_folder_path'))
        self.processed_folder: Path = Path(config.get('paths', 'processed_folder_path'))
        self.error_folder: Path = Path(config.get('paths', 'error_folder_path'))
        
        self.input_folder.mkdir(parents=True, exist_ok=True)
        self.processed_folder.mkdir(parents=True, exist_ok=True)
        self.error_folder.mkdir(parents=True, exist_ok=True
    
    def detect_object_type(self, headers: List[str]) -> Optional[str]:
        """
        Detect object type from CSV column headers
        
        Args:
            headers: List of column headers
            
        Returns:
            Object type string or None if cannot detect
        """
        headers_lower: List[str] = [h.lower().strip() for h in headers]
        
        if 'lcdinspectionid' in headers_lower:
            return 'Driver 360'
        elif 'couplingid' in headers_lower:
            return 'Coupling Compliance Check'
        elif 'trailerauditid' in headers_lower:
            return 'Trailer Audit'
        
        logger.warning(f"Could not detect object type from headers: {headers}")
        return None
    
    def import_csv_file(self, csv_file_path: Path) -> Tuple[int, int, int]:
        """
        Import TIPs from CSV file into database
        
        Args:
            csv_file_path: Path to CSV file
            
        Returns:
            Tuple of (imported_count, duplicate_count, error_count)
        """
        if not csv_file_path.exists():
            raise CSVImportError(f"CSV file not found: {csv_file_path}")
        
        logger.info(f"Importing TIPs from {csv_file_path.name}")
        
        imported_count: int = 0
        duplicate_count: int = 0
        error_count: int = 0
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers: List[str] = next(reader)
                
                if not headers or len(headers) == 0:
                    raise CSVImportError("CSV file has no headers")
                
                tip_column_index: int = 0
                logger.info(f"CSV headers: {headers}")
                logger.info(f"TIP column at index {tip_column_index} (first column)")
                
                object_type: Optional[str] = self.detect_object_type(headers)
                if not object_type:
                    raise CSVImportError(f"Could not detect object type from CSV headers: {headers}")
                
                logger.info(f"Detected object type: {object_type}")
                
                for row_num, row in enumerate(reader, start=2):
                    if not row or len(row) == 0:
                        continue
                    
                    if len(row) <= tip_column_index:
                        logger.warning(f"Row {row_num}: insufficient columns")
                        error_count += 1
                        continue
                    
                    tip_value: str = row[tip_column_index].strip()
                    if not tip_value:
                        continue
                    
                    existing: List[Dict[str, Any]] = self.db_manager.execute_query_dict(
                        "SELECT tip FROM noggin_data WHERE tip = %s",
                        (tip_value,)
                    )
                    
                    if existing:
                        logger.info(f"TIP {tip_value} already exists - skipping")
                        duplicate_count += 1
                        continue
                    
                    try:
                        self.db_manager.execute_update(
                            """
                            INSERT INTO noggin_data (tip, object_type, processing_status, csv_imported_at)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (tip_value, object_type, 'pending', datetime.now())
                        )
                        imported_count += 1
                        logger.debug(f"Imported TIP: {tip_value}")
                    except Exception as e:
                        logger.error(f"Failed to import TIP {tip_value}: {e}")
                        error_count += 1
            
            logger.info(f"Import complete: {imported_count} imported, {duplicate_count} duplicates, {error_count} errors")
            return imported_count, duplicate_count, error_count
        
        except Exception as e:
            logger.error(f"CSV import failed: {e}", exc_info=True)
            raise CSVImportError(f"Import failed: {e}")
    
    def move_csv_file(self, csv_file_path: Path, success: bool) -> Path:
        """
        Move CSV file to processed or error folder
        
        Args:
            csv_file_path: Path to CSV file
            success: True if import succeeded, False if failed
            
        Returns:
            New path where file was moved
        """
        timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename: str = f"{csv_file_path.stem}_{timestamp}{csv_file_path.suffix}"
        
        if success:
            destination: Path = self.processed_folder / new_filename
            logger.info(f"Moving {csv_file_path.name} to processed folder")
        else:
            destination = self.error_folder / new_filename
            logger.warning(f"Moving {csv_file_path.name} to error folder")
        
        try:
            csv_file_path.rename(destination)
            logger.info(f"File moved to: {destination}")
            return destination
        except Exception as e:
            logger.error(f"Failed to move file: {e}")
            raise CSVImportError(f"Failed to move file: {e}")
    
    def scan_and_import_csv_files(self) -> Dict[str, Any]:
        """
        Scan input folder and import all CSV files
        
        Returns:
            Dictionary with import statistics
        """
        csv_pattern: str = self.config.get('input', 'csv_filename_pattern', fallback='*.csv')
        csv_files: List[Path] = list(self.input_folder.glob(csv_pattern))
        
        if not csv_files:
            logger.debug(f"No CSV files found in {self.input_folder}")
            return {
                'files_processed': 0,
                'total_imported': 0,
                'total_duplicates': 0,
                'total_errors': 0
            }
        
        logger.info(f"Found {len(csv_files)} CSV file(s) to process")
        
        total_imported: int = 0
        total_duplicates: int = 0
        total_errors: int = 0
        files_processed: int = 0
        
        for csv_file in csv_files:
            logger.info(f"Processing CSV file: {csv_file.name}")
            
            try:
                imported, duplicates, errors = self.import_csv_file(csv_file)
                total_imported += imported
                total_duplicates += duplicates
                total_errors += errors
                files_processed += 1
                
                if errors > 0:
                    self.move_csv_file(csv_file, success=False)
                else:
                    self.move_csv_file(csv_file, success=True)
            
            except CSVImportError as e:
                logger.error(f"Failed to import {csv_file.name}: {e}")
                self.move_csv_file(csv_file, success=False)
                total_errors += 1
            except Exception as e:
                logger.error(f"Unexpected error processing {csv_file.name}: {e}", exc_info=True)
                try:
                    self.move_csv_file(csv_file, success=False)
                except:
                    pass
                total_errors += 1
        
        summary: Dict[str, Any] = {
            'files_processed': files_processed,
            'total_imported': total_imported,
            'total_duplicates': total_duplicates,
            'total_errors': total_errors
        }
        
        logger.info(f"CSV import summary: {summary}")
        return summary


if __name__ == "__main__":
    from .config import ConfigLoader
    from .database import DatabaseConnectionManager
    from .logger import LoggerManager
    
    try:
        config: ConfigLoader = ConfigLoader(
            '../config/base_config.ini',
            '../config/load_compliance_check_config.ini'
        )
        
        logger_manager: LoggerManager = LoggerManager(config, script_name='test_csv_importer')
        logger_manager.configure_application_logger()
        
        db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
        csv_importer: CSVImporter = CSVImporter(config, db_manager)
        
        summary: Dict[str, Any] = csv_importer.scan_and_import_csv_files()
        
        print(f"\n✓ CSV Import Summary:")
        print(f"  Files processed: {summary['files_processed']}")
        print(f"  TIPs imported: {summary['total_imported']}")
        print(f"  Duplicates: {summary['total_duplicates']}")
        print(f"  Errors: {summary['total_errors']}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()