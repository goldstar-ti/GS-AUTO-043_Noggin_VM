"""
Display Configuration Manager

Loads and manages field display configurations for the web interface.
Parses [web_display] sections from object type config files to determine
which fields to show, how to group them, and how to format them.
"""
import re
import configparser
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class DisplayField:
    """Represents a single field to display"""
    db_column: str
    label: str
    field_type: str = 'string'  # string, bool, datetime, hash
    hash_type: Optional[str] = None  # vehicle, trailer, team, department


@dataclass
class DisplaySection:
    """Represents a group of fields"""
    key: str
    title: str
    fields: List[DisplayField] = field(default_factory=list)
    collapsible: bool = False
    collapsed_default: bool = False


@dataclass
class ObjectTypeDisplayConfig:
    """Complete display configuration for an object type"""
    object_type: str
    abbreviation: str
    full_name: str
    sections: List[DisplaySection] = field(default_factory=list)


# Columns that should never be displayed (internal/system columns)
HIDDEN_COLUMNS = {
    'tip', 'raw_data', 'created_at', 'updated_at', 'processing_status',
    'retry_count', 'last_error', 'total_attachments', 'completed_attachment_count',
    'has_unknown_hashes', 'text_report_path', 'text_report_generated',
    'attachment_folder_path', 'noggin_id', 'object_type'
}

# Columns containing hashes (to be hidden, show resolved value instead)
HASH_COLUMN_SUFFIXES = ('_hash',)

# Metadata columns (shown in collapsible section)
METADATA_COLUMNS = {
    'api_meta_created', 'api_meta_modified', 'api_meta_security',
    'api_meta_type', 'api_meta_tip', 'api_meta_deleted', 'api_meta_parent',
    'api_meta_branch', 'api_meta_version', 'api_meta_raw'
}


def camel_to_title(name: str) -> str:
    """Convert camelCase or snake_case to Title Case with spaces"""
    # Handle snake_case
    name = name.replace('_', ' ')
    # Handle camelCase - insert space before capitals
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    # Handle consecutive capitals (e.g., "APIKey" -> "API Key")
    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', name)
    return name.title()


def format_field_label(db_column: str) -> str:
    """Convert database column name to human-readable label"""
    # Remove common suffixes
    label = db_column
    for suffix in ('_hash', '_id', '_yes', '_no', '_na', '_resolved'):
        if label.endswith(suffix) and label != suffix:
            label = label[:-len(suffix)]
            break
    
    # Handle specific patterns
    label = label.replace('_', ' ')
    label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
    
    # Clean up common abbreviations
    replacements = {
        'lcd': 'LCD',
        'lcs': 'LCS',
        'ccc': 'CCC',
        'fpi': 'FPI',
        'ta': 'TA',
        'so': 'SO',
        'id': 'ID',
        'api': 'API',
        'na': 'N/A',
    }
    
    words = label.split()
    words = [replacements.get(w.lower(), w.title()) for w in words]
    return ' '.join(words)


def format_value(value: Any, field_type: str = 'string', 
                 hide_empty: bool = True, date_format: str = '%d %b %Y',
                 datetime_format: str = '%d %b %Y %H:%M') -> Optional[str]:
    """Format a value for display"""
    if value is None or value == '':
        return None if hide_empty else ''
    
    if field_type == 'bool':
        if isinstance(value, bool):
            return 'Yes' if value else 'No'
        if isinstance(value, str):
            return 'Yes' if value.lower() in ('true', 'yes', '1') else 'No'
        return 'Yes' if value else 'No'
    
    if field_type == 'datetime':
        if isinstance(value, datetime):
            # If time is midnight, show date only
            if value.hour == 0 and value.minute == 0 and value.second == 0:
                return value.strftime(date_format)
            return value.strftime(datetime_format)
        return str(value)
    
    return str(value)


def is_hash_column(column: str) -> bool:
    """Check if column contains a hash value"""
    return column.endswith('_hash')


def get_resolved_column(hash_column: str) -> str:
    """Get the resolved column name for a hash column"""
    # vehicle_hash -> vehicle, trailer_hash -> trailer
    if hash_column.endswith('_hash'):
        return hash_column[:-5]  # Remove '_hash'
    return hash_column


