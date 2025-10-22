from common import ConfigLoader, ConfigurationError, LoggerManager

try:
    config = ConfigLoader(
        'config/base_config.ini',
        'config/lcc_config.ini'
    )
    print("✓ ConfigLoader imported successfully")
    print("✓ PostgreSQL config:", config.get_postgresql_config())
except ConfigurationError as e:
    print(f"✗ Configuration error: {e}")
except ImportError as e:
    print(f"✗ Import error: {e}")