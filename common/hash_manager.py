"""
Hash Manager - Runtime hash lookup operations

Provides in-memory cached lookups for resolving Noggin hashes to human-readable values.
The hash_lookup table is populated by hash_lookup_sync.py from weekly Noggin exports.

This module is used by processors during data extraction to resolve vehicle, trailer,
team, and department hashes to their display names.
"""

from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List, Tuple

logger: logging.Logger = logging.getLogger(__name__)


class HashLookupError(Exception):
    """Raised when hash lookup operations fail"""
    pass


class HashManager:
    """
    Manages hash lookups with in-memory caching for performance.
    
    The cache is loaded on first lookup and provides O(1) access to resolved values.
    Cache invalidation happens automatically when the sync script runs weekly.
    """
    
    def __init__(self, config: 'ConfigLoader', db_manager: 'DatabaseConnectionManager') -> None:
        """
        Initialise hash manager
        
        Args:
            config: ConfigLoader instance
            db_manager: DatabaseConnectionManager instance
        """
        self.config: 'ConfigLoader' = config
        self.db_manager: 'DatabaseConnectionManager' = db_manager
        
        # Cache structure: {tip_hash: {'lookup_type': str, 'resolved_value': str, 'source_type': str}}
        self._cache: Dict[str, Dict[str, str]] = {}
        self._cache_loaded: bool = False
    
    def _load_cache(self) -> None:
        """Load hash lookups into memory cache for performance"""
        if self._cache_loaded:
            return
        
        try:
            results: List[Dict[str, Any]] = self.db_manager.execute_query_dict(
                "SELECT tip_hash, lookup_type, resolved_value, source_type FROM hash_lookup"
            )
            
            for row in results:
                self._cache[row['tip_hash']] = {
                    'lookup_type': row['lookup_type'],
                    'resolved_value': row['resolved_value'],
                    'source_type': row['source_type']
                }
            
            self._cache_loaded = True
            logger.info(f"Loaded {len(self._cache)} hash lookups into cache")
            
        except Exception as e:
            logger.error(f"Failed to load hash lookup cache: {e}")
            raise HashLookupError(f"Cache load failed: {e}")
    
    def invalidate_cache(self) -> None:
        """
        Invalidate the cache to force reload on next lookup.
        Call this after running hash_lookup_sync.py.
        """
        self._cache.clear()
        self._cache_loaded = False
        logger.info("Hash lookup cache invalidated")
    
    def lookup_hash(self, tip_hash: str, expected_type: Optional[str] = None) -> Optional[str]:
        """
        Lookup hash and return resolved value
        
        Args:
            tip_hash: Hash value to resolve
            expected_type: Expected lookup_type for validation (optional)
            
        Returns:
            Resolved value or None if not found
        """
        if not tip_hash:
            return None
        
        if not self._cache_loaded:
            self._load_cache()
        
        cached = self._cache.get(tip_hash)
        
        if not cached:
            logger.debug(f"Hash not found: {tip_hash[:16]}...")
            return None
        
        # Optional type validation
        if expected_type and cached['lookup_type'] != expected_type:
            logger.warning(
                f"Hash {tip_hash[:16]}... expected type '{expected_type}' "
                f"but found '{cached['lookup_type']}'"
            )
        
        return cached['resolved_value']
    
    def lookup_hash_with_metadata(self, tip_hash: str) -> Optional[Dict[str, str]]:
        """
        Lookup hash and return full metadata
        
        Args:
            tip_hash: Hash value to resolve
            
        Returns:
            Dictionary with lookup_type, resolved_value, source_type, or None if not found
        """
        if not tip_hash:
            return None
        
        if not self._cache_loaded:
            self._load_cache()
        
        return self._cache.get(tip_hash)
    
    def get_lookup_type(self, tip_hash: str) -> Optional[str]:
        """
        Get the lookup_type for a hash
        
        Args:
            tip_hash: Hash value
            
        Returns:
            Lookup type (vehicle, trailer, team, department, uhf) or None
        """
        if not tip_hash:
            return None
        
        if not self._cache_loaded:
            self._load_cache()
        
        cached = self._cache.get(tip_hash)
        return cached['lookup_type'] if cached else None
    
    def search_hash(self, search_value: str) -> List[Dict[str, Any]]:
        """
        Search for hashes by resolved value (case-insensitive)
        
        Args:
            search_value: Value to search for (partial match supported)
            
        Returns:
            List of matching hash lookups with full details
        """
        results: List[Dict[str, Any]] = self.db_manager.execute_query_dict(
            """
            SELECT tip_hash, lookup_type, resolved_value, source_type, created_at, updated_at
            FROM hash_lookup
            WHERE resolved_value ILIKE %s
            ORDER BY lookup_type, resolved_value
            """,
            (f"%{search_value}%",)
        )
        return results
    
    def get_by_type(self, lookup_type: str) -> List[Dict[str, Any]]:
        """
        Get all hashes of a specific lookup_type
        
        Args:
            lookup_type: Type to filter by (vehicle, trailer, team, department, uhf)
            
        Returns:
            List of hash lookups
        """
        results: List[Dict[str, Any]] = self.db_manager.execute_query_dict(
            """
            SELECT tip_hash, resolved_value, source_type
            FROM hash_lookup
            WHERE lookup_type = %s
            ORDER BY resolved_value
            """,
            (lookup_type,)
        )
        return results
    
    def get_by_source_type(self, source_type: str) -> List[Dict[str, Any]]:
        """
        Get all hashes of a specific source_type (e.g., PrimeMover, Trailer, Team)
        
        Args:
            source_type: Noggin's original type classification
            
        Returns:
            List of hash lookups
        """
        results: List[Dict[str, Any]] = self.db_manager.execute_query_dict(
            """
            SELECT tip_hash, lookup_type, resolved_value
            FROM hash_lookup
            WHERE source_type = %s
            ORDER BY resolved_value
            """,
            (source_type,)
        )
        return results
    
    def get_hash_statistics(self) -> Dict[str, Dict[str, int]]:
        """
        Get statistics about hash lookups grouped by type
        
        Returns:
            Dictionary with counts by lookup_type and source_type
        """
        stats: Dict[str, Any] = {}
        
        # Count by lookup_type
        type_results = self.db_manager.execute_query_dict(
            """
            SELECT lookup_type, COUNT(*) as count 
            FROM hash_lookup 
            GROUP BY lookup_type
            ORDER BY lookup_type
            """
        )
        
        for row in type_results:
            stats[row['lookup_type']] = {'count': row['count']}
        
        # Count by source_type
        source_results = self.db_manager.execute_query_dict(
            """
            SELECT source_type, COUNT(*) as count
            FROM hash_lookup
            WHERE source_type IS NOT NULL
            GROUP BY source_type
            ORDER BY source_type
            """
        )
        
        stats['by_source_type'] = {row['source_type']: row['count'] for row in source_results}
        
        # Total
        total_result = self.db_manager.execute_query_dict(
            "SELECT COUNT(*) as count FROM hash_lookup"
        )
        stats['total'] = total_result[0]['count'] if total_result else 0
        
        return stats
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring
        
        Returns:
            Dictionary with cache status and size
        """
        return {
            'cache_loaded': self._cache_loaded,
            'cache_size': len(self._cache),
            'memory_entries': len(self._cache) if self._cache_loaded else 0
        }


if __name__ == "__main__":
    from config import ConfigLoader
    from database import DatabaseConnectionManager
    from logger import LoggerManager
    
    try:
        config: ConfigLoader = ConfigLoader(
            'config/base_config.ini',
            'config/load_compliance_check_config.ini'
        )
        
        logger_manager: LoggerManager = LoggerManager(config, script_name='test_hash_manager')
        logger_manager.configure_application_logger()
        
        db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
        hash_manager: HashManager = HashManager(config, db_manager)
        
        # Test lookup
        test_hash = "02409bd3dd8355a53b3cef56e0eb6440b653bfad9579e7e602528db25cfbdc34"
        result = hash_manager.lookup_hash(test_hash)
        print(f"Lookup test: {test_hash[:16]}... -> {result}")
        
        # Test metadata lookup
        metadata = hash_manager.lookup_hash_with_metadata(test_hash)
        print(f"Metadata: {metadata}")
        
        # Test search
        search_results = hash_manager.search_hash("MB")
        print(f"Search 'MB': found {len(search_results)} results")
        
        # Test statistics
        stats = hash_manager.get_hash_statistics()
        print(f"Statistics: {stats}")
        
        # Cache stats
        cache_stats = hash_manager.get_cache_stats()
        print(f"Cache stats: {cache_stats}")
        
        print("\nHash manager tests passed")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()