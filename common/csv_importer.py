"""
CSV Importer Module

Imports TIP records from Noggin CSV exports into PostgreSQL database.
Supports all object types with configurable preview field extraction.

Key features:
- Auto-detects object type from CSV headers
- Resolves hash values using hash_lookup table
- Extracts preview fields for web search interface
- Batch inserts for efficiency
- Sets status to 'csv_imported' to distinguish from API failures
- Detects if value is hash (64-char hex) or resolved text
- Looks up hashes in hash_lookup table
- Stores both hash and resolved value in appropriate columns
- Falls back to default preview fields if INI section missing

Usage:
    from common.csv_importer import CSVImporter
    
    importer = CSVImporter(config, db_manager)
    result = importer.scan_and_import()
"""

from __future__ import annotations
import csv
import re
import logging
from pathlib import Path
from datetime import datetime
from configparser import ConfigParser
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

from .object_types import (
    ObjectTypeConfig,
    detect_object_type_from_headers,
    find_column_index,
    OBJECT_TYPES
)

logger: logging.Logger = logging.getLogger(__name__)


class CSVImportError(Exception):
    """Raised when CSV import operations fail"""
    pass


@dataclass
class ImportResult:
    """Result of importing a single CSV file"""
    filename: str
    object_type: str
    total_rows: int = 0
    imported_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    success: bool = False
    error_message: Optional[str] = None


@dataclass
class PreviewFieldMapping:
    """
    Mapping for a preview field to extract from CSV
    
    Attributes:
        csv_column: Column name in the CSV file
        db_column: Column name in the database
        is_hash_field: Whether this field may contain hash values
        hash_db_column: If is_hash_field, the column to store the hash
    """
    csv_column: str
    db_column: str
    is_hash_field: bool = False
    hash_db_column: Optional[str] = None


@dataclass
class ObjectTypePreviewConfig:
    """Preview field configuration for an object type"""
    abbreviation: str
    id_column: str
    date_column: str
    preview_fields: List[PreviewFieldMapping] = field(default_factory=list)


