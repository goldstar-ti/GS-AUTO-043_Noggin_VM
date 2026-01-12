"""
Hash Manager - Runtime hash lookup operations

Provides in-memory cached lookups for resolving Noggin hashes to human-readable values.
The hash_lookup table is populated by hash_lookup_sync.py from weekly Noggin exports.

This module is used by processors during data extraction to resolve vehicle, trailer,
team, and department hashes to their display names.

Loads hash type detection patterns from config/hash_detection.ini


Changes from original:
1. Removed unnecessary pandas dependency and file rewrite operations
2. Improved type detection with configurable patterns
3. Added batch database operations for efficiency
4. Better cache management
5. Added statistics and reporting methods
6. Fixed cache invalidation issues
"""
from __future__ import annotations
import configparser
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


class HashTypeDetector:
    """Loads and applies hash type detection rules from config"""
    
    _instance: Optional['HashTypeDetector'] = None
    _patterns: Dict[str, Dict[str, Any]] = {}
    _settings: Dict[str, int] = {}
    _loaded: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load(self, config_path: Optional[str] = None) -> None:
        """Load detection patterns from config file"""
        if self._loaded and config_path is None:
            return
        
        if config_path is None:
            config_path = self._find_config_file()
        
        if config_path is None:
            logger.warning("hash_detection.ini not found, using defaults")
            self._load_defaults()
            return
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        self._patterns.clear()
        
        # Load scoring settings
        if config.has_section('hash_detection'):
            self._settings = {
                'keyword_score': config.getint('hash_detection', 'keyword_score', fallback=10),
                'prefix_score': config.getint('hash_detection', 'prefix_score', fallback=20),
                'pattern_score': config.getint('hash_detection', 'pattern_score', fallback=15),
                'max_code_length': config.getint('hash_detection', 'max_code_length', fallback=10),
            }
        else:
            self._settings = {
                'keyword_score': 10,
                'prefix_score': 20,
                'pattern_score': 15,
                'max_code_length': 10,
            }
        
        # Load type patterns
        for section in config.sections():
            if not section.startswith('hash_type.'):
                continue
            
            type_name = section.replace('hash_type.', '')
            
            # Parse comma-separated values, filter empty strings
            keywords_str = config.get(section, 'keywords', fallback='')
            prefixes_str = config.get(section, 'prefixes', fallback='')
            patterns_str = config.get(section, 'patterns', fallback='')
            
            keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
            prefixes = [p.strip() for p in prefixes_str.split(',') if p.strip()]
            patterns = [p.strip() for p in patterns_str.split(',') if p.strip()]
            
            self._patterns[type_name] = {
                'keywords': keywords,
                'prefixes': prefixes,
                'patterns': patterns,
                'priority': config.getint(section, 'priority', fallback=99)
            }
        
        self._loaded = True
        logger.info(f"Loaded {len(self._patterns)} hash type patterns from {config_path}")
    
    def _find_config_file(self) -> Optional[str]:
        """Search for hash_detection.ini in common locations"""
        search_paths = [
            Path('config/hash_detection.ini'),
            Path('../config/hash_detection.ini'),
            Path(__file__).parent.parent / 'config' / 'hash_detection.ini',
            Path(__file__).parent / 'config' / 'hash_detection.ini',
            Path('/home/noggin_admin/scripts/config/hash_detection.ini'),
        ]
        
        for path in search_paths:
            if path.exists():
                return str(path)
        
        return None
    
    def _load_defaults(self) -> None:
        """Load default patterns (fallback if no config found)"""
        self._settings = {
            'keyword_score': 10,
            'prefix_score': 20,
            'pattern_score': 15,
            'max_code_length': 10,
        }
        
        self._patterns = {
            'team': {
                'keywords': ['team', 'workers', 'drivers', 'admin', 'yard', 'delivery', 'steel', 'bulk', 'packaged'],
                'prefixes': [],
                'patterns': [r'.+\s+-\s+.+'],
                'priority': 1
            },
            'department': {
                'keywords': ['department', 'transport', 'workshop', 'distribution'],
                'prefixes': [],
                'patterns': [],
                'priority': 2
            },
            'trailer': {
                'prefixes': ['T', 'TL', 'TLD', 'TS', 'TSD', 'TSE', 'TSP', 'TDD', 'TEX'],
                'patterns': [r'^T[A-Z]*\d+$', r'^T\d+$'],
                'keywords': [],
                'priority': 3
            },
            'vehicle': {
                'prefixes': ['MB', 'D', 'F', 'R', 'RC', 'RF', 'H', 'A', 'LV', 'SL', 'FS', 'AL', 'VCT', 'MAN', 'RE', 'RA', 'ALL'],
                'patterns': [r'^[A-Z]{1,3}\d+$'],
                'keywords': [],
                'priority': 4
            }
        }
        
        self._loaded = True
        logger.debug("Loaded default hash type patterns")
    
    def detect_type(self, resolved_value: str) -> str:
        """
        Detect lookup type from resolved value
        
        Args:
            resolved_value: The human-readable value
            
        Returns:
            Detected lookup type or 'unknown'
        """
        if not self._loaded:
            self.load()
        
        if not resolved_value:
            return 'unknown'
        
        value_upper = resolved_value.upper().strip()
        value_lower = resolved_value.lower().strip()
        
        type_scores: Dict[str, int] = {}
        
        for type_name, config in self._patterns.items():
            score = 0
            
            # Check keywords
            for keyword in config.get('keywords', []):
                if keyword in value_lower:
                    score += self._settings['keyword_score']
            
            # Check prefixes (for code-style values like MB26, T107)
            for prefix in config.get('prefixes', []):
                if value_upper.startswith(prefix) and len(resolved_value) <= self._settings['max_code_length']:
                    remainder = value_upper[len(prefix):]
                    if remainder.isdigit():
                        score += self._settings['prefix_score']
            
            # Check regex patterns
            for pattern in config.get('patterns', []):
                if re.match(pattern, resolved_value, re.IGNORECASE):
                    score += self._settings['pattern_score']
            
            if score > 0:
                type_scores[type_name] = score
        
        if not type_scores:
            return 'unknown'
        
        return max(type_scores, key=type_scores.get)
    
    def get_all_types(self) -> List[str]:
        """Get list of all configured hash types"""
        if not self._loaded:
            self.load()
        return list(self._patterns.keys())
    
    def add_prefix(self, type_name: str, prefix: str) -> None:
        """Dynamically add a prefix to a type (for runtime updates)"""
        if type_name in self._patterns:
            if prefix not in self._patterns[type_name]['prefixes']:
                self._patterns[type_name]['prefixes'].append(prefix)
                logger.info(f"Added prefix '{prefix}' to {type_name}")
    
    def add_keyword(self, type_name: str, keyword: str) -> None:
        """Dynamically add a keyword to a type"""
        if type_name in self._patterns:
            if keyword not in self._patterns[type_name]['keywords']:
                self._patterns[type_name]['keywords'].append(keyword)
                logger.info(f"Added keyword '{keyword}' to {type_name}")


