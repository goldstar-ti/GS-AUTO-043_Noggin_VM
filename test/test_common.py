from common import ConfigLoader, ConfigurationError, LoggerManager
from common import UNKNOWN_TEXT

try:
    config = ConfigLoader(
        'config/base.ini',
        'config/LCD.ini'
    )
    print(f"ConfigLoader imported successfully.\nPostgreSQL config:{config.get_postgresql_config()}")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except ImportError as e:
    print(f"Import error: {e}")