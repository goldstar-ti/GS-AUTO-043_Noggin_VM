from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, HashManager
from common import UNKNOWN_TEXT
from pathlib import Path
import logging

config: ConfigLoader = ConfigLoader(
    'config/base_config.ini',
    'config/load_compliance_check_driver_loader_config.ini'
)

logger_manager: LoggerManager = LoggerManager(config, script_name='test_hash_manager')
logger_manager.configure_application_logger()

logger: logging.Logger = logging.getLogger(__name__)

try:
    logger.info("Initialising hash manager...")
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
    hash_manager: HashManager = HashManager(config, db_manager)
    
    lookup_table_path: str = 'lookup_table.csv'
    if Path(lookup_table_path).exists():
        logger.info(f"Migrating hash lookups from {lookup_table_path}")
        imported, skipped = hash_manager.migrate_lookup_table_from_csv(lookup_table_path)
        logger.info(f"Migration complete: {imported} imported, {skipped} skipped")
    else:
        logger.warning(f"lookup_table.csv not found at {lookup_table_path}")
    
    logger.info("Testing hash lookup...")
    test_hash: str = "9d28a0b2a601d53eddcd10b433fd9716a172193e425cc964d263507be3be578e"
    result: str = hash_manager.lookup_hash('vehicle', test_hash, 'test_tip', 'LCD-TEST')
    logger.info(f"Lookup result: {result}")
    
    logger.info("Checking unknown hashes...")
    unknown = hash_manager.get_unknown_hashes(resolved=False)
    logger.info(f"Unknown hashes: {len(unknown)}")
    
    logger.info("✓ All hash manager tests passed")
    
except Exception as e:
    logger.error(f"Test failed: {e}", exc_info=True)
finally:
    if 'db_manager' in locals():
        db_manager.close_all()