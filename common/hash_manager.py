from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import csv
import pandas as pd

logger: logging.Logger = logging.getLogger(__name__)


class HashLookupError(Exception):
    """Raised when hash lookup operations fail"""
    pass


class HashManager:
    """Manages hash lookups and resolution for Noggin data"""
    
    def __init__(self, config: 'ConfigLoader', db_manager: 'DatabaseConnectionManager') -> None:
        """
        Initialise hash manager
        
        Args:
            config: ConfigLoader instance
            db_manager: DatabaseConnectionManager instance
        """
        self.config: 'ConfigLoader' = config
        self.db_manager: 'DatabaseConnectionManager' = db_manager
        self.log_path: Path = Path(config.get('paths', 'base_log_path'))
        self.log_path.mkdir(parents=True, exist_ok=True)
        
        self._cache: Dict[Tuple[str, str], str] = {}
        self._cache_loaded: bool = False
    
    def _load_cache(self) -> None:
        """Load hash lookups into memory cache for performance"""
        if self._cache_loaded:
            return
        
        try:
            results: List[Tuple[Any, ...]] = self.db_manager.execute_query(
                "SELECT tip_hash, lookup_type, resolved_value FROM hash_lookup"
            )
            
            for tip_hash, lookup_type, resolved_value in results:
                self._cache[(tip_hash, lookup_type)] = resolved_value
            
            self._cache_loaded = True
            logger.info(f"Loaded {len(self._cache)} hash lookups into cache")
            
        except Exception as e:
            logger.error(f"Failed to load hash lookup cache: {e}")
            raise HashLookupError(f"Cache load failed: {e}")
    
    def lookup_hash(self, lookup_type: str, tip_hash: str, tip_value: Optional[str] = None, 
                   lcd_inspection_id: Optional[str] = None) -> str:
        """
        Lookup hash and return resolved value
        
        Args:
            lookup_type: Type of lookup (vehicle, trailer, department, team)
            tip_hash: Hash value to resolve
            tip_value: TIP value for logging unknown hashes (optional)
            lcd_inspection_id: LCD Inspection ID for logging (optional)
            
        Returns:
            Resolved value or "Unknown (hash)" if not found
        """
        if not self._cache_loaded:
            self._load_cache()
        
        cache_key: Tuple[str, str] = (tip_hash, lookup_type)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        self._log_unknown_hash(lookup_type, tip_hash, tip_value, lcd_inspection_id)
        
        try:
            self.db_manager.execute_update(
                """
                INSERT INTO hash_lookup_unknown (tip_hash, lookup_type, first_encountered)
                VALUES (%s, %s, %s)
                ON CONFLICT (tip_hash, lookup_type) DO NOTHING
                """,
                (tip_hash, lookup_type, datetime.now())
            )
        except Exception as e:
            logger.warning(f"Could not insert unknown hash: {e}")
        
        return f"Unknown ({tip_hash})"
    
    def _log_unknown_hash(self, lookup_type: str, tip_hash: str, 
                         tip_value: Optional[str], lcd_inspection_id: Optional[str]) -> None:
        """Log unknown hash to dedicated file"""
        unknown_log_file: Path = self.log_path / 'unknown_hashes.log'
        
        timestamp: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lcd_id: str = lcd_inspection_id or 'UNKNOWN'
        tip: str = tip_value or 'UNKNOWN'
        
        log_entry: str = f"{timestamp} | {lookup_type} | {tip_hash} | {lcd_id} | TIP: {tip}\n"
        
        try:
            with open(unknown_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.warning(f"Could not write to unknown hashes log: {e}")
        
        logger.warning(f"Unknown hash encountered: {lookup_type}={tip_hash}")
    
    def migrate_lookup_table_from_csv(self, csv_file_path: str) -> Tuple[int, int]:
        """
        Migrate hash lookup table from CSV to PostgreSQL
        
        Args:
            csv_file_path: Path to lookup_table.csv
            
        Returns:
            Tuple of (imported_count, skipped_count)
        """
        csv_path: Path = Path(csv_file_path)
        
        if not csv_path.exists():
            raise HashLookupError(f"CSV file not found: {csv_file_path}")

        # use pandas to strip BOM marker added by Excel when saving UTF-8
        df: pd.DataFrame = pd.read_csv(csv_path, encoding='utf-8')
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        imported_count: int = 0
        skipped_count: int = 0
        
        logger.info(f"Migrating hash lookups from {csv_file_path}")

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
                    
                    lookup_type: str = self._detect_lookup_type(tip_hash, resolved_value)
                    
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
                        imported_count += 1
                    except Exception as e:
                        logger.warning(f"Could not import hash {tip_hash}: {e}")
                        skipped_count += 1
            
            self._cache_loaded = False
            
            logger.info(f"Migration complete: {imported_count} imported, {skipped_count} skipped")
            return imported_count, skipped_count
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            raise HashLookupError(f"Migration failed: {e}")
    
    def _detect_lookup_type(self, tip_hash: str, resolved_value: str) -> str:
        """
        Detect lookup type from resolved value pattern
        
        Args:
            tip_hash: Hash value
            resolved_value: Resolved value
            
        Returns:
            Lookup type string
        """
        value_upper: str = resolved_value.upper()
        
        if any(dept in value_upper for dept in ['DRIVERS', 'TRANSPORT', 'WORKSHOP', 'ADMIN']):
            return 'department'
        elif 'TEAM' in value_upper or ' - ' in resolved_value:
            return 'team'
        elif any(c.isdigit() for c in resolved_value) and len(resolved_value) <= 10:
            if resolved_value.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9')):
                return 'vehicle'
        
        return 'unknown'
    
    def resolve_unknown_hash(self, tip_hash: str, lookup_type: str, resolved_value: str) -> bool:
        """
        Manually resolve an unknown hash
        
        Args:
            tip_hash: Hash to resolve
            lookup_type: Type of lookup
            resolved_value: Value to associate with hash
            
        Returns:
            True if successful, False otherwise
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
                UPDATE hash_lookup_unknown
                SET resolved_at = %s, resolved_value = %s
                WHERE tip_hash = %s AND lookup_type = %s
                """,
                (datetime.now(), resolved_value, tip_hash, lookup_type)
            )
            
            if (tip_hash, lookup_type) in self._cache:
                del self._cache[(tip_hash, lookup_type)]
            
            self._cache[(tip_hash, lookup_type)] = resolved_value
            
            logger.info(f"Resolved hash: {lookup_type}={tip_hash} -> {resolved_value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve hash: {e}")
            return False
    
    def get_unknown_hashes(self, resolved: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of unknown hashes
        
        Args:
            resolved: If True, get resolved hashes. If False, get unresolved hashes.
            
        Returns:
            List of dictionaries with unknown hash information
        """
        if resolved:
            query: str = """
                SELECT tip_hash, lookup_type, first_encountered, resolved_at, resolved_value
                FROM hash_lookup_unknown
                WHERE resolved_at IS NOT NULL
                ORDER BY resolved_at DESC
            """
        else:
            query = """
                SELECT tip_hash, lookup_type, first_encountered
                FROM hash_lookup_unknown
                WHERE resolved_at IS NULL
                ORDER BY first_encountered DESC
            """
        
        results: List[Dict[str, Any]] = self.db_manager.execute_query_dict(query)
        return results
    
    def search_hash(self, search_value: str) -> List[Dict[str, Any]]:
        """
        Search for hashes by resolved value
        
        Args:
            search_value: Value to search for
            
        Returns:
            List of matching hash lookups
        """
        results: List[Dict[str, Any]] = self.db_manager.execute_query_dict(
            """
            SELECT tip_hash, lookup_type, resolved_value, created_at, updated_at
            FROM hash_lookup
            WHERE resolved_value ILIKE %s
            ORDER BY resolved_value
            """,
            (f"%{search_value}%",)
        )
        return results


if __name__ == "__main__":
    from .config import ConfigLoader
    from .database import DatabaseConnectionManager
    from .logger import LoggerManager
    
    try:
        config: ConfigLoader = ConfigLoader(
            '../config/base_config.ini',
            '../config/load_compliance_check_config.ini'
        )
        
        logger_manager: LoggerManager = LoggerManager(config, script_name='test_hash_manager')
        logger_manager.configure_application_logger()
        
        db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
        hash_manager: HashManager = HashManager(config, db_manager)
        
        lookup_table_path: str = '../lookup_table.csv'
        if Path(lookup_table_path).exists():
            imported, skipped = hash_manager.migrate_lookup_table_from_csv(lookup_table_path)
            print(f"✓ Migrated: {imported} imported, {skipped} skipped")
        else:
            print(f"✗ lookup_table.csv not found at {lookup_table_path}")
        
        test_hash: str = "9d28a0b2a601d53eddcd10b433fd9716a172193e425cc964d263507be3be578e"
        result: str = hash_manager.lookup_hash('vehicle', test_hash, 'test_tip', 'LCD-TEST')
        print(f"✓ Lookup test: {result}")
        
        unknown: List[Dict[str, Any]] = hash_manager.get_unknown_hashes(resolved=False)
        print(f"✓ Unknown hashes: {len(unknown)}")
        
        print("\n✓ Hash manager tests passed")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()