# Module-level detector instance
_detector = HashTypeDetector()


def load_hash_detection_config(config_path: Optional[str] = None) -> None:
    """Explicitly load hash detection config"""
    _detector.load(config_path)


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
        
        # Load detection config if available
        hash_config_path = config.get('hash_detection', 'config_file', fallback=None)
        if hash_config_path:
            _detector.load(hash_config_path)
    
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
        Detect lookup type from resolved value using config patterns
        
        Args:
            resolved_value: The human-readable value
            
        Returns:
            Detected lookup type or 'unknown'
        """
        return _detector.detect_type(resolved_value)
    
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
                
                if batch:
                    imported_count += self._insert_batch(batch)
            
            self.invalidate_cache()
            
            logger.info(f"Migration complete: {imported_count} imported, {skipped_count} skipped")
            return imported_count, skipped_count
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            raise HashLookupError(f"Migration failed: {e}")
    
    def _insert_batch(self, batch: List[Tuple[str, str, str]]) -> int:
        """Insert batch of hash lookups using upsert"""
        if not batch:
            return 0
        
        try:
            for tip_hash, lookup_type, resolved_value in batch:
                self.db_manager.execute_update(
                    """
                    INSERT INTO hash_lookup (tip_hash, lookup_type, resolved_value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (tip_hash, lookup_type) 
                    DO UPDATE SET resolved_value = EXCLUDED.resolved_value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (tip_hash, lookup_type, resolved_value)
                )
                self._cache[(tip_hash, lookup_type)] = resolved_value
            
            return len(batch)
                
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
            self.db_manager.execute_update(
                """
                INSERT INTO hash_lookup (tip_hash, lookup_type, resolved_value)
                VALUES (%s, %s, %s)
                ON CONFLICT (tip_hash, lookup_type) 
                DO UPDATE SET resolved_value = EXCLUDED.resolved_value, updated_at = CURRENT_TIMESTAMP
                """,
                (tip_hash, lookup_type, resolved_value)
            )
            
            self.db_manager.execute_update(
                """
                UPDATE unknown_hashes
                SET resolved_at = CURRENT_TIMESTAMP, resolved_value = %s
                WHERE tip_hash = %s AND lookup_type = %s AND resolved_at IS NULL
                """,
                (resolved_value, tip_hash, lookup_type)
            )
            
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
                if (tip_hash, 'unknown') in self._cache:
                    value = self._cache.pop((tip_hash, 'unknown'))
                    self._cache[(tip_hash, normalised_type)] = value
                logger.debug(f"Updated lookup_type: {tip_hash[:16]}... from unknown to {normalised_type}")
                
        except Exception as e:
            logger.debug(f"Could not update lookup_type for {tip_hash[:16]}...: {e}")

    def get_by_type(self, lookup_type: str) -> list[dict]:
            """
            Get all hash entries for a specific lookup type.
            
            Args:
                lookup_type: The type of entity to list (e.g., 'vehicle', 'trailer')
                
            Returns:
                List of dictionaries containing hash details with keys:
                'resolved_value', 'source_type', 'tip_hash'
            """
            query = """
                SELECT resolved_value, source_type, tip_hash
                FROM hash_lookup
                WHERE lookup_type = %s
                ORDER BY resolved_value ASC
            """
            
            try:
                return self.db_manager.execute_query_dict(query, (lookup_type,))
            except Exception as e:
                # Use the class logger if available, otherwise fallback
                if hasattr(self, 'logger'):
                    self.logger.error(f"Failed to get hashes by type {lookup_type}: {e}")
                else:
                    logging.error(f"Failed to get hashes by type {lookup_type}: {e}")
                return []
    
    def get_statistics(self) -> Dict[str, Dict[str, int]]:
        """Get statistics about known and unknown hashes by type"""
        stats = {}
        
        known_query = """
            SELECT lookup_type, COUNT(*) as count 
            FROM hash_lookup 
            GROUP BY lookup_type
        """
        known_results = self.db_manager.execute_query_dict(known_query)
        
        unknown_query = """
            SELECT lookup_type, COUNT(*) as count 
            FROM unknown_hashes 
            WHERE resolved_at IS NULL
            GROUP BY lookup_type
        """
        unknown_results = self.db_manager.execute_query_dict(unknown_query)
        
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
                    '',
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
    
    def import_hashes_from_csv(self, lookup_type: str, csv_path: Path, 
                               source: str = 'manual_import') -> Tuple[int, int, int]:
        """
        Import hashes from CSV file with specified lookup type
        
        Args:
            lookup_type: Type of lookup (vehicle, trailer, department, team)
            csv_path: Path to CSV file
            source: Source identifier for tracking (unused, kept for API compatibility)
            
        Returns:
            Tuple of (imported_count, duplicate_count, error_count)
        """
        if not csv_path.exists():
            raise HashLookupError(f"CSV file not found: {csv_path}")
        
        logger.info(f"Importing {lookup_type} hashes from {csv_path}")
        
        imported_count = 0
        duplicate_count = 0
        error_count = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                if not reader.fieldnames:
                    raise HashLookupError("CSV file is empty or has no headers")
                
                tip_col = 'TIP' if 'TIP' in reader.fieldnames else 'tip_hash'
                value_col = 'VALUE' if 'VALUE' in reader.fieldnames else 'resolved_value'
                
                if tip_col not in reader.fieldnames or value_col not in reader.fieldnames:
                    raise HashLookupError(
                        f"CSV must contain '{tip_col}' and '{value_col}' columns. "
                        f"Found: {reader.fieldnames}"
                    )
                
                hashes_to_import: List[Tuple[str, str]] = []
                
                for row in reader:
                    tip_hash = row[tip_col].strip()
                    resolved_value = row[value_col].strip()
                    
                    if not tip_hash or not resolved_value:
                        error_count += 1
                        continue
                    
                    hashes_to_import.append((tip_hash, resolved_value))
                
                if not hashes_to_import:
                    logger.warning("No valid hashes found in CSV")
                    return 0, 0, error_count
                
                tip_hashes = [h[0] for h in hashes_to_import]
                placeholders = ', '.join(['%s'] * len(tip_hashes))
                
                existing_results = self.db_manager.execute_query_dict(
                    f"""
                    SELECT tip_hash FROM hash_lookup 
                    WHERE tip_hash IN ({placeholders}) AND lookup_type = %s
                    """,
                    tuple(tip_hashes) + (lookup_type,)
                )
                existing_hashes = {r['tip_hash'] for r in existing_results}
                
                for tip_hash, resolved_value in hashes_to_import:
                    try:
                        if tip_hash in existing_hashes:
                            self.db_manager.execute_update(
                                """
                                UPDATE hash_lookup 
                                SET resolved_value = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE tip_hash = %s AND lookup_type = %s
                                """,
                                (resolved_value, tip_hash, lookup_type)
                            )
                            duplicate_count += 1
                        else:
                            self.db_manager.execute_update(
                                """
                                INSERT INTO hash_lookup (tip_hash, lookup_type, resolved_value)
                                VALUES (%s, %s, %s)
                                """,
                                (tip_hash, lookup_type, resolved_value)
                            )
                            imported_count += 1
                        
                        self._cache[(tip_hash, lookup_type)] = resolved_value
                        
                        self.db_manager.execute_update(
                            """
                            UPDATE unknown_hashes
                            SET resolved_at = CURRENT_TIMESTAMP, resolved_value = %s
                            WHERE tip_hash = %s AND lookup_type = %s AND resolved_at IS NULL
                            """,
                            (resolved_value, tip_hash, lookup_type)
                        )
                        
                    except Exception as e:
                        logger.warning(f"Could not import hash {tip_hash[:16]}...: {e}")
                        error_count += 1
                
                logger.info(
                    f"Import complete: {imported_count} imported, "
                    f"{duplicate_count} duplicates/updated, {error_count} errors"
                )
                return imported_count, duplicate_count, error_count
                
        except HashLookupError:
            raise
        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            raise HashLookupError(f"Import failed: {e}")


if __name__ == "__main__":
    import sys
    
    # Test type detection
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    _detector.load(config_path)
    
    test_values = [
        ('MB26', 'vehicle'),
        ('D27', 'vehicle'),
        ('T107', 'trailer'),
        ('TL149', 'trailer'),
        ('TLD250', 'trailer'),
        ('Steel Delivery', 'team'),
        ('Air Liquide Packaged - Drivers', 'team'),
        ('Metro Distribution - Admin', 'team'),
        ('LH Yard - Team', 'team'),
        ('F52', 'vehicle'),
        ('RC91', 'vehicle'),
        ('TSP304', 'trailer'),
        ('Rentco', 'unknown'),
        ('CBH', 'unknown'),
    ]
    
    print("Hash Type Detection Test:")
    print("-" * 60)
    correct = 0
    total = len(test_values)
    
    for value, expected in test_values:
        detected = _detector.detect_type(value)
        status = 'OK' if detected == expected else 'WRONG'
        if detected == expected:
            correct += 1
        print(f"{value:35} -> {detected:12} (expected: {expected:10}) [{status}]")
    
    print()
    print(f"Result: {correct}/{total} correct")
