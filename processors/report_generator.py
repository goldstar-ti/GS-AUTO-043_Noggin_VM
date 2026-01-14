"""
Report Generator Module

Generates human-readable inspection reports using templates from config files.

Template syntax:
- <field_name>: Replace with field value
- <field_name_resolved>: Replace with resolved hash value
- <if:field_name>...</if:field_name>: Conditional block (include if field has value)
- <generation_date>: Current date
- <full_name>: Object type full name
- <abbreviation>: Object type abbreviation
- <json_payload>: Full JSON payload
- <attachment_count>: Number of attachments
"""

from __future__ import annotations
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger: logging.Logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates inspection reports from templates"""
    
    def __init__(self, config: 'ConfigLoader', hash_manager: 'HashManager') -> None:
        self.config = config
        self.hash_manager = hash_manager
        
        # Load object type info
        obj_config = config.get_object_type_config()
        self.object_type: str = obj_config['object_type']
        self.abbreviation: str = obj_config['abbreviation']
        self.full_name: str = obj_config['full_name']
        
        # Load template
        self.template: str = config.get_template_content()
        
        # Output settings
        self.show_json: bool = config.getboolean('output', 'show_json_payload_in_text_file', 
                                                  fallback=True, from_specific=True)
        self.show_all_fields: bool = config.getboolean('output', 'show_all_fields',
                                                        fallback=False, from_specific=True)
        self.unknown_text: str = config.get('output', 'unknown_response_output_text',
                                            fallback='Unknown', from_specific=True)
        
        # Date format for reports
        self.date_format: str = config.get('report', 'date_format', fallback='%Y-%m-%d')
        
        # Parse field mappings for hash resolution
        self.field_mappings = config.get_field_mappings()
        
        # Build set of date field names for quick lookup
        self.date_fields: set = {'date'}
        for api_field, (db_column, field_type, hash_type) in self.field_mappings.items():
            if field_type == 'datetime':
                self.date_fields.add(api_field)
        
        logger.debug(f"ReportGenerator initialised for {self.abbreviation}")
    
    def generate_report(self, response_data: Dict[str, Any], 
                       inspection_id: str) -> str:
        """
        Generate report from template and API response
        
        Args:
            response_data: API response JSON
            inspection_id: Inspection ID for hash lookups
            
        Returns:
            Formatted report string
        """
        # Build context with all available values
        context = self._build_context(response_data, inspection_id)
        
        # Process template
        report = self._process_template(self.template, context)
        
        # Clean up extra blank lines
        report = re.sub(r'\n{3,}', '\n\n', report)
        
        return report
    
    def _build_context(self, response_data: Dict[str, Any], 
                       inspection_id: str) -> Dict[str, Any]:
        """Build context dictionary for template substitution"""
        context: Dict[str, Any] = {
            'generation_date': datetime.now().strftime('%d-%m-%Y'),
            'full_name': self.full_name.upper(),
            'abbreviation': self.abbreviation,
            'attachment_count': len(response_data.get('attachments', [])),
            'json_payload': json.dumps(response_data, indent=2, ensure_ascii=False),
            'show_json_payload_in_text_file': self.show_json,
            'show_all_fields': self.show_all_fields,
        }
        
        # Add all response fields directly
        for key, value in response_data.items():
            if key == '$meta':
                continue
            
            # Format date fields
            if key in self.date_fields and value:
                context[key] = self._format_date(value)
            else:
                context[key] = value if value is not None else self.unknown_text
        
        # Process hash fields and add resolved values
        tip_value = response_data.get('$meta', {}).get('tip', '')
        
        for api_field, (db_column, field_type, hash_type) in self.field_mappings.items():
            value = response_data.get(api_field)
            
            if field_type == 'hash' and value and hash_type:
                # Resolve hash to human-readable value
                resolved = self.hash_manager.lookup_hash(
                    hash_type, str(value), tip_value, inspection_id
                )
                context[f"{api_field}_resolved"] = resolved
                
                # Also add without _resolved suffix for simpler templates
                base_name = api_field.replace('_hash', '').replace('Hash', '')
                context[f"{base_name}_resolved"] = resolved
        
        return context
    
    def _format_date(self, date_value: str) -> str:
        """
        Format ISO date string to configured format.
        
        Args:
            date_value: ISO format date string (e.g., '2025-11-28T00:00:00.000+08:00')
            
        Returns:
            Formatted date string or original if parsing fails
        """
        if not date_value or not isinstance(date_value, str):
            return str(date_value) if date_value else self.unknown_text
        
        try:
            # Handle various ISO formats
            clean_date = date_value.replace('Z', '+00:00')
            
            # Try parsing with timezone
            if '+' in clean_date or '-' in clean_date[10:]:
                # Has timezone info
                parsed = datetime.fromisoformat(clean_date)
            else:
                parsed = datetime.fromisoformat(clean_date)
            
            return parsed.strftime(self.date_format)
        except (ValueError, AttributeError) as e:
            logger.debug(f"Could not parse date '{date_value}': {e}")
            return date_value
    
    def _process_template(self, template: str, context: Dict[str, Any]) -> str:
        """Process template with context substitution"""
        result = template
        
        # Process conditional blocks first (nested supported)
        result = self._process_conditionals(result, context)
        
        # Replace placeholders
        result = self._replace_placeholders(result, context)
        
        return result
    
    def _process_conditionals(self, template: str, context: Dict[str, Any]) -> str:
        """
        Process conditional blocks <if:field>...</if:field>
        
        Supports nested conditionals.
        """
        # Regex for conditional blocks (non-greedy, handles nesting by processing innermost first)
        pattern = r'<if:(\w+)>(.*?)</if:\1>'
        
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            matches = list(re.finditer(pattern, template, re.DOTALL))
            if not matches:
                break
            
            # Process from end to start to preserve positions
            for match in reversed(matches):
                field_name = match.group(1)
                content = match.group(2)
                
                # Check if condition is met
                should_include = self._evaluate_condition(field_name, context)
                
                if should_include:
                    # Include content (will be processed for nested conditionals in next iteration)
                    replacement = content
                else:
                    # Remove entire block
                    replacement = ''
                
                template = template[:match.start()] + replacement + template[match.end():]
            
            iteration += 1
        
        return template
    
    def _evaluate_condition(self, field_name: str, context: Dict[str, Any]) -> bool:
        """Evaluate if a conditional field should be included"""
        value = context.get(field_name)
        
        if value is None:
            return False
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            # Empty string or "Unknown" = false
            return bool(value) and value != self.unknown_text
        
        if isinstance(value, (list, dict)):
            return len(value) > 0
        
        # Numbers: 0 = false, anything else = true
        if isinstance(value, (int, float)):
            return value != 0
        
        return bool(value)
    
    def _replace_placeholders(self, template: str, context: Dict[str, Any]) -> str:
        """Replace <placeholder> with values from context"""
        
        def replacer(match):
            field_name = match.group(1)
            value = context.get(field_name)
            
            if value is None:
                return self.unknown_text
            
            if isinstance(value, bool):
                return 'Yes' if value else 'No'
            
            if isinstance(value, datetime):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            
            if isinstance(value, (dict, list)):
                return json.dumps(value, indent=2, ensure_ascii=False)
            
            return str(value)
        
        # Match <field_name> but not <if: or </if:
        pattern = r'<(?!if:|/if:)(\w+)>'
        
        return re.sub(pattern, replacer, template)
    
    def save_report(self, report: str, inspection_folder: Path, 
                   inspection_id: str) -> Optional[Path]:
        """
        Save report to file
        
        Args:
            report: Report content
            inspection_folder: Folder to save in
            inspection_id: Used for filename
            
        Returns:
            Path to saved file or None on error
        """
        # Sanitise ID for filename
        safe_id = re.sub(r'[<>:"/\\|?*]', '_', str(inspection_id))
        safe_id = safe_id[:100]
        
        filename = f"{safe_id}_inspection_data.txt"
        file_path = inspection_folder / filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"Saved report to: {file_path}")
            return file_path
            
        except IOError as e:
            logger.error(f"Failed to save report to {file_path}: {e}")
            return None


class DefaultReportGenerator:
    """
    Fallback report generator when no template is configured
    
    Generates a simple key-value report from the API response.
    """
    
    def __init__(self, config: 'ConfigLoader', hash_manager: 'HashManager') -> None:
        self.config = config
        self.hash_manager = hash_manager
        
        obj_config = config.get_object_type_config()
        self.full_name: str = obj_config['full_name']
        self.abbreviation: str = obj_config['abbreviation']
        
        self.show_json: bool = config.getboolean('output', 'show_json_payload_in_text_file',
                                                  fallback=True, from_specific=True)
        self.unknown_text: str = config.get('output', 'unknown_response_output_text',
                                            fallback='Unknown', from_specific=True)
        
        # Date format for reports
        self.date_format: str = config.get('report', 'date_format', fallback='%Y-%m-%d')
        
        self.field_mappings = config.get_field_mappings()
        
        # Build set of date field names
        self.date_fields: set = {'date'}
        for api_field, (db_column, field_type, hash_type) in self.field_mappings.items():
            if field_type == 'datetime':
                self.date_fields.add(api_field)
    
    def generate_report(self, response_data: Dict[str, Any],
                       inspection_id: str) -> str:
        """Generate a default report without template"""
        lines: List[str] = []
        
        lines.append("=" * 60)
        lines.append(self.full_name.upper())
        lines.append(f"RECORD GENERATED: {datetime.now().strftime('%d-%m-%Y')}")
        lines.append("=" * 60)
        lines.append("")
        
        tip_value = response_data.get('$meta', {}).get('tip', '')
        
        # Output all mapped fields
        for api_field, (db_column, field_type, hash_type) in self.field_mappings.items():
            value = response_data.get(api_field)
            
            if value is None:
                continue
            
            # Format field name nicely
            display_name = self._format_field_name(api_field)
            
            if field_type == 'hash' and hash_type:
                resolved = self.hash_manager.lookup_hash(
                    hash_type, str(value), tip_value, inspection_id
                )
                lines.append(f"{display_name}: {resolved}")
            elif field_type == 'bool':
                lines.append(f"{display_name}: {'Yes' if value else 'No'}")
            elif field_type == 'datetime' or api_field in self.date_fields:
                lines.append(f"{display_name}: {self._format_date(value)}")
            else:
                lines.append(f"{display_name}: {value}")
        
        lines.append("")
        
        # Attachments
        attachment_count = len(response_data.get('attachments', []))
        lines.append(f"Attachments: {attachment_count}")
        lines.append("")
        
        # Optional JSON payload
        if self.show_json:
            lines.append("-" * 60)
            lines.append("COMPLETE TECHNICAL DATA (JSON FORMAT)")
            lines.append("-" * 60)
            lines.append("")
            lines.append(json.dumps(response_data, indent=2, ensure_ascii=False))
        
        return '\n'.join(lines)
    
    def _format_field_name(self, field_name: str) -> str:
        """Convert camelCase to Title Case with spaces"""
        # Insert space before capitals
        spaced = re.sub(r'([A-Z])', r' \1', field_name)
        # Handle consecutive capitals (e.g., "ID" -> "ID" not "I D")
        spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', spaced)
        # Title case and strip
        return spaced.strip().title()
    
    def _format_date(self, date_value: str) -> str:
        """Format ISO date string to configured format"""
        if not date_value or not isinstance(date_value, str):
            return str(date_value) if date_value else self.unknown_text
        
        try:
            clean_date = date_value.replace('Z', '+00:00')
            parsed = datetime.fromisoformat(clean_date)
            return parsed.strftime(self.date_format)
        except (ValueError, AttributeError):
            return date_value
    
    def save_report(self, report: str, inspection_folder: Path,
                   inspection_id: str) -> Optional[Path]:
        """Save report to file"""
        safe_id = re.sub(r'[<>:"/\\|?*]', '_', str(inspection_id))[:100]
        filename = f"{safe_id}_inspection_data.txt"
        file_path = inspection_folder / filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Saved report to: {file_path}")
            return file_path
        except IOError as e:
            logger.error(f"Failed to save report: {e}")
            return None


def create_report_generator(config: 'ConfigLoader', 
                           hash_manager: 'HashManager') -> ReportGenerator:
    """
    Factory function to create appropriate report generator
    
    Returns ReportGenerator if template configured, else DefaultReportGenerator.
    """
    try:
        template = config.get_template_content()
        if template and template.strip():
            return ReportGenerator(config, hash_manager)
    except Exception as e:
        logger.warning(f"Could not load template, using default: {e}")
    
    return DefaultReportGenerator(config, hash_manager)