class HashResolver:
    """
    Resolves hash values to human-readable text using the hash_lookup table.
    
    Caches lookups to minimise database queries during batch imports.
    """
    
    # 64-character hexadecimal pattern for detecting hash values
    HASH_PATTERN = re.compile(r'^[a-fA-F0-9]{64}$')
    
    def __init__(self, db_manager: 'DatabaseConnectionManager') -> None:
        self.db_manager = db_manager
        self._cache: Dict[str, Optional[str]] = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0
    
    def is_hash(self, value: str) -> bool:
        """Check if a value appears to be a 64-character hash"""
        if not value or not isinstance(value, str):
            return False
        return bool(self.HASH_PATTERN.match(value.strip()))
    
    def resolve(self, hash_value: str) -> Optional[str]:
        """
        Resolve a hash to its human-readable value.
        
        Args:
            hash_value: The 64-character hash to resolve
            
        Returns:
            Resolved value if found, None otherwise
        """
        if not hash_value:
            return None
        
        hash_value = hash_value.strip()
        
        if hash_value in self._cache:
            self._cache_hits += 1
            return self._cache[hash_value]
        
        self._cache_misses += 1
        
        try:
            rows = self.db_manager.execute_query_dict(
                "SELECT resolved_value FROM hash_lookup WHERE tip_hash = %s",
                (hash_value,)
            )
            
            if rows:
                resolved = rows[0]['resolved_value']
                self._cache[hash_value] = resolved
                return resolved
            else:
                self._cache[hash_value] = None
                return None
                
        except Exception as e:
            logger.warning(f"Hash lookup failed for {hash_value[:16]}...: {e}")
            return None
    
    def resolve_or_passthrough(self, value: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve a value if it's a hash, otherwise pass through.
        
        Args:
            value: Value that may be a hash or resolved text
            
        Returns:
            Tuple of (resolved_value, hash_value)
            - If input is a hash: (resolved_text or None, original_hash)
            - If input is text: (original_text, None)
        """
        if not value:
            return (None, None)
        
        value = str(value).strip()
        
        if self.is_hash(value):
            resolved = self.resolve(value)
            return (resolved, value)
        else:
            return (value, None)
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Return cache statistics"""
        return {
            'cache_size': len(self._cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses
        }
    
    def clear_cache(self) -> None:
        """Clear the resolution cache"""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0


class PreviewFieldConfigLoader:
    """
    Loads preview field configurations from INI files.
    
    Each object type's INI file should have a [csv_import] section defining
    which fields to extract for web search preview.
    """
    
    # Default preview fields if [csv_import] section is missing
    DEFAULT_PREVIEW_FIELDS: Dict[str, List[Tuple[str, str, bool]]] = {
        # (csv_column, db_column, is_hash_field)
        'LCD': [
            ('lcdInspectionId', 'lcd_inspection_id', False),
            ('date', 'inspection_date', False),
            ('inspectedBy', 'inspected_by', False),
            ('driverLoaderName', 'driver_loader_name', False),
            ('team', 'team', True),
            ('vehicle', 'vehicle', True),
            ('vehicleId', 'vehicle_id', False),
            ('trailer', 'trailer', True),
            ('trailerId', 'trailer_id', False),
        ],
        'LCS': [
            ('lcsInspectionId', 'lcs_inspection_id', False),
            ('date', 'inspection_date', False),
            ('inspectedBy', 'inspected_by', False),
            ('driverLoaderName', 'driver_loader_name', False),
            ('team', 'team', True),
            ('vehicle', 'vehicle', True),
            ('vehicleId', 'vehicle_id', False),
            ('trailer', 'trailer', True),
            ('trailerId', 'trailer_id', False),
        ],
        'CCC': [
            ('couplingId', 'coupling_id', False),
            ('date', 'inspection_date', False),
            ('personCompleting', 'person_completing', False),
            ('team', 'team', True),
            ('vehicleId', 'vehicle_id', False),
            ('trailer', 'trailer', True),
            ('trailerId', 'trailer_id', False),
        ],
        'FPI': [
            ('forkliftPrestartInspectionId', 'forklift_inspection_id', False),
            ('date', 'inspection_date', False),
            ('personsCompleting', 'persons_completing', False),
            ('team', 'team', True),
            ('goldstarAsset', 'goldstar_asset', False),
            ('preStartStatus', 'prestart_status', False),
        ],
        'SO': [
            ('siteObservationId', 'site_observation_id', False),
            ('date', 'inspection_date', False),
            ('siteManager', 'site_manager', False),
            ('department', 'department', True),
            ('inspectedBy', 'inspected_by', False),
        ],
        'TA': [
            ('trailerAuditId', 'trailer_audit_id', False),
            ('date', 'inspection_date', False),
            ('inspectedBy', 'inspected_by', False),
            ('team', 'team', True),
            ('vehicle', 'vehicle', True),
            ('rego', 'rego', False),
        ],
    }
    
    # Hash field to hash column mapping
    HASH_COLUMN_MAP: Dict[str, str] = {
        'team': 'team_hash',
        'vehicle': 'vehicle_hash',
        'trailer': 'trailer_hash',
        'trailer2': 'trailer2_hash',
        'trailer3': 'trailer3_hash',
        'department': 'department_hash',
    }
    
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self._configs: Dict[str, ObjectTypePreviewConfig] = {}
    
    def load_config(self, abbreviation: str) -> ObjectTypePreviewConfig:
        """
        Load preview field config for an object type.
        
        Args:
            abbreviation: Object type abbreviation (LCD, CCC, etc.)
            
        Returns:
            ObjectTypePreviewConfig with preview field mappings
        """
        if abbreviation in self._configs:
            return self._configs[abbreviation]
        
        object_config = OBJECT_TYPES.get(abbreviation)
        if not object_config:
            raise CSVImportError(f"Unknown object type: {abbreviation}")
        
        config_file = self.config_dir / object_config.config_file
        
        preview_fields: List[PreviewFieldMapping] = []
        
        if config_file.exists():
            parser = ConfigParser()
            parser.read(config_file)
            
            if parser.has_section('csv_import'):
                for csv_col, db_col in parser.items('csv_import'):
                    is_hash = db_col in self.HASH_COLUMN_MAP
                    hash_col = self.HASH_COLUMN_MAP.get(db_col) if is_hash else None
                    
                    preview_fields.append(PreviewFieldMapping(
                        csv_column=csv_col,
                        db_column=db_col,
                        is_hash_field=is_hash,
                        hash_db_column=hash_col
                    ))
                    
                logger.debug(f"Loaded {len(preview_fields)} preview fields from {config_file.name}")
        
        if not preview_fields:
            defaults = self.DEFAULT_PREVIEW_FIELDS.get(abbreviation, [])
            for csv_col, db_col, is_hash in defaults:
                hash_col = self.HASH_COLUMN_MAP.get(db_col) if is_hash else None
                preview_fields.append(PreviewFieldMapping(
                    csv_column=csv_col,
                    db_column=db_col,
                    is_hash_field=is_hash,
                    hash_db_column=hash_col
                ))
            
            logger.debug(f"Using {len(preview_fields)} default preview fields for {abbreviation}")
        
        result = ObjectTypePreviewConfig(
            abbreviation=abbreviation,
            id_column=object_config.id_column,
            date_column=object_config.date_column,
            preview_fields=preview_fields
        )
        
        self._configs[abbreviation] = result
        return result


class CSVRowParser:
    """
    Parses CSV rows and extracts preview fields with hash resolution.
    """
    
    def __init__(self, headers: List[str], preview_config: ObjectTypePreviewConfig,
                 hash_resolver: HashResolver) -> None:
        self.headers = headers
        self.preview_config = preview_config
        self.hash_resolver = hash_resolver
        
        self._column_indices: Dict[str, int] = {}
        self._build_column_index_map()
    
    def _build_column_index_map(self) -> None:
        """Build mapping of field names to column indices"""
        for mapping in self.preview_config.preview_fields:
            idx = find_column_index(self.headers, mapping.csv_column)
            if idx >= 0:
                self._column_indices[mapping.csv_column] = idx
            else:
                logger.debug(f"Column '{mapping.csv_column}' not found in CSV headers")
        
        idx = find_column_index(self.headers, self.preview_config.id_column)
        if idx >= 0:
            self._column_indices[self.preview_config.id_column] = idx
        
        idx = find_column_index(self.headers, self.preview_config.date_column)
        if idx >= 0:
            self._column_indices[self.preview_config.date_column] = idx
    
    def parse_row(self, row: List[str]) -> Dict[str, Any]:
        """
        Parse a CSV row and extract all preview fields.
        
        Args:
            row: CSV row data (list of strings)
            
        Returns:
            Dictionary with database column names as keys
        """
        result: Dict[str, Any] = {}
        
        # TIP is always first column
        tip = row[0].strip() if row else ''
        if not tip:
            return {}
        
        result['tip'] = tip
        result['object_type'] = self.preview_config.abbreviation
        
        # # Extract inspection ID
        # id_col = self.preview_config.id_column
        # if id_col in self._column_indices:
        #     idx = self._column_indices[id_col]
        #     if idx < len(row):
        #         result['inspection_id'] = row[idx].strip() or None
        
        # Extract and convert date
        date_col = self.preview_config.date_column
        if date_col in self._column_indices:
            idx = self._column_indices[date_col]
            if idx < len(row):
                raw_date = row[idx].strip()
                result['inspection_date'] = self._parse_date(raw_date)
        
        # Extract preview fields
        for mapping in self.preview_config.preview_fields:
            if mapping.csv_column not in self._column_indices:
                continue
            
            idx = self._column_indices[mapping.csv_column]
            if idx >= len(row):
                continue
            
            raw_value = row[idx].strip()
            if not raw_value:
                continue
            
            if mapping.is_hash_field:
                resolved, hash_val = self.hash_resolver.resolve_or_passthrough(raw_value)
                
                if resolved:
                    result[mapping.db_column] = resolved
                if hash_val and mapping.hash_db_column:
                    result[mapping.hash_db_column] = hash_val
            else:
                result[mapping.db_column] = raw_value
        
        return result
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string into datetime object"""
        if not date_str:
            return None
        
        # Common date formats from Noggin exports
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d-%b-%y',      # 4-Jun-24
            '%d-%B-%Y',      # 4-June-2024
            '%d/%m/%Y',
            '%m/%d/%Y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        logger.debug(f"Could not parse date: {date_str}")
        return None


class BatchInserter:
    """
    Handles batch insertion of records into the database.
    
    Uses INSERT ... ON CONFLICT DO NOTHING to efficiently skip duplicates.
    """
    
    def __init__(self, db_manager: 'DatabaseConnectionManager', batch_size: int = 100) -> None:
        self.db_manager = db_manager
        self.batch_size = batch_size
        self._pending: List[Dict[str, Any]] = []
        self._inserted_count: int = 0
        self._duplicate_count: int = 0
    
    def add(self, record: Dict[str, Any]) -> None:
        """Add a record to the batch"""
        if record and record.get('tip'):
            self._pending.append(record)
        
        if len(self._pending) >= self.batch_size:
            self.flush()
    
    def flush(self) -> Tuple[int, int]:
        """
        Flush pending records to database.
        
        Returns:
            Tuple of (inserted_count, duplicate_count) for this batch
        """
        if not self._pending:
            return (0, 0)
        
        batch_inserted = 0
        batch_duplicates = 0
        
        # Check for existing TIPs first (batch query)
        tips = [r['tip'] for r in self._pending]
        existing_tips = self._get_existing_tips(tips)
        
        # Filter out duplicates
        new_records = [r for r in self._pending if r['tip'] not in existing_tips]
        batch_duplicates = len(self._pending) - len(new_records)
        
        if new_records:
            batch_inserted = self._insert_batch(new_records)
        
        self._inserted_count += batch_inserted
        self._duplicate_count += batch_duplicates
        self._pending.clear()
        
        return (batch_inserted, batch_duplicates)
    
    def _get_existing_tips(self, tips: List[str]) -> set:
        """Check which TIPs already exist in database"""
        if not tips:
            return set()
        
        placeholders = ','.join(['%s'] * len(tips))
        query = f"SELECT tip FROM noggin_data WHERE tip IN ({placeholders})"
        
        try:
            rows = self.db_manager.execute_query_dict(query, tuple(tips))
            return {row['tip'] for row in rows}
        except Exception as e:
            logger.error(f"Error checking existing TIPs: {e}")
            return set()

    def _insert_batch(self, records: List[Dict[str, Any]]) -> int:
        """Insert a batch of records"""
        if not records:
            return 0
        
        # --- FIX START: Add standard fields BEFORE calculating columns ---
        current_time = datetime.now()
        for record in records:
            record['processing_status'] = 'csv_imported'
            record['csv_imported_at'] = current_time
        # --- FIX END ---

        # Collect all columns used across records
        all_columns = set()
        for record in records:
            all_columns.update(record.keys())
        
        # Order columns consistently, ensuring tip and object_type are first
        priority_cols = ['tip', 'object_type', 'processing_status', 'csv_imported_at']
        ordered_columns = [c for c in priority_cols if c in all_columns]
        ordered_columns.extend(sorted(c for c in all_columns if c not in priority_cols))
        
        column_list = ', '.join(ordered_columns)
        placeholders = ', '.join(['%s'] * len(ordered_columns))
        
        insert_sql = f"""
            INSERT INTO noggin_data ({column_list})
            VALUES ({placeholders})
            ON CONFLICT (tip) DO NOTHING
        """
        
        inserted = 0
        for record in records:
            # Fields are already added above, so we just get the values now
            values = tuple(record.get(col) for col in ordered_columns)
            
            try:
                result = self.db_manager.execute_update(insert_sql, values)
                if result > 0:
                    inserted += 1
            except Exception as e:
                logger.error(f"Insert failed for TIP {record.get('tip', 'unknown')[:16]}...: {e}")
        
        return inserted
    
    # def _insert_batch(self, records: List[Dict[str, Any]]) -> int:
    #     """Insert a batch of records"""
    #     if not records:
    #         return 0
        
    #     # Collect all columns used across records
    #     all_columns = set()
    #     for record in records:
    #         all_columns.update(record.keys())
        
    #     # Order columns consistently, ensuring tip and object_type are first
    #     priority_cols = ['tip', 'object_type', 'processing_status', 'csv_imported_at']
    #     ordered_columns = [c for c in priority_cols if c in all_columns]
    #     ordered_columns.extend(sorted(c for c in all_columns if c not in priority_cols))
        
    #     column_list = ', '.join(ordered_columns)
    #     placeholders = ', '.join(['%s'] * len(ordered_columns))
        
    #     insert_sql = f"""
    #         INSERT INTO noggin_data ({column_list})
    #         VALUES ({placeholders})
    #         ON CONFLICT (tip) DO NOTHING
    #     """
        
    #     inserted = 0
    #     for record in records:
    #         # Add standard fields
    #         record['processing_status'] = 'csv_imported'
    #         record['csv_imported_at'] = datetime.now()
            
    #         values = tuple(record.get(col) for col in ordered_columns)
            
    #         try:
    #             result = self.db_manager.execute_update(insert_sql, values)
    #             if result > 0:
    #                 inserted += 1
    #         except Exception as e:
    #             logger.error(f"Insert failed for TIP {record.get('tip', 'unknown')[:16]}...: {e}")
        
    #     return inserted
    
    def get_stats(self) -> Dict[str, int]:
        """Get insertion statistics"""
        return {
            'inserted': self._inserted_count,
            'duplicates': self._duplicate_count,
            'pending': len(self._pending)
        }


class CSVFileProcessor:
    """
    Processes a single CSV file and imports its records.
    """
    
    def __init__(self, file_path: Path, preview_config_loader: PreviewFieldConfigLoader,
                 hash_resolver: HashResolver, db_manager: 'DatabaseConnectionManager',
                 batch_size: int = 100) -> None:
        self.file_path = file_path
        self.preview_config_loader = preview_config_loader
        self.hash_resolver = hash_resolver
        self.db_manager = db_manager
        self.batch_size = batch_size
    
    def process(self) -> ImportResult:
        """
        Process the CSV file and import records.
        
        Returns:
            ImportResult with import statistics
        """
        result = ImportResult(filename=self.file_path.name, object_type='Unknown')
        
        try:
            with open(self.file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                
                if not headers:
                    result.error_message = "CSV file has no headers"
                    return result
                
                # Detect object type
                object_config = detect_object_type_from_headers(headers)
                if not object_config:
                    result.error_message = f"Could not detect object type from headers: {headers[:5]}"
                    return result
                
                result.object_type = object_config.abbreviation
                logger.info(f"Detected object type: {object_config.abbreviation} ({object_config.full_name})")
                
                # Load preview field config
                preview_config = self.preview_config_loader.load_config(object_config.abbreviation)
                
                # Create row parser
                row_parser = CSVRowParser(headers, preview_config, self.hash_resolver)
                
                # Create batch inserter
                inserter = BatchInserter(self.db_manager, self.batch_size)
                
                # Process rows
                for row_num, row in enumerate(reader, start=2):
                    if not row or not row[0].strip():
                        continue
                    
                    result.total_rows += 1
                    
                    try:
                        parsed = row_parser.parse_row(row)
                        if parsed:
                            inserter.add(parsed)
                    except Exception as e:
                        logger.warning(f"Row {row_num}: Parse error - {e}")
                        result.error_count += 1
                
                # Flush remaining records
                inserter.flush()
                
                stats = inserter.get_stats()
                result.imported_count = stats['inserted']
                result.duplicate_count = stats['duplicates']
                result.success = result.error_count == 0
                
                logger.info(
                    f"Import complete for {self.file_path.name}: "
                    f"{result.imported_count} imported, "
                    f"{result.duplicate_count} duplicates, "
                    f"{result.error_count} errors"
                )
                
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Failed to process {self.file_path.name}: {e}")
        
        return result


class CSVImporter:
    """
    Main CSV importer class.
    
    Scans input folder for CSV files, auto-detects object types,
    and imports records with preview field extraction and hash resolution.
    
    Example usage:
        importer = CSVImporter(config, db_manager)
        summary = importer.scan_and_import()
        
        # Or import a specific file
        result = importer.import_file(Path('/path/to/file.csv'))
    """
    
    def __init__(self, config: 'ConfigLoader', db_manager: 'DatabaseConnectionManager') -> None:
        """
        Initialise the CSV importer.
        
        Args:
            config: ConfigLoader instance for reading paths and settings
            db_manager: DatabaseConnectionManager instance for database operations
        """
        self.config = config
        self.db_manager = db_manager
        
        self.input_folder = Path(config.get('paths', 'input_folder_path'))
        self.processed_folder = Path(config.get('paths', 'processed_folder_path'))
        self.error_folder = Path(config.get('paths', 'error_folder_path'))
        
        self.input_folder.mkdir(parents=True, exist_ok=True)
        self.processed_folder.mkdir(parents=True, exist_ok=True)
        self.error_folder.mkdir(parents=True, exist_ok=True)
        
        config_dir = Path(config.get('paths', 'config_dir', fallback='config'))
        
        self.preview_config_loader = PreviewFieldConfigLoader(config_dir)
        self.hash_resolver = HashResolver(db_manager)
        self.batch_size = config.getint('csv_import', 'batch_size', fallback=100)
    
    def import_file(self, file_path: Path) -> ImportResult:
        """
        Import a single CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            ImportResult with import statistics
        """
        if not file_path.exists():
            return ImportResult(
                filename=file_path.name,
                object_type='Unknown',
                error_message=f"File not found: {file_path}"
            )
        
        logger.info(f"Importing CSV file: {file_path.name}")
        
        processor = CSVFileProcessor(
            file_path=file_path,
            preview_config_loader=self.preview_config_loader,
            hash_resolver=self.hash_resolver,
            db_manager=self.db_manager,
            batch_size=self.batch_size
        )
        
        return processor.process()
    
    def scan_and_import(self) -> Dict[str, Any]:
        """
        Scan input folder and import all CSV files.
        
        Returns:
            Dictionary with overall import statistics
        """
        csv_files = list(self.input_folder.glob('*.csv'))
        
        if not csv_files:
            logger.debug(f"No CSV files found in {self.input_folder}")
            return {
                'files_processed': 0,
                'total_imported': 0,
                'total_duplicates': 0,
                'total_errors': 0,
                'files_succeeded': 0,
                'files_failed': 0,
            }
        
        logger.info(f"Found {len(csv_files)} CSV file(s) to process")
        
        results: List[ImportResult] = []
        
        for csv_file in csv_files:
            result = self.import_file(csv_file)
            results.append(result)
            
            # Move file based on result
            if result.success:
                self._move_file(csv_file, self.processed_folder)
            else:
                self._move_file(csv_file, self.error_folder)
                logger.error(f"Import failed for {csv_file.name}: {result.error_message}")
        
        # Log hash resolver stats
        cache_stats = self.hash_resolver.get_cache_stats()
        logger.info(
            f"Hash resolver stats: {cache_stats['cache_size']} cached, "
            f"{cache_stats['cache_hits']} hits, {cache_stats['cache_misses']} misses"
        )
        
        summary = {
            'files_processed': len(results),
            'total_imported': sum(r.imported_count for r in results),
            'total_duplicates': sum(r.duplicate_count for r in results),
            'total_errors': sum(r.error_count for r in results),
            'files_succeeded': sum(1 for r in results if r.success),
            'files_failed': sum(1 for r in results if not r.success),
            'results': results,
        }
        
        logger.info(
            f"CSV import summary: {summary['files_processed']} files, "
            f"{summary['total_imported']} imported, "
            f"{summary['total_duplicates']} duplicates, "
            f"{summary['total_errors']} errors"
        )
        
        return summary
    
    def _move_file(self, source: Path, destination_folder: Path) -> Optional[Path]:
        """Move file to destination folder with timestamp"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{source.stem}_{timestamp}{source.suffix}"
        destination = destination_folder / new_filename
        
        try:
            source.rename(destination)
            logger.info(f"Moved {source.name} to {destination_folder.name}/")
            return destination
        except Exception as e:
            logger.error(f"Failed to move {source.name}: {e}")
            return None


# Legacy function for backward compatibility
def detect_object_type(headers: List[str]) -> Optional[str]:
    """
    Detect object type from CSV headers (legacy compatibility).
    
    Args:
        headers: List of column headers
        
    Returns:
        Object type abbreviation or None
    """
    config = detect_object_type_from_headers(headers)
    return config.abbreviation if config else None


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    script_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(script_dir))
    
    from common import ConfigLoader, DatabaseConnectionManager, LoggerManager
    
    try:
        config = ConfigLoader('config/base_config.ini')
        
        logger_manager = LoggerManager(config, script_name='csv_importer')
        logger_manager.configure_application_logger()
        
        db_manager = DatabaseConnectionManager(config)
        importer = CSVImporter(config, db_manager)
        
        summary = importer.scan_and_import()
        
        print(f"\nCSV Import Summary:")
        print(f"  Files processed: {summary['files_processed']}")
        print(f"  Files succeeded: {summary['files_succeeded']}")
        print(f"  Files failed: {summary['files_failed']}")
        print(f"  TIPs imported: {summary['total_imported']}")
        print(f"  Duplicates skipped: {summary['total_duplicates']}")
        print(f"  Errors: {summary['total_errors']}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()