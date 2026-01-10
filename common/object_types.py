"""
Object Type Detection Module

Centralised object type detection logic used by:
- csv_importer.py
- sftp_download_tips.py
- noggin_processor_unified.py
- Any future importers

This ensures consistent detection across all entry points.

CHANGE LOG:
- Renamed 'LCC' to 'LCD' to match Noggin's naming convention (Load Compliance Check Driver/Loader)
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class ObjectTypeConfig:
    """Configuration for an object type"""
    abbreviation: str
    full_name: str
    id_column: str
    id_prefix: str
    config_file: str
    date_column: str = 'date'


# Centralised object type definitions
# Note: LCD = Load Compliance Check (Driver/Loader), matches Noggin's ID prefix "LCD - "
OBJECT_TYPES: Dict[str, ObjectTypeConfig] = {
    'CCC': ObjectTypeConfig(
        abbreviation='CCC',
        full_name='Coupling Compliance Check',
        id_column='couplingId',
        id_prefix='C - ',
        config_file='coupling_compliance_check_config.ini'
    ),
    'FPI': ObjectTypeConfig(
        abbreviation='FPI',
        full_name='Forklift Prestart Inspection',
        id_column='forkliftPrestartInspectionId',
        id_prefix='FL - Inspection - ',
        config_file='forklift_prestart_inspection_config.ini'
    ),
    'LCS': ObjectTypeConfig(
        abbreviation='LCS',
        full_name='Load Compliance Check Supervisor/Manager',
        id_column='lcsInspectionId',
        id_prefix='LCS - ',
        config_file='load_compliance_check_supervisor_manager_config.ini'
    ),
    'LCD': ObjectTypeConfig(
        abbreviation='LCD',
        full_name='Load Compliance Check Driver/Loader',
        id_column='lcdInspectionId',
        id_prefix='LCD - ',
        config_file='load_compliance_check_config.ini'
    ),
    'SO': ObjectTypeConfig(
        abbreviation='SO',
        full_name='Site Observations',
        id_column='siteObservationId',
        id_prefix='SO - ',
        config_file='site_observations_config.ini'
    ),
    'TA': ObjectTypeConfig(
        abbreviation='TA',
        full_name='Trailer Audits',
        id_column='trailerAuditId',
        id_prefix='TA - ',
        config_file='trailer_audits_config.ini'
    )
}

# Backward compatibility alias: LCC -> LCD
# Remove this after all code has been updated
OBJECT_TYPES['LCC'] = OBJECT_TYPES['LCD']

# Build reverse lookup: id_column -> ObjectTypeConfig
ID_COLUMN_TO_TYPE: Dict[str, ObjectTypeConfig] = {
    config.id_column: config for config in OBJECT_TYPES.values()
}

# Also support lowercase lookups
ID_COLUMN_TO_TYPE_LOWER: Dict[str, ObjectTypeConfig] = {
    config.id_column.lower(): config for config in OBJECT_TYPES.values()
}


def detect_object_type_from_headers(headers: List[str]) -> Optional[ObjectTypeConfig]:
    """
    Detect object type from CSV column headers
    
    Args:
        headers: List of column header strings
        
    Returns:
        ObjectTypeConfig if detected, None otherwise
    """
    clean_headers = [h.strip() for h in headers]
    clean_headers_lower = [h.lower() for h in clean_headers]
    
    for id_column, config in ID_COLUMN_TO_TYPE.items():
        if id_column in clean_headers:
            logger.debug(f"Detected object type {config.abbreviation} via column '{id_column}'")
            return config
    
    for id_column_lower, config in ID_COLUMN_TO_TYPE_LOWER.items():
        if id_column_lower in clean_headers_lower:
            logger.debug(f"Detected object type {config.abbreviation} via column '{config.id_column}' (case-insensitive)")
            return config
    
    logger.warning(f"Could not detect object type from headers: {clean_headers[:10]}")
    return None


def get_object_type_by_abbreviation(abbreviation: str) -> Optional[ObjectTypeConfig]:
    """Get object type config by abbreviation (LCD, CCC, etc.)"""
    return OBJECT_TYPES.get(abbreviation.upper())


def get_object_type_by_full_name(full_name: str) -> Optional[ObjectTypeConfig]:
    """Get object type config by full name"""
    for config in OBJECT_TYPES.values():
        if config.full_name.lower() == full_name.lower():
            return config
    return None


def get_all_object_types() -> List[ObjectTypeConfig]:
    """Get list of all supported object types (excluding aliases)"""
    # Filter out the LCC alias to avoid duplicates
    seen_abbrevs = set()
    result = []
    for abbrev, config in OBJECT_TYPES.items():
        if abbrev == 'LCC':
            continue
        if config.abbreviation not in seen_abbrevs:
            seen_abbrevs.add(config.abbreviation)
            result.append(config)
    return result


def get_id_column_for_type(abbreviation: str) -> Optional[str]:
    """Get the ID column name for an object type"""
    config = OBJECT_TYPES.get(abbreviation.upper())
    return config.id_column if config else None


def find_column_index(headers: List[str], column_name: str) -> int:
    """
    Find column index by name (case-insensitive, handles whitespace)
    
    Args:
        headers: List of column headers
        column_name: Column name to find
        
    Returns:
        Column index, or -1 if not found
    """
    clean_headers = [h.strip().lower() for h in headers]
    target = column_name.strip().lower()
    
    try:
        return clean_headers.index(target)
    except ValueError:
        return -1


def extract_row_data(row: List[str], headers: List[str], 
                     object_config: ObjectTypeConfig) -> Dict[str, Any]:
    """
    Extract standardised data from a CSV row
    
    Args:
        row: CSV row data
        headers: Column headers
        object_config: Object type configuration
        
    Returns:
        Dictionary with: tip, inspection_id, inspection_date, object_type, abbreviation
    """
    tip_value = row[0].strip() if row else ''
    
    id_index = find_column_index(headers, object_config.id_column)
    inspection_id = None
    if id_index >= 0 and len(row) > id_index:
        inspection_id = row[id_index].strip() or None
    
    date_index = find_column_index(headers, object_config.date_column)
    inspection_date = None
    if date_index >= 0 and len(row) > date_index:
        inspection_date = row[date_index].strip() or None
    
    return {
        'tip': tip_value,
        'inspection_id': inspection_id,
        'inspection_date': inspection_date,
        'object_type': object_config.abbreviation,
        'abbreviation': object_config.abbreviation
    }


def detect_object_type(headers: List[str]) -> Optional[str]:
    """
    Detect object type and return abbreviation (legacy compatibility)
    
    Args:
        headers: List of column headers
        
    Returns:
        Object type abbreviation or None
    """
    config = detect_object_type_from_headers(headers)
    return config.abbreviation if config else None


def load_object_types() -> Dict[str, ObjectTypeConfig]:
    """Return the object types dictionary (for external access)"""
    return OBJECT_TYPES


if __name__ == "__main__":
    test_cases = [
        ['nogginId', 'couplingId', 'date', 'team'],
        [' ', 'forkliftPrestartInspectionId', 'date'],
        ['nogginId', 'lcsInspectionId', 'date'],
        ['nogginId', 'lcdInspectionId', 'date'],
        ['nogginId', 'siteObservationId', 'date'],
        [' ', 'trailerAuditId', 'date'],
        ['unknown', 'columns', 'here'],
    ]
    
    print("Object Type Detection Test:")
    print("-" * 60)
    
    for headers in test_cases:
        config = detect_object_type_from_headers(headers)
        if config:
            print(f"Headers: {headers[:3]}...")
            print(f"  -> {config.abbreviation} ({config.full_name})")
        else:
            print(f"Headers: {headers[:3]}...")
            print(f"  -> NOT DETECTED")
        print()
    
    print("\nAll supported object types:")
    for config in get_all_object_types():
        print(f"  {config.abbreviation}: {config.full_name}")
        print(f"      ID column: {config.id_column}")
        print(f"      Config: {config.config_file}")
