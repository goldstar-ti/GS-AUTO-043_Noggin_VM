from common import ConfigLoader, ConfigurationError, LoggerManager
from common import UNKNOWN_TEXT

try:
    config = ConfigLoader(
        'config/base_config.ini',
        'config/load_compliance_check_config.ini'
    )
    print(f"ConfigLoader imported successfully.\nPostgreSQL config:{config.get_postgresql_config()}")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except ImportError as e:
    print(f"Import error: {e}")