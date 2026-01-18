import configparser
import logging
import os
import re
from typing import List, Dict, Optional

class ConfigManager:
    def __init__(self, base_config_path: str = 'base_config.ini'):
        self.base_config_path = base_config_path
        self.base_config = configparser.ConfigParser()
        self.logger = logging.getLogger(__name__)
        self._load_base_config()
        
        # Mapping Object Types to their config files
        # Assumes these files are in the current working directory or 'config/' folder
        self.object_type_configs = {
            'CCC': 'coupling_compliance_check_config.ini',
            'FPI': 'forklift_prestart_inspection_config.ini',
            'LCS': 'load_compliance_check_supervisor_manager_config.ini',
            'LCD': 'load_compliance_check_driver_loader_config.ini',
            'SO':  'site_observations_config.ini',
            'TA':  'trailer_audits_config.ini'
        }

    def _load_base_config(self):
        """Loads the base configuration for DB and global settings."""
        if not os.path.exists(self.base_config_path):
            self.logger.error(f"Base configuration file not found at: {self.base_config_path}")
            return
        self.base_config.read(self.base_config_path)

    def get_db_config(self) -> Dict[str, str]:
        """
        Retrieves PostgreSQL credentials from base_config.ini.
        """
        db_config = {}
        if self.base_config.has_section('postgresql'):
            section = self.base_config['postgresql']
            db_config['host'] = section.get('host', 'localhost')
            db_config['port'] = section.get('port', '5432')
            db_config['database'] = section.get('database', 'noggin_db')
            db_config['user'] = section.get('user', 'noggin_app')
            db_config['password'] = section.get('password', '')
        return db_config

    def _get_specific_config(self, object_type: str) -> Optional[configparser.ConfigParser]:
        """Helper to load the specific INI file for an object type."""
        filename = self.object_type_configs.get(object_type)
        if not filename:
            self.logger.warning(f"No config file mapped for object type: {object_type}")
            return None

        # Look in current directory or 'config' subdirectory
        candidates = [filename, os.path.join('config', filename)]
        for path in candidates:
            if os.path.exists(path):
                config = configparser.ConfigParser()
                # strict=False allows for potential duplicate keys or loose syntax in templates
                config.read(path)
                return config
        
        self.logger.error(f"Config file {filename} for {object_type} not found.")
        return None

    def get_inspection_type_label(self, object_type: str) -> str:
        """
        Retrieves the 'inspection_type' (e.g., 'Observation', 'Audit') from the config.
        """
        config = self._get_specific_config(object_type)
        if config and config.has_section('object_type'):
            return config.get('object_type', 'inspection_type', fallback=f"{object_type} Details")
        return f"{object_type} Details"

    def _extract_label_from_template(self, content: str, keys_to_find: List[str]) -> str:
        """
        Searches the [template] content block to find the label preceding a tag.
        Handles:
        1. "Label: <tag>"
        2. "Label:\n<tag>" (Multiline)
        """
        if not content:
            return None
        
        for key in keys_to_find:
            escaped_key = re.escape(key)
            # Pattern 1: Inline "Label: <key>"
            # ^\s* -> Start of line, optional whitespace
            # ([^:\r\n<]+?) -> Capture group for label (non-greedy, no colons or newlines)
            # \s*:\s* -> Colon separator
            # .*? -> Any chars (like other tags)
            # <key> -> The target tag
            inline_pattern = r'(?im)^\s*([^:\r\n<]+?)\s*:\s*.*?<' + escaped_key + r'>'
            
            match = re.search(inline_pattern, content)
            if match:
                return match.group(1).strip()

            # Pattern 2: Multiline "Label:\n<key>"
            multiline_pattern = r'(?im)^\s*([^:\r\n<]+?)\s*:\s*\r?\n\s*<' + escaped_key + r'>'
            match_multi = re.search(multiline_pattern, content)
            if match_multi:
                return match_multi.group(1).strip()
        
        return None

    def get_display_fields(self, object_type: str) -> List[Dict[str, str]]:
        """
        Returns a list of fields to display.
        1. Reads [fields] section to get API Key and DB Column.
        2. Parses [template] content to find the human-readable label.
        """
        fields_data = []
        config = self._get_specific_config(object_type)
        
        if not config:
            return []

        if not config.has_section('fields'):
            return []

        # Get the raw template content block
        template_content = ""
        if config.has_section('template') and config.has_option('template', 'content'):
            template_content = config.get('template', 'content')

        for api_key, value_str in config.items('fields'):
            # Parse value: "db_column:type" (e.g. "site_manager:string")
            parts = value_str.split(':')
            db_column = parts[0].strip()
            
            # We need to find the label.
            # The template might use the api_key OR the db_column name as the tag.
            label = self._extract_label_from_template(template_content, [api_key, db_column])
            
            # Fallback: If not found in template, Title Case the API key
            if not label:
                # e.g. 'siteManager' -> 'Site Manager'
                label = re.sub('([a-z0-9])([A-Z])', r'\1 \2', api_key).title()

            fields_data.append({
                'label': label,
                'db_column': db_column,
                'api_key': api_key
            })
        
        return fields_data