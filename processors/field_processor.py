"""
Field Processor Module

Handles config-driven field extraction from API responses and database operations.
Uses field mappings from object-type-specific config files to:
- Extract values from API JSON response
- Resolve hash fields to human-readable values
- Insert/update noggin_data records dynamically
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List

logger: logging.Logger = logging.getLogger(__name__)


class FieldProcessor:
    """
    Processes API response fields based on config-driven mappings
    
    Field mapping format in config:
        api_field = db_column:field_type[:hash_type]
        
    Field types:
        - string: Direct string value
        - datetime: Parse as ISO datetime
        - bool: Boolean value
        - int: Integer value
        - float: Float value
        - hash: Hash value that needs resolution (requires hash_type)
        - json: Store as JSON
    """
    
    def __init__(self, config: 'ConfigLoader', hash_manager: 'HashManager') -> None:
        self.config = config
        self.hash_manager = hash_manager
        
        # Load object type info
        obj_config = config.get_object_type_config()
        self.abbreviation: str = obj_config['abbreviation']
        self.api_id_field: str = obj_config['api_id_field']
        self.db_id_column: str = obj_config['db_id_column']
        
        # Determine object type name for DB consistency
        use_abbrev = config.getboolean('processing', 'use_abbreviation_for_object_type', fallback=False)
        if use_abbrev:
            self.object_type = self.abbreviation
        else:
            self.object_type = obj_config['object_type']
            
        # Parse field mappings
        self.field_mappings: Dict[str, Tuple[str, str, Optional[str]]] = config.get_field_mappings()
        
        logger.info(f"FieldProcessor initialised for {self.abbreviation} with {len(self.field_mappings)} field mappings")
        logger.debug(f"Using object type identifier: {self.object_type}")
    
    def extract_inspection_id(self, response_data: Dict[str, Any]) -> Optional[str]:
        """Extract the inspection ID from response"""
        return response_data.get(self.api_id_field)
    
    def extract_date(self, response_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[datetime]]:
        """
        Extract date string and parsed datetime from response
        
        Returns:
            Tuple of (date_string, parsed_datetime)
        """
        date_str: Optional[str] = response_data.get('date')
        parsed_date: Optional[datetime] = None
        
        if date_str:
            try:
                parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                logger.warning(f"Could not parse date: {date_str}")
        
        return date_str, parsed_date
    
    def process_field(self, api_field: str, value: Any, tip_value: str, 
                     inspection_id: str) -> Tuple[Any, Optional[str]]:
        """
        Process a single field value based on its type
        
        Args:
            api_field: Field name in API response
            value: Raw value from API
            tip_value: TIP for hash lookup logging
            inspection_id: Inspection ID for hash lookup logging
            
        Returns:
            Tuple of (processed_value, resolved_hash_value or None)
        """
        if api_field not in self.field_mappings:
            return value, None
        
        db_column, field_type, hash_type = self.field_mappings[api_field]
        
        if value is None:
            return None, None
        
        if field_type == 'string':
            return str(value) if value else None, None
        
        elif field_type == 'datetime':
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace('Z', '+00:00')), None
                except (ValueError, AttributeError):
                    return None, None
            return value, None
        
        elif field_type == 'bool':
            if isinstance(value, bool):
                return value, None
            if isinstance(value, str):
                return value.lower() in ('true', 'yes', '1'), None
            return bool(value), None
        
        elif field_type == 'int':
            try:
                return int(value), None
            except (ValueError, TypeError):
                return None, None
        
        elif field_type == 'float':
            try:
                return float(value), None
            except (ValueError, TypeError):
                return None, None
        
        elif field_type == 'hash':
            # Hash field - resolve to human-readable value
            if not value or not hash_type:
                return value, None
            
            hash_value: str = str(value)
            resolved: str = self.hash_manager.lookup_hash(
                hash_type, hash_value, tip_value, inspection_id
            )
            self.hash_manager.update_lookup_type_if_unknown(hash_value, hash_type)
            
            return hash_value, resolved
        
        elif field_type == 'json':
            if isinstance(value, (dict, list)):
                return json.dumps(value), None
            return str(value), None
        
        else:
            return value, None
    
    def extract_all_fields(self, response_data: Dict[str, Any], 
                          tip_value: str) -> Dict[str, Any]:
        """
        Extract all mapped fields from API response
        
        Returns:
            Dictionary with:
            - All mapped fields with processed values
            - Hash fields have both raw (_hash) and resolved values
            - has_unknown_hashes: bool indicating if any hashes unresolved
        """
        inspection_id = self.extract_inspection_id(response_data) or 'unknown'
        result: Dict[str, Any] = {
            'tip': tip_value,
            'object_type': self.object_type,
            'inspection_id': inspection_id,
        }
        
        # Track unknown hashes
        unknown_hashes: List[str] = []
        
        # Process date separately (always extract)
        date_str, parsed_date = self.extract_date(response_data)
        result['inspection_date'] = parsed_date
        result['date_str'] = date_str
        
        # Process all mapped fields
        for api_field, (db_column, field_type, hash_type) in self.field_mappings.items():
            value = response_data.get(api_field)
            
            processed_value, resolved_value = self.process_field(
                api_field, value, tip_value, inspection_id
            )
            
            if field_type == 'hash':
                # Store both hash and resolved value
                result[f"{db_column}"] = processed_value  # The hash
                resolved_column = db_column.replace('_hash', '')
                result[resolved_column] = resolved_value
                
                # Check if unresolved
                if resolved_value and resolved_value.startswith('Unknown'):
                    unknown_hashes.append(api_field)
            else:
                result[db_column] = processed_value
        
        result['has_unknown_hashes'] = len(unknown_hashes) > 0
        result['unknown_hash_fields'] = unknown_hashes
        
        return result
    
    def extract_meta_fields(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract $meta fields from API response"""
        meta: Dict[str, Any] = response_data.get('$meta', {})
        
        result: Dict[str, Any] = {
            'api_meta_raw': json.dumps(meta),
            'api_payload_raw': json.dumps(response_data),
            'raw_json': json.dumps(response_data),
        }
        
        # Parse meta dates
        if meta.get('createdDate'):
            try:
                result['api_meta_created_date'] = datetime.fromisoformat(
                    meta['createdDate'].replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                result['api_meta_created_date'] = None
        
        if meta.get('modifiedDate'):
            try:
                result['api_meta_modified_date'] = datetime.fromisoformat(
                    meta['modifiedDate'].replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                result['api_meta_modified_date'] = None
        
        # Other meta fields
        result['api_meta_security'] = meta.get('security')
        result['api_meta_type'] = meta.get('type')
        result['api_meta_tip'] = meta.get('tip')
        result['api_meta_sid'] = meta.get('sid')
        result['api_meta_branch'] = meta.get('branch')
        result['api_meta_parent'] = meta.get('parent')
        result['api_meta_errors'] = json.dumps(meta.get('errors', []))
        
        return result


class DatabaseRecordManager:
    """Manages database record operations for processed inspections"""
    
    # Core columns that exist for all object types
    CORE_COLUMNS = [
        'tip', 'object_type', 'inspection_date', 'processing_status',
        'has_unknown_hashes', 'total_attachments', 'csv_imported_at',
        'api_meta_created_date', 'api_meta_modified_date',
        'api_meta_security', 'api_meta_type', 'api_meta_tip',
        'api_meta_sid', 'api_meta_branch', 'api_meta_parent',
        'api_meta_errors', 'api_meta_raw', 'api_payload_raw', 'raw_json'
    ]
    
    # Statuses eligible for processing
    PROCESSABLE_STATUSES = [
        'pending',
        'csv_imported',
        'api_error',
        'partial',
        'failed',
    ]
    
    def __init__(self, db_manager: 'DatabaseConnectionManager', 
                 field_processor: FieldProcessor) -> None:
        self.db_manager = db_manager
        self.field_processor = field_processor
        
        # Build list of columns we'll use from field mappings
        self.mapped_columns: List[str] = []
        for api_field, (db_column, field_type, hash_type) in field_processor.field_mappings.items():
            self.mapped_columns.append(db_column)
            if field_type == 'hash':
                # Also add the resolved column
                resolved_col = db_column.replace('_hash', '')
                if resolved_col != db_column:
                    self.mapped_columns.append(resolved_col)
    
    def insert_or_update_record(self, response_data: Dict[str, Any], 
                                tip_value: str) -> None:
        """Insert or update noggin_data record with API response"""
        
        # Extract all fields
        fields = self.field_processor.extract_all_fields(response_data, tip_value)
        meta_fields = self.field_processor.extract_meta_fields(response_data)
        
        # Merge fields
        all_fields = {**fields, **meta_fields}
        all_fields['processing_status'] = 'api_success'
        all_fields['total_attachments'] = len(response_data.get('attachments', []))
        
        # Build dynamic INSERT query
        columns = []
        values = []
        update_clauses = []
        
        for col in self.CORE_COLUMNS:
            if col in all_fields:
                columns.append(col)
                values.append(all_fields[col])
                if col != 'tip':  # Don't update primary key
                    update_clauses.append(f"{col} = EXCLUDED.{col}")
        
        for col in self.mapped_columns:
            if col in all_fields and col not in columns:
                columns.append(col)
                values.append(all_fields[col])
                update_clauses.append(f"{col} = EXCLUDED.{col}")
        
        # Add inspection_id column (varies by object type)
        inspection_id = fields.get('inspection_id')
        id_column = self._get_id_column()
        if id_column and id_column not in columns:
            columns.append(id_column)
            values.append(inspection_id)
            update_clauses.append(f"{id_column} = EXCLUDED.{id_column}")
        
        update_clauses.append("updated_at = CURRENT_TIMESTAMP")
        
        placeholders = ', '.join(['%s'] * len(values))
        column_str = ', '.join(columns)
        update_str = ', '.join(update_clauses)
        
        query = f"""
            INSERT INTO noggin_data ({column_str})
            VALUES ({placeholders})
            ON CONFLICT (tip) DO UPDATE SET {update_str}
        """
        
        try:
            self.db_manager.execute_update(query, tuple(values))
            logger.debug(f"Inserted/updated noggin_data record for TIP {tip_value}")
        except Exception as e:
            logger.error(f"Failed to insert/update record for TIP {tip_value}: {e}")
            raise
    
    def _get_id_column(self) -> str:
        """Get the database column name for inspection ID (config-driven)"""
        return self.field_processor.db_id_column
    
    def update_processing_status(self, tip_value: str, status: str,
                                 error_message: Optional[str] = None) -> None:
        """Update processing status for a TIP"""
        if error_message:
            self.db_manager.execute_update(
                """
                UPDATE noggin_data 
                SET processing_status = %s, last_error_message = %s, updated_at = CURRENT_TIMESTAMP
                WHERE tip = %s
                """,
                (status, error_message, tip_value)
            )
        else:
            self.db_manager.execute_update(
                """
                UPDATE noggin_data 
                SET processing_status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE tip = %s
                """,
                (status, tip_value)
            )
    
    def update_attachment_counts(self, tip_value: str, total: int, 
                                 completed: int, all_complete: bool) -> None:
        """Update attachment counts for a TIP"""
        self.db_manager.execute_update(
            """
            UPDATE noggin_data 
            SET total_attachments = %s, 
                completed_attachment_count = %s,
                all_attachments_complete = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE tip = %s
            """,
            (total, completed, all_complete, tip_value)
        )
    
    def record_processing_error(self, tip_value: str, error_type: str,
                               error_message: str, error_details: Optional[Dict] = None) -> None:
        """Record a processing error"""
        self.db_manager.execute_update(
            """
            INSERT INTO processing_errors (tip, error_type, error_message, error_details)
            VALUES (%s, %s, %s, %s)
            """,
            (tip_value, error_type, error_message, json.dumps(error_details or {}))
        )
    
    def get_tips_to_process(self, abbreviation: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get TIPs eligible for processing"""
        # Build status placeholders for IN clause
        status_placeholders = ', '.join(['%s'] * len(self.PROCESSABLE_STATUSES))
        
        query = f"""
            SELECT tip, retry_count, processing_status
            FROM noggin_data
            WHERE object_type = %s
              AND processing_status IN ({status_placeholders})
              AND (next_retry_at IS NULL OR next_retry_at <= CURRENT_TIMESTAMP)
              AND permanently_failed = FALSE
            ORDER BY 
                CASE processing_status
                    WHEN 'pending' THEN 1
                    WHEN 'csv_imported' THEN 2
                    WHEN 'partial' THEN 3
                    WHEN 'api_error' THEN 4
                    WHEN 'failed' THEN 5
                END,
                csv_imported_at ASC
            LIMIT %s
        """
        
        params = (abbreviation, *self.PROCESSABLE_STATUSES, limit)
        return self.db_manager.execute_query_dict(query, params)
    
    def mark_permanently_failed(self, tip_value: str, reason: str) -> None:
        """Mark a TIP as permanently failed"""
        self.db_manager.execute_update(
            """
            UPDATE noggin_data 
            SET permanently_failed = TRUE,
                processing_status = 'permanently_failed',
                last_error_message = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE tip = %s
            """,
            (reason, tip_value)
        )
    
    def update_retry_info(self, tip_value: str, retry_count: int, 
                         next_retry_at: datetime) -> None:
        """Update retry information for a TIP"""
        self.db_manager.execute_update(
            """
            UPDATE noggin_data 
            SET retry_count = %s,
                next_retry_at = %s,
                last_retry_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE tip = %s
            """,
            (retry_count, next_retry_at, tip_value)
        )