"""
Common Utilities Package

Provides shared infrastructure for the Noggin data processing pipeline:

Modules:
  - config: ConfigLoader for loading and managing INI-based configuration
  - logger: LoggerManager for setting up application and script logging
  - database: DatabaseConnectionManager for PostgreSQL connections and queries
  - hash_manager: HashManager for runtime hash-to-text lookups with caching
  - csv_importer: CSVImporter for batch importing CSV files with preview extraction
  - object_types: Object type definitions and detection (LCD, CCC, FPI, etc.)
  - rate_limiter: CircuitBreaker for transient fault handling in API requests

Key Classes:
  - ConfigLoader: Manages multi-file INI configuration merging and type conversion
  - LoggerManager: Configures standardised logging with file rotation
  - DatabaseConnectionManager: Connection pooling and query execution
  - HashManager: In-memory cached hash lookup with search and statistics
  - CSVImporter: Batch CSV import with auto object-type detection and preview extraction
  - CircuitBreaker: Monitors failure rates and fails fast during outages

Global Constants:
  - UNKNOWN_TEXT: Sentinel value for unresolved hashes ('UNKNOWN')

Dependencies:
  - PostgreSQL 13+
  - Python 3.8+
  - psycopg2, python-dotenv, requests

Usage Example:
    from common import ConfigLoader, DatabaseConnectionManager, LoggerManager
    
    config = ConfigLoader('config/base_config.ini', 'config/app_config.ini')
    logger_mgr = LoggerManager(config, script_name='my_script')
    logger_mgr.configure_application_logger()
    
    db_mgr = DatabaseConnectionManager(config)
    results = db_mgr.execute_query('SELECT * FROM my_table LIMIT 10')
"""

from .config import ConfigLoader, ConfigurationError
from .logger import LoggerManager
from .database import DatabaseConnectionManager, DatabaseConnectionError
from .hash_manager import HashManager, HashLookupError
from .csv_importer import CSVImporter, CSVImportError
from .rate_limiter import CircuitBreaker, CircuitBreakerError, CircuitState
from .object_types import ObjectTypeConfig


### GLOBAL CONSTANTS
UNKNOWN_TEXT = "UNKNOWN"

__all__ = [
    'ConfigLoader',
    'ConfigurationError',
    'LoggerManager',
    'DatabaseConnectionManager',
    'DatabaseConnectionError',
    'HashManager',
    'HashLookupError',
    'CSVImporter',
    'CSVImportError',
    'CircuitBreaker',
    'CircuitBreakerError',
    'CircuitState',
    'ObjectTypeConfig'
]