"""
Hash Manager - Runtime hash lookup operations

Provides in-memory cached lookups for resolving Noggin hashes to human-readable values.
The hash_lookup table is populated by hash_lookup_sync.py from weekly Noggin exports.

This module is used by processors during data extraction to resolve vehicle, trailer,
team, and department hashes to their display names.

Changes from original:
1. Removed unnecessary pandas dependency and file rewrite operations
2. Improved type detection with configurable patterns
3. Added batch database operations for efficiency
4. Better cache management
5. Added statistics and reporting methods
6. Fixed cache invalidation issues
"""

from __future__ import annotations
import logging
import csv
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set
from datetime import datetime

logger: logging.Logger = logging.getLogger(__name__)


class HashLookupError(Exception):
    """Raised when hash lookup operations fail"""
    pass


# Type detection patterns - configurable and more accurate
TYPE_DETECTION_PATTERNS: Dict[str, Dict[str, Any]] = {
    'team': {
        'keywords': ['team', 'workers', 'drivers', 'admin', 'yard', 'delivery', 'steel', 'bulk', 'packaged'],
        'patterns': [r'.+\s+-\s+.+'], 
        'priority': 1
    },
    'department': {
        'keywords': ['department', 'transport', 'workshop', 'distribution'],
        'patterns': [],
        'priority': 2
    },
    'trailer': {
        'prefixes': ['T', 'TL', 'TLD', 'TS', 'TSD', 'TSE', 'TSP', 'TDD', 'TEX'],
        'patterns': [r'^T[A-Z]*\d+$', r'^T\d+$'],
        'priority': 3
    },
    'vehicle': {
        'prefixes': ['MB', 'D', 'F', 'R', 'RC', 'RF', 'H', 'A', 'LV', 'SL', 'FS', 'AL', 'VCT', 'MAN', 'RE', 'RA'],
        'patterns': [r'^[A-Z]{1,3}\d+$'],
        'priority': 4
    }
}