class DisplayConfigManager:
    """Manages display configurations for all object types"""
    
    def __init__(self, config_dir: str = '../config', base_config=None):
        self.config_dir = Path(config_dir)
        self.base_config = base_config
        self._configs: Dict[str, ObjectTypeDisplayConfig] = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load all object type config files"""
        config_files = [
            'load_compliance_check_driver_loader_config.ini',
            'load_compliance_check_supervisor_manager_config.ini',
            'coupling_compliance_check_config.ini',
            'trailer_audits_config.ini',
            'site_observations_config.ini',
            'forklift_prestart_inspection_config.ini',
        ]
        
        for filename in config_files:
            filepath = self.config_dir / filename
            if filepath.exists():
                self._load_config_file(filepath)
    
    def _load_config_file(self, filepath: Path):
        """Load a single config file and extract display configuration"""
        parser = configparser.ConfigParser()
        parser.read(filepath)
        
        if not parser.has_section('object_type') or not parser.has_section('api'):
            return
        
        object_type = parser.get('api', 'object_type', fallback='')
        abbreviation = parser.get('object_type', 'abbreviation', fallback='')
        full_name = parser.get('object_type', 'full_name', fallback='')
        
        config = ObjectTypeDisplayConfig(
            object_type=object_type,
            abbreviation=abbreviation,
            full_name=full_name
        )
        
        # Check for [web_display] section
        if parser.has_section('web_display'):
            config.sections = self._parse_web_display_section(parser)
        else:
            # Generate default sections from [fields]
            config.sections = self._generate_default_sections(parser, object_type)
        
        self._configs[object_type] = config
    
    def _parse_web_display_section(self, parser: configparser.ConfigParser) -> List[DisplaySection]:
        """Parse the [web_display] section to build display sections"""
        sections = []
        section_order = parser.get('web_display', 'sections', fallback='').split(',')
        section_order = [s.strip() for s in section_order if s.strip()]
        
        for section_key in section_order:
            title = parser.get('web_display', f'{section_key}_title', fallback=camel_to_title(section_key))
            fields_str = parser.get('web_display', f'{section_key}_fields', fallback='')
            collapsible = parser.getboolean('web_display', f'{section_key}_collapsible', fallback=False)
            collapsed = parser.getboolean('web_display', f'{section_key}_collapsed', fallback=False)
            
            fields = []
            for field_def in fields_str.split(','):
                field_def = field_def.strip()
                if not field_def:
                    continue
                
                if ':' in field_def:
                    parts = field_def.split(':')
                    db_col = parts[0].strip()
                    label = parts[1].strip() if len(parts) > 1 else format_field_label(db_col)
                    field_type = parts[2].strip() if len(parts) > 2 else 'string'
                else:
                    db_col = field_def
                    label = format_field_label(db_col)
                    field_type = 'string'
                
                fields.append(DisplayField(
                    db_column=db_col,
                    label=label,
                    field_type=field_type
                ))
            
            sections.append(DisplaySection(
                key=section_key,
                title=title,
                fields=fields,
                collapsible=collapsible,
                collapsed_default=collapsed
            ))
        
        return sections
    
    def _generate_default_sections(self, parser: configparser.ConfigParser, 
                                   object_type: str) -> List[DisplaySection]:
        """Generate default display sections based on object type"""
        # Define default section structures per object type pattern
        if 'Load Compliance' in object_type and 'Driver' in object_type:
            return self._get_lcd_sections()
        elif 'Load Compliance' in object_type and 'Supervisor' in object_type:
            return self._get_lcs_sections()
        elif 'Coupling' in object_type:
            return self._get_ccc_sections()
        elif 'Trailer Audit' in object_type:
            return self._get_ta_sections()
        elif 'Site Observation' in object_type:
            return self._get_so_sections()
        elif 'Forklift' in object_type:
            return self._get_fpi_sections()
        else:
            return self._get_generic_sections()
    
    def _get_lcd_sections(self) -> List[DisplaySection]:
        """Default sections for Load Compliance Check (Driver/Loader)"""
        return [
            DisplaySection(
                key='basic_info',
                title='Basic Information',
                fields=[
                    DisplayField('noggin_reference', 'Reference', 'string'),
                    DisplayField('inspection_date', 'Date', 'datetime'),
                    DisplayField('inspected_by', 'Inspected By', 'string'),
                    DisplayField('driver_loader_name', 'Driver/Loader Name', 'string'),
                ]
            ),
            DisplaySection(
                key='vehicle_trailer',
                title='Vehicle & Trailer',
                fields=[
                    DisplayField('vehicle', 'Vehicle', 'string'),
                    DisplayField('vehicle_id', 'Vehicle ID', 'string'),
                    DisplayField('trailer', 'Trailer', 'string'),
                    DisplayField('trailer_id', 'Trailer ID', 'string'),
                    DisplayField('trailer2', 'Trailer 2', 'string'),
                    DisplayField('trailer2_id', 'Trailer 2 ID', 'string'),
                    DisplayField('trailer3', 'Trailer 3', 'string'),
                    DisplayField('trailer3_id', 'Trailer 3 ID', 'string'),
                ]
            ),
            DisplaySection(
                key='job_details',
                title='Job Details',
                fields=[
                    DisplayField('job_number', 'Job Number', 'string'),
                    DisplayField('run_number', 'Run Number', 'string'),
                    DisplayField('customer_client', 'Customer/Client', 'string'),
                    DisplayField('department', 'Department', 'string'),
                    DisplayField('team', 'Team', 'string'),
                    DisplayField('goldstar_or_contractor', 'Goldstar/Contractor', 'string'),
                    DisplayField('contractor_name', 'Contractor Name', 'string'),
                ]
            ),
            DisplaySection(
                key='compliance',
                title='Load Compliance',
                fields=[
                    DisplayField('compliance_yes', 'Compliant', 'bool'),
                    DisplayField('compliance_no', 'Not Compliant', 'bool'),
                    DisplayField('non_compliance_reason', 'Reason for Non-Compliance', 'string'),
                ]
            ),
            DisplaySection(
                key='restraints',
                title='Restraint Equipment',
                fields=[
                    DisplayField('straps', 'Straps Used', 'bool'),
                    DisplayField('no_of_straps', 'Number of Straps', 'string'),
                    DisplayField('chains', 'Chains Used', 'bool'),
                    DisplayField('no_of_chains', 'Number of Chains', 'string'),
                    DisplayField('mass', 'Load Mass', 'string'),
                ]
            ),
        ]
    
    def _get_lcs_sections(self) -> List[DisplaySection]:
        """Default sections for Load Compliance Check (Supervisor/Manager)"""
        return [
            DisplaySection(
                key='basic_info',
                title='Basic Information',
                fields=[
                    DisplayField('noggin_reference', 'Reference', 'string'),
                    DisplayField('inspection_date', 'Date', 'datetime'),
                    DisplayField('inspected_by', 'Inspected By', 'string'),
                    DisplayField('driver_loader_name', 'Driver/Loader Name', 'string'),
                ]
            ),
            DisplaySection(
                key='vehicle_trailer',
                title='Vehicle & Trailer',
                fields=[
                    DisplayField('vehicle', 'Vehicle', 'string'),
                    DisplayField('vehicle_id', 'Vehicle ID', 'string'),
                    DisplayField('trailer', 'Trailer', 'string'),
                    DisplayField('trailer_id', 'Trailer ID', 'string'),
                    DisplayField('trailer2', 'Trailer 2', 'string'),
                    DisplayField('trailer3', 'Trailer 3', 'string'),
                ]
            ),
            DisplaySection(
                key='job_details',
                title='Job Details',
                fields=[
                    DisplayField('job_number', 'Job Number', 'string'),
                    DisplayField('run_number', 'Run Number', 'string'),
                    DisplayField('customer_client', 'Customer/Client', 'string'),
                    DisplayField('department', 'Department', 'string'),
                    DisplayField('team', 'Team', 'string'),
                    DisplayField('mass', 'Load Mass', 'string'),
                ]
            ),
            DisplaySection(
                key='compliance_checks',
                title='Compliance Checks',
                collapsible=True,
                collapsed_default=False,
                fields=[
                    DisplayField('vehicle_appropriate_yes', 'Vehicle Appropriate', 'bool'),
                    DisplayField('load_distributed_yes', 'Load Distributed Correctly', 'bool'),
                    DisplayField('load_sitting_yes', 'Load on Timber/Rubber/Anti-Slip', 'bool'),
                    DisplayField('galas_corners_yes', 'Galas Corners Applied', 'bool'),
                    DisplayField('lashings_appropriate_yes', 'Lashings Appropriate', 'bool'),
                    DisplayField('low_lashing_angle_yes', 'No Low Lashing Angle', 'bool'),
                    DisplayField('additional_restraint_yes', 'Additional Restraint Used', 'bool'),
                    DisplayField('no_loose_items_yes', 'No Loose Items', 'bool'),
                    DisplayField('headboard_height_yes', 'Headboard Height OK', 'bool'),
                    DisplayField('mass_dimension_yes', 'Mass/Dimension OK', 'bool'),
                    DisplayField('pallets_condition_yes', 'Pallets in Good Condition', 'bool'),
                    DisplayField('tailgates_secured_yes', 'Tailgates Secured', 'bool'),
                    DisplayField('lashings_anchored_yes', 'Lashings Anchored', 'bool'),
                    DisplayField('lashings_positioned_yes', 'Lashings Positioned', 'bool'),
                    DisplayField('restraint_equipment_yes', 'Restraint Equipment OK', 'bool'),
                    DisplayField('dunnage_aligned_yes', 'Dunnage Aligned', 'bool'),
                    DisplayField('product_protection_yes', 'Product Protection', 'bool'),
                ]
            ),
            DisplaySection(
                key='restraints',
                title='Restraint Equipment Used',
                fields=[
                    DisplayField('gluts', 'Gluts', 'bool'),
                    DisplayField('no_of_gluts', 'Number of Gluts', 'string'),
                    DisplayField('straps', 'Straps', 'bool'),
                    DisplayField('no_of_straps', 'Number of Straps', 'string'),
                    DisplayField('webbings', 'Webbings', 'bool'),
                    DisplayField('no_of_webbings', 'Number of Webbings', 'string'),
                    DisplayField('chains', 'Chains', 'bool'),
                    DisplayField('no_of_chains', 'Number of Chains', 'string'),
                ]
            ),
            DisplaySection(
                key='final_compliance',
                title='Final Compliance Status',
                fields=[
                    DisplayField('compliance_yes', 'Load Compliant', 'bool'),
                    DisplayField('compliance_no', 'Load Not Compliant', 'bool'),
                    DisplayField('non_compliance_reason', 'Reason', 'string'),
                    DisplayField('comments_actions', 'Comments/Actions', 'string'),
                ]
            ),
        ]
    
    def _get_ccc_sections(self) -> List[DisplaySection]:
        """Default sections for Coupling Compliance Check"""
        return [
            DisplaySection(
                key='basic_info',
                title='Basic Information',
                fields=[
                    DisplayField('noggin_reference', 'Reference', 'string'),
                    DisplayField('inspection_date', 'Date', 'datetime'),
                    DisplayField('person_completing', 'Person Completing', 'string'),
                    DisplayField('team', 'Team', 'string'),
                ]
            ),
            DisplaySection(
                key='vehicle_trailer',
                title='Vehicle & Trailers',
                fields=[
                    DisplayField('vehicle_id', 'Vehicle ID', 'string'),
                    DisplayField('trailer', 'Trailer 1', 'string'),
                    DisplayField('trailer_id', 'Trailer 1 ID', 'string'),
                    DisplayField('trailer2', 'Trailer 2', 'string'),
                    DisplayField('trailer2_id', 'Trailer 2 ID', 'string'),
                    DisplayField('trailer3', 'Trailer 3', 'string'),
                    DisplayField('trailer3_id', 'Trailer 3 ID', 'string'),
                ]
            ),
            DisplaySection(
                key='job_details',
                title='Job Details',
                fields=[
                    DisplayField('job_number', 'Job Number', 'string'),
                    DisplayField('run_number', 'Run Number', 'string'),
                    DisplayField('customer_client', 'Customer/Client', 'string'),
                ]
            ),
            DisplaySection(
                key='trailer1_checks',
                title='Trailer 1 Coupling Checks',
                collapsible=True,
                fields=[
                    DisplayField('skid_plate_contact_t1', 'Skid Plate Contact', 'bool'),
                    DisplayField('turntable_release_engaged_t1', 'Turntable Release Engaged', 'bool'),
                    DisplayField('king_pin_engaged_t1', 'King Pin Engaged', 'bool'),
                    DisplayField('tug_test_performed_t1', 'Tug Test Performed', 'bool'),
                    DisplayField('tug_tests_count_t1', 'Tug Tests Count', 'string'),
                    DisplayField('trailer_legs_raised_t1', 'Trailer Legs Raised', 'bool'),
                ]
            ),
            DisplaySection(
                key='trailer2_checks',
                title='Trailer 2 Coupling Checks',
                collapsible=True,
                collapsed_default=True,
                fields=[
                    DisplayField('skid_plate_contact_t2', 'Skid Plate Contact', 'bool'),
                    DisplayField('turntable_release_engaged_t2', 'Turntable Release Engaged', 'bool'),
                    DisplayField('king_pin_engaged_t2', 'King Pin Engaged', 'bool'),
                    DisplayField('tug_test_performed_t2', 'Tug Test Performed', 'bool'),
                    DisplayField('tug_tests_count_t2', 'Tug Tests Count', 'string'),
                    DisplayField('ring_feeder_pin_engaged_t2', 'Ring Feeder Pin Engaged', 'bool'),
                    DisplayField('trailer_legs_raised_t2', 'Trailer Legs Raised', 'bool'),
                ]
            ),
            DisplaySection(
                key='trailer3_checks',
                title='Trailer 3 Coupling Checks',
                collapsible=True,
                collapsed_default=True,
                fields=[
                    DisplayField('skid_plate_contact_t3', 'Skid Plate Contact', 'bool'),
                    DisplayField('turntable_release_engaged_t3', 'Turntable Release Engaged', 'bool'),
                    DisplayField('king_pin_engaged_t3', 'King Pin Engaged', 'bool'),
                    DisplayField('tug_test_performed_t3', 'Tug Test Performed', 'bool'),
                    DisplayField('tug_tests_count_t3', 'Tug Tests Count', 'string'),
                    DisplayField('ring_feeder_pin_engaged_t3', 'Ring Feeder Pin Engaged', 'bool'),
                    DisplayField('trailer_legs_raised_t3', 'Trailer Legs Raised', 'bool'),
                ]
            ),
        ]
    
    def _get_ta_sections(self) -> List[DisplaySection]:
        """Default sections for Trailer Audits"""
        return [
            DisplaySection(
                key='basic_info',
                title='Basic Information',
                fields=[
                    DisplayField('noggin_reference', 'Reference', 'string'),
                    DisplayField('inspection_date', 'Date', 'datetime'),
                    DisplayField('inspected_by', 'Inspected By', 'string'),
                    DisplayField('team', 'Team', 'string'),
                ]
            ),
            DisplaySection(
                key='vehicle_details',
                title='Vehicle Details',
                fields=[
                    DisplayField('vehicle', 'Vehicle', 'string'),
                    DisplayField('rego', 'Registration', 'string'),
                    DisplayField('regular_driver', 'Regular Driver', 'string'),
                    DisplayField('driver_present_yes', 'Driver Present', 'bool'),
                ]
            ),
            DisplaySection(
                key='condition',
                title='Condition Assessment',
                fields=[
                    DisplayField('externally_excellent', 'External - Excellent', 'bool'),
                    DisplayField('externally_good', 'External - Good', 'bool'),
                    DisplayField('externally_fair', 'External - Fair', 'bool'),
                    DisplayField('externally_unacceptable', 'External - Unacceptable', 'bool'),
                    DisplayField('internally_excellent', 'Internal - Excellent', 'bool'),
                    DisplayField('internally_good', 'Internal - Good', 'bool'),
                    DisplayField('internally_fair', 'Internal - Fair', 'bool'),
                    DisplayField('internally_unacceptable', 'Internal - Unacceptable', 'bool'),
                ]
            ),
            DisplaySection(
                key='equipment',
                title='Equipment Checks',
                fields=[
                    DisplayField('revolving_beacon_yes', 'Revolving Beacon', 'bool'),
                    DisplayField('spare_tyre_yes', 'Spare Tyre', 'bool'),
                    DisplayField('fire_extinguisher_yes', 'Fire Extinguisher', 'bool'),
                    DisplayField('load_restraint_yes', 'Load Restraint Equipment', 'bool'),
                ]
            ),
            DisplaySection(
                key='restraints',
                title='Restraint Equipment Count',
                fields=[
                    DisplayField('no_of_webbing_straps', 'Webbing Straps', 'string'),
                    DisplayField('no_of_chains', 'Chains', 'string'),
                    DisplayField('no_of_gluts', 'Gluts', 'string'),
                ]
            ),
            DisplaySection(
                key='comments',
                title='Comments',
                fields=[
                    DisplayField('comments', 'Audit Comments', 'string'),
                    DisplayField('driver_comment', 'Driver Comment', 'string'),
                ]
            ),
        ]
    
    def _get_so_sections(self) -> List[DisplaySection]:
        """Default sections for Site Observations"""
        return [
            DisplaySection(
                key='basic_info',
                title='Basic Information',
                fields=[
                    DisplayField('noggin_reference', 'Reference', 'string'),
                    DisplayField('observation_date', 'Date', 'datetime'),
                    DisplayField('inspected_by', 'Inspected By', 'string'),
                    DisplayField('site_manager', 'Site Manager', 'string'),
                    DisplayField('department', 'Department', 'string'),
                ]
            ),
            DisplaySection(
                key='persons',
                title='Persons & Vehicles',
                fields=[
                    DisplayField('person_involved', 'Person(s) Involved', 'string'),
                    DisplayField('vehicles', 'Vehicle(s)', 'string'),
                ]
            ),
            DisplaySection(
                key='observation1',
                title='Observation 1',
                collapsible=True,
                fields=[
                    DisplayField('observation_1_checkbox', 'Observation Recorded', 'bool'),
                    DisplayField('details_1', 'Details', 'string'),
                    DisplayField('findings_1', 'Findings', 'string'),
                    DisplayField('summary_1', 'Summary', 'string'),
                ]
            ),
            DisplaySection(
                key='observation2',
                title='Observation 2',
                collapsible=True,
                collapsed_default=True,
                fields=[
                    DisplayField('observation_2_checkbox', 'Observation Recorded', 'bool'),
                    DisplayField('details_2', 'Details', 'string'),
                    DisplayField('findings_2', 'Findings', 'string'),
                    DisplayField('summary_2', 'Summary', 'string'),
                ]
            ),
            DisplaySection(
                key='observation3',
                title='Observation 3',
                collapsible=True,
                collapsed_default=True,
                fields=[
                    DisplayField('observation_3_checkbox', 'Observation Recorded', 'bool'),
                    DisplayField('details_3', 'Details', 'string'),
                    DisplayField('findings_3', 'Findings', 'string'),
                    DisplayField('summary_3', 'Summary', 'string'),
                ]
            ),
            DisplaySection(
                key='observation4',
                title='Observation 4',
                collapsible=True,
                collapsed_default=True,
                fields=[
                    DisplayField('observation_4_checkbox', 'Observation Recorded', 'bool'),
                    DisplayField('details_4', 'Details', 'string'),
                    DisplayField('findings_4', 'Findings', 'string'),
                    DisplayField('summary_4', 'Summary', 'string'),
                ]
            ),
        ]
    
    def _get_fpi_sections(self) -> List[DisplaySection]:
        """Default sections for Forklift Prestart Inspection"""
        return [
            DisplaySection(
                key='basic_info',
                title='Basic Information',
                fields=[
                    DisplayField('noggin_reference', 'Reference', 'string'),
                    DisplayField('inspection_date', 'Date', 'datetime'),
                    DisplayField('persons_completing', 'Person Completing', 'string'),
                    DisplayField('team', 'Team', 'string'),
                    DisplayField('prestart_status', 'Prestart Status', 'string'),
                ]
            ),
            DisplaySection(
                key='asset_details',
                title='Asset Details',
                fields=[
                    DisplayField('goldstar_asset', 'Goldstar Asset', 'string'),
                    DisplayField('asset_type', 'Asset Type', 'string'),
                    DisplayField('asset_id', 'Asset ID', 'string'),
                    DisplayField('asset_name', 'Asset Name', 'string'),
                    DisplayField('hour_reading', 'Hour Reading', 'string'),
                ]
            ),
            DisplaySection(
                key='visual_checks',
                title='Visual Inspection',
                collapsible=True,
                fields=[
                    DisplayField('damage_compliant', 'Damage - Compliant', 'bool'),
                    DisplayField('damage_defect', 'Damage - Defect', 'bool'),
                    DisplayField('damage_comments', 'Damage Comments', 'string'),
                    DisplayField('fluid_leaks_compliant', 'Fluid Leaks - Compliant', 'bool'),
                    DisplayField('fluid_leaks_defect', 'Fluid Leaks - Defect', 'bool'),
                    DisplayField('fluid_leaks_comments', 'Fluid Leaks Comments', 'string'),
                    DisplayField('tyres_wheels_compliant', 'Tyres/Wheels - Compliant', 'bool'),
                    DisplayField('tyres_wheels_defect', 'Tyres/Wheels - Defect', 'bool'),
                    DisplayField('tyres_wheels_comments', 'Tyres/Wheels Comments', 'string'),
                    DisplayField('fork_tynes_compliant', 'Fork Tynes - Compliant', 'bool'),
                    DisplayField('fork_tynes_defect', 'Fork Tynes - Defect', 'bool'),
                    DisplayField('fork_tynes_comments', 'Fork Tynes Comments', 'string'),
                ]
            ),
            DisplaySection(
                key='mechanical_checks',
                title='Mechanical Inspection',
                collapsible=True,
                fields=[
                    DisplayField('chains_hoses_cables_compliant', 'Chains/Hoses/Cables - Compliant', 'bool'),
                    DisplayField('chains_hoses_cables_defect', 'Chains/Hoses/Cables - Defect', 'bool'),
                    DisplayField('guards_compliant', 'Guards - Compliant', 'bool'),
                    DisplayField('guards_defect', 'Guards - Defect', 'bool'),
                    DisplayField('brakes_compliant', 'Brakes - Compliant', 'bool'),
                    DisplayField('brakes_defect', 'Brakes - Defect', 'bool'),
                    DisplayField('steering_compliant', 'Steering - Compliant', 'bool'),
                    DisplayField('steering_defect', 'Steering - Defect', 'bool'),
                    DisplayField('hydraulic_controls_compliant', 'Hydraulic Controls - Compliant', 'bool'),
                    DisplayField('hydraulic_controls_defect', 'Hydraulic Controls - Defect', 'bool'),
                ]
            ),
            DisplaySection(
                key='safety_checks',
                title='Safety Equipment',
                collapsible=True,
                fields=[
                    DisplayField('safety_devices_compliant', 'Safety Devices - Compliant', 'bool'),
                    DisplayField('safety_devices_defect', 'Safety Devices - Defect', 'bool'),
                    DisplayField('audible_alarms_compliant', 'Audible Alarms - Compliant', 'bool'),
                    DisplayField('audible_alarms_defect', 'Audible Alarms - Defect', 'bool'),
                    DisplayField('capacity_plate_compliant', 'Capacity Plate - Compliant', 'bool'),
                    DisplayField('capacity_plate_defect', 'Capacity Plate - Defect', 'bool'),
                ]
            ),
            DisplaySection(
                key='comments',
                title='General Comments',
                fields=[
                    DisplayField('general_comments', 'Comments', 'string'),
                ]
            ),
        ]
    
    def _get_generic_sections(self) -> List[DisplaySection]:
        """Generic sections for unknown object types"""
        return [
            DisplaySection(
                key='basic_info',
                title='Basic Information',
                fields=[
                    DisplayField('noggin_reference', 'Reference', 'string'),
                    DisplayField('inspection_date', 'Date', 'datetime'),
                ]
            ),
        ]
    
    def get_config(self, object_type: str) -> Optional[ObjectTypeDisplayConfig]:
        """Get display configuration for an object type"""
        return self._configs.get(object_type)
    
    def build_display_data(self, inspection: Dict[str, Any], 
                           hide_empty: bool = True,
                           date_format: str = '%d %b %Y',
                           datetime_format: str = '%d %b %Y %H:%M') -> Dict[str, Any]:
        """
        Build structured display data from raw inspection record.
        Returns sections with formatted field values.
        Falls back to dynamic generation if no config found.
        """
        object_type = inspection.get('object_type', '')
        config = self.get_config(object_type)
        
        result = {
            'object_type': object_type,
            'sections': [],
            'metadata': [],
            'raw_data_available': bool(inspection.get('raw_data')),
        }
        
        displayed_columns = set()
        
        if config and config.sections:
            # Use predefined sections from config
            for section in config.sections:
                section_data = {
                    'key': section.key,
                    'title': section.title,
                    'collapsible': section.collapsible,
                    'collapsed_default': section.collapsed_default,
                    'fields': []
                }
                
                for field in section.fields:
                    db_col = field.db_column
                    displayed_columns.add(db_col)
                    value = inspection.get(db_col)
                    
                    formatted = format_value(
                        value, 
                        field.field_type,
                        hide_empty,
                        date_format,
                        datetime_format
                    )
                    
                    if formatted is not None or not hide_empty:
                        section_data['fields'].append({
                            'label': field.label,
                            'value': formatted if formatted is not None else '',
                            'type': field.field_type,
                            'is_bool': field.field_type == 'bool',
                            'bool_value': value if field.field_type == 'bool' else None,
                        })
                
                if section_data['fields'] or not hide_empty:
                    result['sections'].append(section_data)
        else:
            # Fallback: generate sections dynamically from inspection data
            result['sections'] = self._generate_dynamic_sections(
                inspection, hide_empty, date_format, datetime_format, displayed_columns
            )
        
        # Build metadata section from remaining columns
        metadata_fields = []
        for key, value in inspection.items():
            if key in HIDDEN_COLUMNS or key in displayed_columns:
                continue
            if key.endswith('_hash'):
                continue
            if key.startswith('api_meta') or key in METADATA_COLUMNS:
                formatted = format_value(value, 'string', hide_empty, date_format, datetime_format)
                if formatted is not None:
                    metadata_fields.append({
                        'label': format_field_label(key),
                        'value': formatted,
                        'type': 'string',
                        'is_bool': False,
                    })
        
        if metadata_fields:
            result['metadata'] = metadata_fields
        
        return result
    
    def _generate_dynamic_sections(self, inspection: Dict[str, Any],
                                   hide_empty: bool,
                                   date_format: str,
                                   datetime_format: str,
                                   displayed_columns: set) -> List[Dict[str, Any]]:
        """
        Generate display sections dynamically from inspection data
        when no predefined config exists.
        """
        # Group fields by category based on column name patterns
        basic_fields = []
        vehicle_fields = []
        job_fields = []
        compliance_fields = []
        other_fields = []
        
        # Patterns for categorisation
        basic_patterns = ('noggin_reference', 'inspection_date', 'observation_date', 
                         'inspected_by', 'person_completing', 'persons_completing',
                         'driver_loader_name', 'regular_driver', 'site_manager')
        vehicle_patterns = ('vehicle', 'trailer', 'rego', 'asset')
        job_patterns = ('job_number', 'run_number', 'customer', 'department', 'team',
                       'goldstar', 'contractor', 'mass')
        compliance_patterns = ('compliance', 'compliant', 'defect', 'condition',
                              'excellent', 'good', 'fair', 'unacceptable')
        
        for key, value in inspection.items():
            if key in HIDDEN_COLUMNS:
                continue
            if key.endswith('_hash'):
                continue
            if key.startswith('api_meta') or key in METADATA_COLUMNS:
                continue
            
            displayed_columns.add(key)
            
            # Determine field type
            field_type = 'string'
            if isinstance(value, bool):
                field_type = 'bool'
            elif isinstance(value, datetime):
                field_type = 'datetime'
            elif key.endswith(('_yes', '_no', '_na', '_compliant', '_defect')):
                field_type = 'bool'
            
            formatted = format_value(value, field_type, hide_empty, date_format, datetime_format)
            
            if formatted is None and hide_empty:
                continue
            
            field_data = {
                'label': format_field_label(key),
                'value': formatted if formatted is not None else '',
                'type': field_type,
                'is_bool': field_type == 'bool',
                'bool_value': value if field_type == 'bool' else None,
            }
            
            # Categorise the field
            key_lower = key.lower()
            if any(p in key_lower for p in basic_patterns):
                basic_fields.append(field_data)
            elif any(p in key_lower for p in vehicle_patterns):
                vehicle_fields.append(field_data)
            elif any(p in key_lower for p in job_patterns):
                job_fields.append(field_data)
            elif any(p in key_lower for p in compliance_patterns):
                compliance_fields.append(field_data)
            else:
                other_fields.append(field_data)
        
        # Build sections
        sections = []
        
        if basic_fields:
            sections.append({
                'key': 'basic_info',
                'title': 'Basic Information',
                'collapsible': False,
                'collapsed_default': False,
                'fields': basic_fields
            })
        
        if vehicle_fields:
            sections.append({
                'key': 'vehicle_trailer',
                'title': 'Vehicle & Trailer',
                'collapsible': False,
                'collapsed_default': False,
                'fields': vehicle_fields
            })
        
        if job_fields:
            sections.append({
                'key': 'job_details',
                'title': 'Job Details',
                'collapsible': False,
                'collapsed_default': False,
                'fields': job_fields
            })
        
        if compliance_fields:
            sections.append({
                'key': 'compliance',
                'title': 'Compliance & Condition',
                'collapsible': True,
                'collapsed_default': False,
                'fields': compliance_fields
            })
        
        if other_fields:
            sections.append({
                'key': 'other',
                'title': 'Additional Information',
                'collapsible': True,
                'collapsed_default': True,
                'fields': other_fields
            })
        
        return sections