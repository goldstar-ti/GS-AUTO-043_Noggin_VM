#!/usr/bin/env python3
"""
Noggin Object Type Config Generator

Generates INI configuration files from Noggin OpenAPI JSON schemas.
Reusable for adding new object types to the Noggin Data Extraction System.

Usage:
    python generate_config.py <json_schema_path> <output_config_path> [options]

Example:
    python generate_config.py schemas/newObjectType.json config/new_object_type_config.ini \
        --abbreviation NOT --full-name "New Object Type" --id-field newObjectId
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HASH_FIELDS = {
    'vehicle': 'vehicle',
    'trailer': 'trailer',
    'trailer2': 'trailer',
    'trailer3': 'trailer',
    'team': 'team',
    'department': 'department',
    'whichDepartmentDoesTheLoadBelongTo': 'department',
}

SKIP_FIELDS = {'$meta', 'attachments'}


def extract_object_type_schema(json_data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract the main object type schema from OpenAPI spec."""
    components = json_data.get('components', {}).get('schemas', {})
    
    for name, schema in components.items():
        if name.startswith('ObjectType_') and not name.endswith('_patch'):
            object_key = name.replace('ObjectType_', '')
            return object_key, schema.get('properties', {})
    
    raise ValueError('No ObjectType schema found in JSON')


def infer_field_type(field_name: str, field_schema: dict[str, Any]) -> tuple[str, str | None]:
    """Infer field type and hash type from schema definition."""
    json_type = field_schema.get('type', 'string')
    json_format = field_schema.get('format', '')
    
    if field_name in HASH_FIELDS:
        return 'hash', HASH_FIELDS[field_name]
    
    if json_type == 'boolean':
        return 'bool', None
    elif json_type == 'number' or json_type == 'integer':
        return 'string', None
    elif json_format == 'date' or json_format == 'date-time':
        return 'datetime', None
    else:
        return 'string', None


def to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def generate_field_mappings(properties: dict[str, Any], id_field: str) -> list[str]:
    """Generate field mapping lines for config file."""
    lines = []
    
    for field_name, field_schema in sorted(properties.items()):
        if field_name in SKIP_FIELDS:
            continue
        if field_schema.get('type') == 'array':
            continue
        
        db_column = to_snake_case(field_name)
        field_type, hash_type = infer_field_type(field_name, field_schema)
        
        if hash_type:
            db_column = f"{db_column}_hash"
            mapping = f"{field_name} = {db_column}:hash:{hash_type}"
        else:
            mapping = f"{field_name} = {db_column}:{field_type}"
        
        lines.append(mapping)
    
    return lines


def generate_template_header(full_name: str, id_field: str, id_label: str) -> str:
    """Generate the template header section."""
    return f'''[template]
content = 
    ============================================================
    <full_name>
    RECORD GENERATED: <generation_date>
    ============================================================
    
    {id_label}:{''.ljust(max(0, 22 - len(id_label)))}<{id_field}>
    Date:                  <date>
'''


def generate_config(
    json_path: str,
    output_path: str,
    abbreviation: str,
    full_name: str,
    id_field: str,
    id_label: str,
) -> None:
    """Generate a config file from JSON schema."""
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    object_key, properties = extract_object_type_schema(json_data)
    
    if id_field not in properties:
        print(f"Warning: ID field '{id_field}' not found in schema properties")
    
    field_mappings = generate_field_mappings(properties, id_field)
    
    config_content = f'''[object_type]
abbreviation = {abbreviation}
full_name = {full_name}

[api]
endpoint = /rest/object/{object_key}/$tip
object_type = {full_name}

[fields]
id_field = {id_field}:{to_snake_case(id_field)}:string
date_field = date:inspection_date:datetime
'''
    
    for mapping in field_mappings:
        config_content += f"{mapping}\n"
    
    config_content += f'''
[output]
folder_pattern = {{abbreviation}}/{{year}}/{{month}}/{{date}} {{inspection_id}}
attachment_pattern = {{abbreviation}}_{{inspection_id}}_{{date}}_{{stub}}_{{sequence}}.jpg
session_log_header = TIMESTAMP\tTIP\tINSPECTION_ID\tATTACHMENTS_COUNT\tATTACHMENT_FILENAMES
show_json_payload_in_text_file = true
show_all_fields = false
filename_image_stub = photo
unknown_response_output_text = Unknown

[template]
content = 
    ============================================================
    <full_name>
    RECORD GENERATED: <generation_date>
    ============================================================
    
    {id_label}:{''.ljust(max(0, 22 - len(id_label)))}<{id_field}>
    Date:                  <date>
    
    Team:                  <team_resolved>
    
    <if:show_all_fields>
    ------------------------------------------------------------
    ALL FIELDS
    ------------------------------------------------------------
    (Edit this section to customize field display)
    </if:show_all_fields>
    
    Attachments:           <attachment_count>
    
    <if:show_json_payload_in_text_file>
    ------------------------------------------------------------
    COMPLETE TECHNICAL DATA (JSON FORMAT)
    ------------------------------------------------------------
    
    <json_payload>
    </if:show_json_payload_in_text_file>
'''
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"Config generated: {output_path}")
    print(f"  Object key: {object_key}")
    print(f"  Fields mapped: {len(field_mappings)}")
    print(f"  Template requires manual customization for show_all_fields section")


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate Noggin object type config from JSON schema'
    )
    parser.add_argument('json_path', help='Path to OpenAPI JSON schema file')
    parser.add_argument('output_path', help='Path for output INI config file')
    parser.add_argument('--abbreviation', '-a', required=True,
                        help='Object type abbreviation (e.g., CCC, TA)')
    parser.add_argument('--full-name', '-n', required=True,
                        help='Full name of object type')
    parser.add_argument('--id-field', '-i', required=True,
                        help='API field name for record ID')
    parser.add_argument('--id-label', '-l', default='ID',
                        help='Label for ID in template (default: ID)')
    
    args = parser.parse_args()
    
    if not Path(args.json_path).exists():
        print(f"Error: JSON file not found: {args.json_path}")
        return 1
    
    try:
        generate_config(
            args.json_path,
            args.output_path,
            args.abbreviation,
            args.full_name,
            args.id_field,
            args.id_label,
        )
        return 0
    except Exception as e:
        print(f"Error generating config: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