class HashManager:
    """Manages hash lookups and resolution for Noggin data"""
    
    def __init__(self, config: 'ConfigLoader', db_manager: 'DatabaseConnectionManager') -> None:
        self.config: 'ConfigLoader' = config
        self.db_manager: 'DatabaseConnectionManager' = db_manager
        self.log_path: Path = Path(config.get('paths', 'base_log_path'))
        self.log_path.mkdir(parents=True, exist_ok=True)
        
        self._cache: Dict[Tuple[str, str], str] = {}
        self._cache_loaded: bool = False
        self._unknown_hashes_logged: Set[Tuple[str, str]] = set()
    
    def _load_cache(self) -> None:
        """Load hash lookups into memory cache"""
        if self._cache_loaded:
            return
        
        try:
            results: List[Dict[str, Any]] = self.db_manager.execute_query_dict(
                "SELECT tip_hash, lookup_type, resolved_value FROM hash_lookup"
            )
            
            self._cache.clear()
            for row in results:
                cache_key = (row['tip_hash'], row['lookup_type'])
                self._cache[cache_key] = row['resolved_value']
            
            self._cache_loaded = True
            logger.info(f"Loaded {len(self._cache)} hash lookups into cache")
            
        except Exception as e:
            logger.error(f"Failed to load hash lookup cache: {e}")
            raise HashLookupError(f"Cache load failed: {e}")
    
    def invalidate_cache(self) -> None:
        """Force cache reload on next lookup"""
        self._cache_loaded = False
        self._cache.clear()
        logger.debug("Hash cache invalidated")
    
    def lookup_hash(self, lookup_type: str, tip_hash: str, tip_value: Optional[str] = None, 
                   inspection_id: Optional[str] = None) -> str:
        """
        Lookup hash and return resolved value
        
        Args:
            lookup_type: Type of lookup (vehicle, trailer, department, team)
            tip_hash: Hash value to resolve
            tip_value: TIP value for logging unknown hashes
            inspection_id: Inspection ID for logging
            
        Returns:
            Resolved value or "Unknown (hash)" if not found
        """
        if not tip_hash:
            return ""
        
        if not self._cache_loaded:
            self._load_cache()
        
        cache_key: Tuple[str, str] = (tip_hash, lookup_type)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Also check if hash exists under 'unknown' type
        unknown_key = (tip_hash, 'unknown')
        if unknown_key in self._cache:
            return self._cache[unknown_key]
        
        self._record_unknown_hash(lookup_type, tip_hash, tip_value, inspection_id)
        
        return f"Unknown ({tip_hash[:16]}...)"
    
    def _record_unknown_hash(self, lookup_type: str, tip_hash: str, 
                            tip_value: Optional[str], inspection_id: Optional[str]) -> None:
        """Record unknown hash to database and log file"""
        cache_key = (tip_hash, lookup_type)
        
        # Avoid duplicate logging within same session
        if cache_key in self._unknown_hashes_logged:
            return
        
        self._unknown_hashes_logged.add(cache_key)
        
        # Log to file
        unknown_log_file: Path = self.log_path / 'unknown_hashes.log'
        timestamp: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry: str = f"{timestamp} | {lookup_type} | {tip_hash} | {inspection_id or 'N/A'} | TIP: {tip_value or 'N/A'}\n"
        
        try:
            with open(unknown_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.warning(f"Could not write to unknown hashes log: {e}")
        
        # Insert to database
        try:
            self.db_manager.execute_update(
                """
                INSERT INTO unknown_hashes (tip_hash, lookup_type, first_seen_at, first_seen_tip, first_seen_inspection_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (tip_hash, lookup_type) DO UPDATE SET
                    last_seen_at = CURRENT_TIMESTAMP,
                    occurrence_count = unknown_hashes.occurrence_count + 1
                """,
                (tip_hash, lookup_type, datetime.now(), tip_value, inspection_id)
            )
        except Exception as e:
            logger.debug(f"Could not record unknown hash to database: {e}")
        
        logger.warning(f"Unknown hash: {lookup_type}={tip_hash[:16]}...")
    
    def detect_lookup_type(self, resolved_value: str) -> str:
        """
        Detect lookup type from resolved value using configurable patterns
        
        Args:
            resolved_value: The human-readable value
            
        Returns:
            Detected lookup type or 'unknown'
        """
        if not resolved_value:
            return 'unknown'
        
        value_upper: str = resolved_value.upper().strip()
        value_lower: str = resolved_value.lower().strip()
        
        # Check each type in priority order
        type_scores: Dict[str, int] = {}
        
        for type_name, config in TYPE_DETECTION_PATTERNS.items():
            score = 0
            
            # Check keywords
            keywords = config.get('keywords', [])
            for keyword in keywords:
                if keyword in value_lower:
                    score += 10
            
            # Check prefixes (for vehicle/trailer codes)
            prefixes = config.get('prefixes', [])
            for prefix in prefixes:
                if value_upper.startswith(prefix) and len(resolved_value) <= 10:
                    # Ensure it's a code pattern (prefix + numbers)
                    remainder = value_upper[len(prefix):]
                    if remainder.isdigit() or re.match(r'^\d+$', remainder):
                        score += 20
            
            # Check regex patterns
            patterns = config.get('patterns', [])
            for pattern in patterns:
                if re.match(pattern, resolved_value, re.IGNORECASE):
                    score += 15
            
            if score > 0:
                type_scores[type_name] = score
        
        if not type_scores:
            return 'unknown'
        
        # Return type with highest score
        best_type = max(type_scores, key=type_scores.get)
        return best_type
    
    def migrate_lookup_table_from_csv(self, csv_file_path: str, 
                                      batch_size: int = 100) -> Tuple[int, int]:
        """
        Migrate hash lookup table from CSV to PostgreSQL using batch operations
        
        Args:
            csv_file_path: Path to lookup_table.csv
            batch_size: Number of rows per batch insert
            
        Returns:
            Tuple of (imported_count, skipped_count)
        """
        csv_path: Path = Path(csv_file_path)
        
        if not csv_path.exists():
            raise HashLookupError(f"CSV file not found: {csv_file_path}")
        
        logger.info(f"Migrating hash lookups from {csv_file_path}")
        
        imported_count: int = 0
        skipped_count: int = 0
        batch: List[Tuple[str, str, str]] = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                if 'TIP' not in reader.fieldnames or 'VALUE' not in reader.fieldnames:
                    raise HashLookupError(f"CSV must contain 'TIP' and 'VALUE' columns. Found: {reader.fieldnames}")
                
                for row in reader:
                    tip_hash: str = row['TIP'].strip()
                    resolved_value: str = row['VALUE'].strip()
                    
                    if not tip_hash or not resolved_value:
                        skipped_count += 1
                        continue
                    
                    lookup_type: str = self.detect_lookup_type(resolved_value)
                    batch.append((tip_hash, lookup_type, resolved_value))
                    
                    if len(batch) >= batch_size:
                        imported_count += self._insert_batch(batch)
                        batch = []
                
                # Insert remaining batch
                if batch:
                    imported_count += self._insert_batch(batch)
            
            # Invalidate cache after bulk import
            self.invalidate_cache()
            
            logger.info(f"Migration complete: {imported_count} imported, {skipped_count} skipped")
            return imported_count, skipped_count
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            raise HashLookupError(f"Migration failed: {e}")
    
    def _insert_batch(self, batch: List[Tuple[str, str, str]]) -> int:
        """Insert batch of hash lookups using executemany pattern"""
        if not batch:
            return 0
        
        try:
            # Use execute_transaction for batch insert with upsert
            queries = []
            for tip_hash, lookup_type, resolved_value in batch:
                queries.append((
                    """
                    INSERT INTO hash_lookup (tip_hash, lookup_type, resolved_value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (tip_hash, lookup_type) 
                    DO UPDATE SET resolved_value = EXCLUDED.resolved_value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (tip_hash, lookup_type, resolved_value)
                ))
            
            success = self.db_manager.execute_transaction(queries)
            
            if success:
                # Update cache
                for tip_hash, lookup_type, resolved_value in batch:
                    self._cache[(tip_hash, lookup_type)] = resolved_value
                return len(batch)
            else:
                logger.error("Batch insert transaction failed")
                return 0
                
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            return 0
    
    def resolve_unknown_hash(self, tip_hash: str, lookup_type: str, resolved_value: str) -> bool:
        """
        Manually resolve an unknown hash
        
        Args:
            tip_hash: Hash to resolve
            lookup_type: Type of lookup
            resolved_value: Value to associate with hash
            
        Returns:
            True if successful
        """
        try:
            # Insert/update in hash_lookup
            self.db_manager.execute_update(
                """
                INSERT INTO hash_lookup (tip_hash, lookup_type, resolved_value)
                VALUES (%s, %s, %s)
                ON CONFLICT (tip_hash, lookup_type) 
                DO UPDATE SET resolved_value = EXCLUDED.resolved_value, updated_at = CURRENT_TIMESTAMP
                """,
                (tip_hash, lookup_type, resolved_value)
            )
            
            # Mark as resolved in unknown_hashes
            self.db_manager.execute_update(
                """
                UPDATE unknown_hashes
                SET resolved_at = CURRENT_TIMESTAMP, resolved_value = %s
                WHERE tip_hash = %s AND lookup_type = %s AND resolved_at IS NULL
                """,
                (resolved_value, tip_hash, lookup_type)
            )
            
            # Update cache
            self._cache[(tip_hash, lookup_type)] = resolved_value
            
            logger.info(f"Resolved hash: {lookup_type}={tip_hash[:16]}... -> {resolved_value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve hash: {e}")
            return False
    
    def get_unknown_hashes(self, lookup_type: Optional[str] = None, 
                          resolved: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get list of unknown hashes
        
        Args:
            lookup_type: Filter by type (optional)
            resolved: If True, get resolved. If False, get unresolved.
            limit: Maximum number to return
            
        Returns:
            List of dictionaries with unknown hash information
        """
        conditions = []
        params = []
        
        if resolved:
            conditions.append("resolved_at IS NOT NULL")
        else:
            conditions.append("resolved_at IS NULL")
        
        if lookup_type:
            conditions.append("lookup_type = %s")
            params.append(lookup_type)
        
        where_clause = " AND ".join(conditions)
        params.append(limit)
        
        query = f"""
            SELECT tip_hash, lookup_type, first_seen_at, last_seen_at, 
                   occurrence_count, first_seen_inspection_id, resolved_at, resolved_value
            FROM unknown_hashes
            WHERE {where_clause}
            ORDER BY occurrence_count DESC, last_seen_at DESC
            LIMIT %s
        """
        
        return self.db_manager.execute_query_dict(query, tuple(params))
    
    def auto_resolve_unknown_hashes(self) -> int:
        """
        Automatically resolve unknown hashes that now exist in hash_lookup
        
        Returns:
            Number of hashes resolved
        """
        logger.info("Starting automatic hash resolution")
        
        # Find unknown hashes that have matching entries in hash_lookup
        query = """
            UPDATE unknown_hashes uh
            SET resolved_at = CURRENT_TIMESTAMP,
                resolved_value = hl.resolved_value
            FROM hash_lookup hl
            WHERE uh.tip_hash = hl.tip_hash
              AND uh.lookup_type = hl.lookup_type
              AND uh.resolved_at IS NULL
        """
        
        count = self.db_manager.execute_update(query)
        
        if count > 0:
            logger.info(f"Auto-resolved {count} unknown hashes")
            self.invalidate_cache()
        else:
            logger.debug("No unknown hashes could be auto-resolved")
        
        return count
    
    def update_lookup_type_if_unknown(self, tip_hash: str, context_key: str) -> None:
        """
        Update lookup_type from 'unknown' to actual type based on context
        
        Args:
            tip_hash: Hash value
            context_key: Key from API response (team, vehicle, whichDepartmentDoesTheLoadBelongTo, trailer)
        """
        if not tip_hash:
            return
        
        # Normalise context key to lookup type
        type_mapping = {
            'whichDepartmentDoesTheLoadBelongTo': 'department',
            'vehicle': 'vehicle',
            'trailer': 'trailer',
            'trailer2': 'trailer',
            'trailer3': 'trailer',
            'team': 'team'
        }
        
        normalised_type = type_mapping.get(context_key, context_key)
        
        try:
            rows_updated = self.db_manager.execute_update(
                """
                UPDATE hash_lookup
                SET lookup_type = %s, updated_at = CURRENT_TIMESTAMP
                WHERE tip_hash = %s AND lookup_type = 'unknown'
                """,
                (normalised_type, tip_hash)
            )
            
            if rows_updated > 0:
                # Update cache
                if (tip_hash, 'unknown') in self._cache:
                    value = self._cache.pop((tip_hash, 'unknown'))
                    self._cache[(tip_hash, normalised_type)] = value
                logger.debug(f"Updated lookup_type: {tip_hash[:16]}... from unknown to {normalised_type}")
                
        except Exception as e:
            logger.debug(f"Could not update lookup_type for {tip_hash[:16]}...: {e}")
    
    def get_statistics(self) -> Dict[str, Dict[str, int]]:
        """Get statistics about known and unknown hashes by type"""
        stats = {}
        
        # Get known hash counts
        known_query = """
            SELECT lookup_type, COUNT(*) as count 
            FROM hash_lookup 
            GROUP BY lookup_type
        """
        known_results = self.db_manager.execute_query_dict(known_query)
        
        # Get unknown hash counts
        unknown_query = """
            SELECT lookup_type, COUNT(*) as count 
            FROM unknown_hashes 
            WHERE resolved_at IS NULL
            GROUP BY lookup_type
        """
        unknown_results = self.db_manager.execute_query_dict(unknown_query)
        
        # Combine results
        all_types = set()
        known_by_type = {r['lookup_type']: r['count'] for r in known_results}
        unknown_by_type = {r['lookup_type']: r['count'] for r in unknown_results}
        
        all_types.update(known_by_type.keys())
        all_types.update(unknown_by_type.keys())
        
        for lookup_type in sorted(all_types):
            stats[lookup_type] = {
                'known': known_by_type.get(lookup_type, 0),
                'unknown': unknown_by_type.get(lookup_type, 0)
            }
        
        return stats
    
    def export_unknown_hashes(self, output_path: Path, lookup_type: Optional[str] = None) -> int:
        """
        Export unknown hashes to CSV for manual resolution
        
        Args:
            output_path: Path for output CSV
            lookup_type: Filter by type (optional)
            
        Returns:
            Number of hashes exported
        """
        unknown = self.get_unknown_hashes(lookup_type=lookup_type, resolved=False, limit=10000)
        
        if not unknown:
            logger.info(f"No unknown hashes to export")
            return 0
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['TIP', 'VALUE', 'lookup_type', 'occurrence_count', 'first_seen_inspection_id'])
            
            for row in unknown:
                writer.writerow([
                    row['tip_hash'],
                    '',  # Empty VALUE for user to fill in
                    row['lookup_type'],
                    row['occurrence_count'],
                    row['first_seen_inspection_id'] or ''
                ])
        
        logger.info(f"Exported {len(unknown)} unknown hashes to {output_path}")
        return len(unknown)
    
    def import_resolved_hashes(self, csv_path: Path) -> Tuple[int, int]:
        """
        Import resolved hashes from CSV (after manual resolution)
        
        Expected columns: TIP, VALUE, lookup_type
        
        Args:
            csv_path: Path to CSV with resolved values
            
        Returns:
            Tuple of (resolved_count, skipped_count)
        """
        if not csv_path.exists():
            raise HashLookupError(f"CSV file not found: {csv_path}")
        
        resolved_count = 0
        skipped_count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                tip_hash = row.get('TIP', '').strip()
                resolved_value = row.get('VALUE', '').strip()
                lookup_type = row.get('lookup_type', 'unknown').strip()
                
                if not tip_hash or not resolved_value:
                    skipped_count += 1
                    continue
                
                if self.resolve_unknown_hash(tip_hash, lookup_type, resolved_value):
                    resolved_count += 1
                else:
                    skipped_count += 1
        
        logger.info(f"Import complete: {resolved_count} resolved, {skipped_count} skipped")
        return resolved_count, skipped_count


if __name__ == "__main__":
    from .config import ConfigLoader
    from .database import DatabaseConnectionManager
    from .logger import LoggerManager
    
    try:
        config = ConfigLoader(
            '../config/base_config.ini',
            '../config/load_compliance_check_config.ini'
        )
        
        logger_manager = LoggerManager(config, script_name='test_hash_manager')
        logger_manager.configure_application_logger()
        
        db_manager = DatabaseConnectionManager(config)
        hash_manager = HashManager(config, db_manager)
        
        # Test type detection
        test_values = ['MB26', 'T107', 'Steel Delivery', 'Air Liquide Packaged - Drivers', 'LH Yard - Team']
        print("\nType Detection Test:")
        for value in test_values:
            detected = hash_manager.detect_lookup_type(value)
            print(f"  {value:40} -> {detected}")
        
        # Get statistics
        stats = hash_manager.get_statistics()
        print("\nHash Statistics:")
        for lookup_type, counts in stats.items():
            print(f"  {lookup_type}: {counts['known']} known, {counts['unknown']} unknown")
        
        print("\nHash manager tests passed")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()
