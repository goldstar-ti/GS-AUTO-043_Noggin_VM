from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, DatabaseConnectionError
import logging

config: ConfigLoader = ConfigLoader(
    'config/base_config.ini',
    'config/load_compliance_check_config.ini'
)

logger_manager: LoggerManager = LoggerManager(config, script_name='test_database')
logger_manager.configure_application_logger()

logger: logging.Logger = logging.getLogger(__name__)

try:
    logger.info("Initialising database connection manager...")
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
    
    logger.info("Testing basic query...")
    version: list = db_manager.execute_query("SELECT version()")
    logger.info(f"PostgreSQL version: {version[0][0]}")
    
    logger.info("Testing dictionary query...")
    tables: list = db_manager.execute_query_dict(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    )
    logger.info(f"Found {len(tables)} tables in public schema:")
    for row in tables:
        logger.info(f"  - {row['table_name']}")
    
    logger.info("Testing context manager...")
    with db_manager.get_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM noggin_data")
        count = cur.fetchone()[0]
        logger.info(f"Records in noggin_data: {count}")
    
    logger.info("Testing transaction...")
    test_queries = [
        ("INSERT INTO noggin_data (tip, object_type, processing_status) VALUES (%s, %s, %s)", 
         ('test_tip_stage3', 'Driver 360', 'pending')),
    ]
    success: bool = db_manager.execute_transaction(test_queries)
    logger.info(f"Transaction success: {success}")
    
    logger.info("Cleaning up test data...")
    deleted: int = db_manager.execute_update("DELETE FROM noggin_data WHERE tip = %s", ('test_tip_stage3',))
    logger.info(f"Deleted {deleted} test records")
    
    logger.info("✓ All database tests passed")
    
except DatabaseConnectionError as e:
    logger.error(f"Database connection error: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
finally:
    if 'db_manager' in locals():
        db_manager.close_all()