import configparser
from pathlib import Path
from typing import Any, Optional
import logging

logger: logging.Logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    pass

class ConfigLoader:
    def __init__(self, base_config_path: str, specific_config_path: Optional[str] = None) -> None:
        self.base_config: configparser.ConfigParser = configparser.ConfigParser()
        self.specific_config: configparser.ConfigParser = configparser.ConfigParser()
        
        if not Path(base_config_path).exists():
            raise ConfigurationError(f"Base config not found: {base_config_path}")
        
        self.base_config.read(base_config_path)
        logger.info(f"Loaded base configuration from {base_config_path}")
        
        if specific_config_path:
            if not Path(specific_config_path).exists():
                raise ConfigurationError(f"Specific config not found: {specific_config_path}")
            
            self.specific_config.read(specific_config_path)
            logger.info(f"Loaded specific configuration from {specific_config_path}")
        
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        required_base_sections: dict[str, list[str]] = {
            'postgresql': ['host', 'port', 'database', 'user', 'password'],
            'paths': ['base_output_path', 'base_log_path', 'input_folder_path'],
            'api': ['base_url', 'media_service_url', 'namespace', 'bearer_token'],
            'processing': ['max_api_retries', 'api_timeout'],
            'retry': ['max_retry_attempts', 'retry_backoff_multiplier']
        }
        
        for section, keys in required_base_sections.items():
            if not self.base_config.has_section(section):
                raise ConfigurationError(f"Missing required section: [{section}]")
            
            for key in keys:
                if not self.base_config.has_option(section, key):
                    raise ConfigurationError(f"Missing required key: [{section}] {key}")
        
        logger.info("Configuration validation passed")
    
    def get(self, section: str, key: str, fallback: Optional[str] = None, from_specific: bool = False) -> str:
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if from_specific and not config.has_option(section, key):
            config = self.base_config
        
        value: str = config.get(section, key, fallback=fallback)
        return value
    
    def getint(self, section: str, key: str, fallback: Optional[int] = None, from_specific: bool = False) -> int:
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if from_specific and not config.has_option(section, key):
            config = self.base_config
        
        value: int = config.getint(section, key, fallback=fallback)
        return value
    
    def getfloat(self, section: str, key: str, fallback: Optional[float] = None, from_specific: bool = False) -> float:
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if from_specific and not config.has_option(section, key):
            config = self.base_config
        
        value: float = config.getfloat(section, key, fallback=fallback)
        return value
    
    def getboolean(self, section: str, key: str, fallback: Optional[bool] = None, from_specific: bool = False) -> bool:
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if from_specific and not config.has_option(section, key):
            config = self.base_config
        
        value: bool = config.getboolean(section, key, fallback=fallback)
        return value
    
    def get_section(self, section: str, from_specific: bool = False) -> dict[str, str]:
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if not config.has_section(section):
            return {}
        
        return dict(config.items(section))
    
    def get_postgresql_config(self) -> dict[str, Any]:
        return {
            'host': self.get('postgresql', 'host'),
            'port': self.getint('postgresql', 'port'),
            'database': self.get('postgresql', 'database'),
            'user': self.get('postgresql', 'user'),
            'password': self.get('postgresql', 'password'),
            'schema': self.get('postgresql', 'schema', fallback='noggin_schema'),
            'minconn': self.getint('postgresql', 'pool_min_connections', fallback=2),
            'maxconn': self.getint('postgresql', 'pool_max_connections', fallback=10)
        }
    
    def get_api_headers(self) -> dict[str, str]:
        return {
            'en-namespace': self.get('api', 'namespace'),
            'authorization': f"Bearer {self.get('api', 'bearer_token')}"
        }
    
    def get_object_type_config(self) -> dict[str, str]:
        return {
            'endpoint': self.get('api', 'endpoint', from_specific=True),
            'object_type': self.get('api', 'object_type', from_specific=True),
            'id_column': self.get('object_detection', 'id_column', from_specific=True)
        }

if __name__ == "__main__":
    try:
        config: ConfigLoader = ConfigLoader(
            'config/base_config.ini',
            'config/load_compliance_check_driver_loader_config.ini'
        )
        
        print("PostgreSQL Config:", config.get_postgresql_config())
        print("API Headers:", config.get_api_headers())
        print("Object Type Config:", config.get_object_type_config())
        
    except ConfigurationError as e:
        print(f"Configuration error: {e}")