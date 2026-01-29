"""
Configuration Loader Module

Handles loading and merging of INI-based configuration files for the Noggin
data processing pipeline. Supports a base configuration with object-type-specific
overrides.

Key features:
- Multi-file configuration merging (base + specific)
- Type-safe accessors (get, getint, getfloat, getboolean)
- Case-sensitive option names for API field mappings
- Field mapping parser for database column definitions
- Template content extraction for report generation

Usage:
    config = ConfigLoader('config/base_config.ini', 'config/lcd_config.ini')
    db_config = config.get_postgresql_config()
    field_mappings = config.get_field_mappings()
"""

import configparser
from pathlib import Path
from typing import Any, Optional, Tuple
import logging

logger: logging.Logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required values."""
    pass


class ConfigLoader:
    """
    Loads and manages INI-based configuration with support for base and
    object-type-specific config file merging.
    
    The specific config takes precedence over the base config for overlapping
    sections and keys.
    """
    
    def __init__(self, base_config_path: str, specific_config_path: Optional[str] = None) -> None:
        """
        Initialise the configuration loader.
        
        Args:
            base_config_path: Path to the base configuration file (required)
            specific_config_path: Path to object-type-specific config (optional)
            
        Raises:
            ConfigurationError: If required config files are missing or invalid
        """
        # Create ConfigParser instances with case-sensitive option names.
        # This is critical for the [fields] section where API field names like
        # 'inspectedBy' must retain their camelCase format to match the API response.
        self.base_config: configparser.ConfigParser = configparser.ConfigParser()
        self.base_config.optionxform = str  # Preserve case for option names
        
        self.specific_config: configparser.ConfigParser = configparser.ConfigParser()
        self.specific_config.optionxform = str  # Preserve case for option names
        
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
        """
        Validate that all required sections and keys exist in the base config.
        
        Raises:
            ConfigurationError: If required sections or keys are missing
        """
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
    
    def get(self, section: str, key: str, fallback: Optional[str] = None, 
            from_specific: bool = False) -> str:
        """
        Get a string configuration value.
        
        Args:
            section: Configuration section name
            key: Configuration key within the section
            fallback: Default value if key not found
            from_specific: If True, check specific config first
            
        Returns:
            Configuration value as string
        """
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if from_specific and not config.has_option(section, key):
            config = self.base_config
        
        try:
            value: str = config.get(section, key, fallback=fallback)
        except configparser.InterpolationSyntaxError:
            # If standard parsing fails (e.g. date format like "%d %b %Y"), 
            # retry getting the raw value without interpolation
            logger.debug(f"Interpolation failed for [{section}] {key}, retrieving raw value")
            value: str = config.get(section, key, fallback=fallback, raw=True)
            
        return value

    def getint(self, section: str, key: str, fallback: Optional[int] = None, 
               from_specific: bool = False) -> int:
        """Get an integer configuration value."""
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if from_specific and not config.has_option(section, key):
            config = self.base_config
        
        value: int = config.getint(section, key, fallback=fallback)
        return value
    
    def getfloat(self, section: str, key: str, fallback: Optional[float] = None, 
                 from_specific: bool = False) -> float:
        """Get a float configuration value."""
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if from_specific and not config.has_option(section, key):
            config = self.base_config
        
        value: float = config.getfloat(section, key, fallback=fallback)
        return value
    
    def getboolean(self, section: str, key: str, fallback: Optional[bool] = None, 
                   from_specific: bool = False) -> bool:
        """Get a boolean configuration value."""
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if from_specific and not config.has_option(section, key):
            config = self.base_config
        
        value: bool = config.getboolean(section, key, fallback=fallback)
        return value
    
    def get_section(self, section: str, from_specific: bool = False) -> dict[str, str]:
        """
        Get all key-value pairs from a configuration section.
        
        Args:
            section: Section name to retrieve
            from_specific: If True, use specific config
            
        Returns:
            Dictionary of section contents (preserves key case)
        """
        config: configparser.ConfigParser = self.specific_config if from_specific else self.base_config
        
        if not config.has_section(section):
            return {}
        
        return dict(config.items(section))
    
    def get_postgresql_config(self) -> dict[str, Any]:
        """Get PostgreSQL connection configuration."""
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
        """Get HTTP headers for API requests."""
        return {
            'en-namespace': self.get('api', 'namespace'),
            'authorization': f"Bearer {self.get('api', 'bearer_token')}"
        }
    
    def get_object_type_config(self) -> dict[str, str]:
        """
        Get object type configuration from the specific config file.
        
        The id_field format is: "apiFieldName:dbColumnName:fieldType"
        e.g., "lcdInspectionId:noggin_reference:string"
        
        Returns:
            Dictionary containing object type metadata and field mappings
        """
        # id_field format: "apiFieldName:dbColumnName:fieldType"
        id_field_raw = self.get('fields', 'id_field', from_specific=True)
        
        # Parse the id_field to extract components
        id_parts = id_field_raw.split(':') if id_field_raw else ['', '', '']
        api_id_field = id_parts[0] if len(id_parts) > 0 else ''
        db_id_column = id_parts[1] if len(id_parts) > 1 else ''
        
        return {
            'endpoint': self.get('api', 'endpoint', from_specific=True),
            'object_type': self.get('api', 'object_type', from_specific=True),
            'abbreviation': self.get('object_type', 'abbreviation', from_specific=True),
            'full_name': self.get('object_type', 'full_name', from_specific=True),
            'inspection_type': self.get('object_type', 'inspection_type', from_specific=True, fallback='Inspection'),
            'id_field': id_field_raw,
            'api_id_field': api_id_field,
            'db_id_column': db_id_column,
        }
    
    def get_field_mappings(self) -> dict[str, tuple[str, str, Optional[str]]]:
        """
        Parse [fields] section and return field mappings.
        
        Config format: api_field = db_column:field_type[:hash_type]
        
        Example config entries:
            inspectedBy = inspected_by:string
            vehicle = vehicle_hash:hash:vehicle
            date = inspection_date:datetime
        
        Returns:
            Dictionary mapping API field names (preserving camelCase) to tuples of:
            (db_column, field_type, hash_type or None)
            
        Note:
            Case sensitivity is preserved for API field names. This is essential
            because the Noggin API returns camelCase field names (e.g., 'inspectedBy')
            and the mapping must match exactly.
        """
        fields_section = self.get_section('fields', from_specific=True)
        mappings: dict[str, tuple[str, str, Optional[str]]] = {}
        
        # Skip meta fields (id_field, date_field)
        skip_keys = {'id_field', 'date_field'}
        
        for api_field, value in fields_section.items():
            if api_field in skip_keys:
                continue
            
            parts = value.split(':')
            if len(parts) < 2:
                logger.warning(f"Invalid field mapping for {api_field}: {value}")
                continue
            
            db_column = parts[0]
            field_type = parts[1]
            hash_type = parts[2] if len(parts) > 2 else None
            
            mappings[api_field] = (db_column, field_type, hash_type)
        
        logger.debug(f"Loaded {len(mappings)} field mappings")
        return mappings
    
    def get_output_patterns(self) -> dict[str, str]:
        """Get output patterns from [output] section."""
        return self.get_section('output', from_specific=True)
    
    def get_template_content(self) -> Optional[str]:
        """
        Get report template content from [template] section.
        
        Returns:
            Template string if configured, None otherwise
        """
        if self.specific_config.has_option('template', 'content'):
            return self.specific_config.get('template', 'content')
        return None


if __name__ == "__main__":
    # Test the configuration loader
    try:
        config: ConfigLoader = ConfigLoader(
            'config/base_config.ini',
            'config/load_compliance_check_driver_loader_config.ini'
        )
        
        print("PostgreSQL Config:", config.get_postgresql_config())
        print("\nAPI Headers:", config.get_api_headers())
        print("\nObject Type Config:", config.get_object_type_config())
        
        print("\nField Mappings (showing case preservation):")
        for api_field, (db_col, field_type, hash_type) in config.get_field_mappings().items():
            hash_info = f" -> {hash_type}" if hash_type else ""
            print(f"  {api_field} -> {db_col} ({field_type}{hash_info})")
        
    except ConfigurationError as e:
        print(f"Configuration error: {e}")