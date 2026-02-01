#!/usr/bin/env python3
"""
Noggin Data Validation Script
Validates inspection data integrity for any object type.

Usage:
    validate_noggin_data.py LCD
    validate_noggin_data.py CCC
    validate_noggin_data.py FPI
"""

import sys
import csv
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import (
    ConfigLoader,
    ConfigurationError,
    LoggerManager,
    DatabaseConnectionManager,
    DatabaseConnectionError
)


CONFIG_FILES = {
    'LCD': 'load_compliance_check_driver_loader_config.ini',
    'LCS': 'load_compliance_check_supervisor_manager_config.ini',
    'CCC': 'coupling_compliance_check_config.ini',
    'FPI': 'forklift_prestart_inspection_config.ini',
    'SO': 'site_observations_config.ini',
    'TA': 'trailer_audits_config.ini',
}


class NogginDataValidator:
    def __init__(self, config: ConfigLoader, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.db_manager = None
        self.results = []
        self.stats = {
            'total_records': 0,
            'text_file_exists': 0,
            'text_file_missing': 0,
            'raw_json_exists': 0,
            'raw_json_missing': 0,
            'attachments_match': 0,
            'attachments_mismatch': 0,
            'attachment_files_ok': 0,
            'attachment_files_missing': 0,
            'fully_valid': 0
        }
        self.stats_by_status = defaultdict(lambda: {
            'total': 0,
            'text_file_exists': 0,
            'raw_json_exists': 0,
            'attachment_files_ok': 0,
            'fully_valid': 0
        })
        self.errors = defaultdict(list)
        
        self.base_output_path = Path(self.config.get('paths', 'base_output_path'))
        self.object_type_config = self.config.get_object_type_config()
        self.abbreviation = self.object_type_config.get('abbreviation', 'LCD')
        self.full_name = self.object_type_config.get('full_name', 'Load Compliance Check (Driver/Loader)')
        
    def connect_db(self):
        """Establish database connection"""
        self.db_manager = DatabaseConnectionManager(self.config)
        self.logger.info("Database connection established")
        
    def disconnect_db(self):
        """Close database connection"""
        if self.db_manager:
            self.db_manager.close_all()
            
    def get_record_folder_path(self, inspection_id: str, inspection_date: datetime) -> Path:
        """Build expected folder path for a record"""
        year = inspection_date.strftime('%Y')
        month = inspection_date.strftime('%m')
        date_str = inspection_date.strftime('%Y-%m-%d')
        
        folder_path = self.base_output_path / self.abbreviation / year / month / f"{date_str} {inspection_id}"
        return folder_path
    
    def find_text_file(self, folder_path: Path) -> Optional[Path]:
        """Find text file in folder that matches expected pattern"""
        if not folder_path.exists():
            return None
        
        # Pattern to match based on config full_name
        # Extract first part before parentheses for flexible matching
        name_parts = self.full_name.split('(')
        search_pattern = name_parts[0].strip()
        
        for file_path in folder_path.glob('*.txt'):
            # Check if file starts with expected pattern and has content
            if file_path.name.startswith(search_pattern) and file_path.stat().st_size > 0:
                return file_path
        
        return None
        
    def get_records(self) -> List[Dict]:
        """Retrieve all records for this object type from database"""
        query = """
            SELECT 
                tip,
                noggin_reference,
                inspection_date,
                processing_status,
                raw_json IS NOT NULL as has_raw_json
            FROM noggin_schema.noggin_data
            WHERE object_type = %s
            ORDER BY inspection_date DESC, noggin_reference
        """
        
        return self.db_manager.execute_query_dict(query, (self.abbreviation,))
            
    def get_attachments_for_record(self, tip: str) -> List[Dict]:
        """Get attachment details for a specific record"""
        query = """
            SELECT 
                attachment_tip,
                attachment_sequence,
                filename,
                file_path,
                attachment_status,
                file_size_bytes
            FROM noggin_schema.attachments
            WHERE record_tip = %s
            ORDER BY attachment_sequence
        """
        
        return self.db_manager.execute_query_dict(query, (tip,))
            
    def validate_record(self, record: Dict) -> Dict:
        """Validate a single LCD record"""
        tip = record['tip']
        inspection_id = record['noggin_reference']
        inspection_date = record['inspection_date']
        processing_status = record['processing_status']
        has_raw_json = record['has_raw_json']
        
        result = {
            'tip': tip,
            'inspection_id': inspection_id,
            'inspection_date': inspection_date.strftime('%Y-%m-%d') if inspection_date else 'N/A',
            'processing_status': processing_status,
            'text_file_exists': False,
            'text_file_path': 'N/A',
            'raw_json_exists': has_raw_json,
            'expected_attachments': 0,
            'found_attachments': 0,
            'attachment_files_ok': 0,
            'attachment_files_missing': 0,
            'missing_attachment_files': [],
            'validation_status': 'UNKNOWN',
            'issues': []
        }
        
        self.stats['total_records'] += 1
        self.stats_by_status[processing_status]['total'] += 1
        
        if inspection_date and inspection_id:
            folder_path = self.get_record_folder_path(inspection_id, inspection_date)
            text_file_path = self.find_text_file(folder_path)
            
            if text_file_path:
                result['text_file_exists'] = True
                result['text_file_path'] = str(text_file_path)
                self.stats['text_file_exists'] += 1
                self.stats_by_status[processing_status]['text_file_exists'] += 1
            else:
                self.stats['text_file_missing'] += 1
                result['issues'].append('Text file missing')
                result['text_file_path'] = str(folder_path / 'Expected text file not found')
                self.errors['text_file_missing'].append({
                    'tip': tip,
                    'inspection_id': inspection_id,
                    'processing_status': processing_status,
                    'expected_folder': str(folder_path)
                })
        else:
            result['issues'].append('Missing inspection_date or inspection_id')
            
        if has_raw_json:
            self.stats['raw_json_exists'] += 1
            self.stats_by_status[processing_status]['raw_json_exists'] += 1
        else:
            self.stats['raw_json_missing'] += 1
            result['issues'].append('Raw JSON missing')
            self.errors['raw_json_missing'].append({
                'tip': tip,
                'inspection_id': inspection_id,
                'processing_status': processing_status
            })
            
        attachments = self.get_attachments_for_record(tip)
        result['expected_attachments'] = len(attachments)
        
        if attachments:
            for att in attachments:
                result['found_attachments'] += 1
                
                if att['file_path'] and Path(att['file_path']).exists():
                    result['attachment_files_ok'] += 1
                else:
                    result['attachment_files_missing'] += 1
                    result['missing_attachment_files'].append(att['filename'])
                    
            if result['attachment_files_missing'] == 0:
                self.stats['attachment_files_ok'] += 1
                self.stats_by_status[processing_status]['attachment_files_ok'] += 1
            else:
                self.stats['attachment_files_missing'] += 1
                result['issues'].append(f"{result['attachment_files_missing']} attachment file(s) missing")
                self.errors['attachment_files_missing'].append({
                    'tip': tip,
                    'inspection_id': inspection_id,
                    'processing_status': processing_status,
                    'missing_count': result['attachment_files_missing'],
                    'missing_files': result['missing_attachment_files']
                })
                
        if not result['issues']:
            result['validation_status'] = 'VALID'
            self.stats['fully_valid'] += 1
            self.stats_by_status[processing_status]['fully_valid'] += 1
        elif result['text_file_exists'] and result['raw_json_exists']:
            result['validation_status'] = 'PARTIAL'
        else:
            result['validation_status'] = 'INVALID'
            
        return result
        
    def run_validation(self):
        """Execute validation process"""
        self.logger.info("=" * 80)
        self.logger.info(f"{self.full_name.upper()} DATA VALIDATION")
        self.logger.info("=" * 80)
        
        try:
            self.connect_db()
            
            self.logger.info(f"Retrieving {self.abbreviation} records...")
            records = self.get_records()
            self.logger.info(f"Found {len(records)} {self.abbreviation} records to validate")
            
            self.logger.info("Validating records...")
            for i, record in enumerate(records, 1):
                if i % 100 == 0:
                    self.logger.info(f"Processed {i}/{len(records)} records")
                    
                result = self.validate_record(record)
                self.results.append(result)
                
            self.logger.info(f"Validation complete: {len(records)} records processed")
            
        except Exception as e:
            self.logger.error(f"Validation error: {e}", exc_info=True)
            raise
        finally:
            self.disconnect_db()
            
    def generate_executive_summary(self, output_path: Path):
        """Generate executive summary report"""
        total = self.stats['total_records']
        
        with open(output_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write(f"{self.full_name.upper()} DATA VALIDATION - EXECUTIVE SUMMARY\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("OVERALL STATISTICS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Records Validated:        {total:,}\n")
            f.write(f"Fully Valid Records:            {self.stats['fully_valid']:,} ({self.stats['fully_valid']/total*100:.1f}%)\n")
            f.write(f"Partial/Invalid Records:        {total - self.stats['fully_valid']:,} ({(total - self.stats['fully_valid'])/total*100:.1f}%)\n")
            f.write("\n")
            
            f.write("TEXT FILE VALIDATION\n")
            f.write("-" * 80 + "\n")
            f.write(f"Text Files Found:               {self.stats['text_file_exists']:,} ({self.stats['text_file_exists']/total*100:.1f}%)\n")
            f.write(f"Text Files Missing:             {self.stats['text_file_missing']:,} ({self.stats['text_file_missing']/total*100:.1f}%)\n")
            f.write("\n")
            
            f.write("RAW JSON VALIDATION\n")
            f.write("-" * 80 + "\n")
            f.write(f"Raw JSON Present:               {self.stats['raw_json_exists']:,} ({self.stats['raw_json_exists']/total*100:.1f}%)\n")
            f.write(f"Raw JSON Missing:               {self.stats['raw_json_missing']:,} ({self.stats['raw_json_missing']/total*100:.1f}%)\n")
            f.write("\n")
            
            f.write("ATTACHMENT VALIDATION\n")
            f.write("-" * 80 + "\n")
            
            total_expected = sum(r['expected_attachments'] for r in self.results)
            total_found_files = sum(r['attachment_files_ok'] for r in self.results)
            total_missing_files = sum(r['attachment_files_missing'] for r in self.results)
            
            if total_expected > 0:
                f.write(f"Total Expected Attachments:     {total_expected:,}\n")
                f.write(f"Attachment Files Found:         {total_found_files:,} ({total_found_files/total_expected*100:.1f}%)\n")
                f.write(f"Attachment Files Missing:       {total_missing_files:,} ({total_missing_files/total_expected*100:.1f}%)\n")
                f.write("\n")
            
            records_with_attachments = sum(1 for r in self.results if r['expected_attachments'] > 0)
            if records_with_attachments > 0:
                records_all_attachments_ok = self.stats['attachment_files_ok']
                f.write(f"Records with Attachments:       {records_with_attachments:,}\n")
                f.write(f"Records - All Attachments OK:   {records_all_attachments_ok:,} ({records_all_attachments_ok/records_with_attachments*100:.1f}%)\n")
                f.write(f"Records - Missing Attachments:  {self.stats['attachment_files_missing']:,} ({self.stats['attachment_files_missing']/records_with_attachments*100:.1f}%)\n")
            f.write("\n")
            
            f.write("ISSUES SUMMARY\n")
            f.write("-" * 80 + "\n")
            for issue_type, issues in self.errors.items():
                f.write(f"{issue_type.replace('_', ' ').title():30s} {len(issues):,} records\n")
            f.write("\n")
            
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 80 + "\n")
            if self.stats['text_file_missing'] > 0:
                f.write(f"- Regenerate {self.stats['text_file_missing']:,} missing text reports\n")
            if self.stats['raw_json_missing'] > 0:
                f.write(f"- Re-fetch {self.stats['raw_json_missing']:,} records missing raw JSON\n")
            if total_missing_files > 0:
                f.write(f"- Re-download {total_missing_files:,} missing attachment files\n")
            if self.stats['fully_valid'] == total:
                f.write("- All records validated successfully - no action required\n")
            f.write("\n")
            
        self.logger.info(f"Executive summary: {output_path}")
        
    def generate_detailed_csv(self, output_path: Path):
        """Generate detailed CSV with all validation results"""
        fieldnames = [
            'tip',
            'inspection_id',
            'inspection_date',
            'processing_status',
            'validation_status',
            'text_file_exists',
            'raw_json_exists',
            'expected_attachments',
            'found_attachments',
            'attachment_files_ok',
            'attachment_files_missing',
            'issues',
            'text_file_path'
        ]
        
        sorted_results = sorted(self.results, key=lambda x: x['inspection_date'], reverse=True)
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in sorted_results:
                row = {
                    'tip': result['tip'],
                    'inspection_id': result['inspection_id'],
                    'inspection_date': result['inspection_date'],
                    'processing_status': result['processing_status'],
                    'validation_status': result['validation_status'],
                    'text_file_exists': 'Yes' if result['text_file_exists'] else 'No',
                    'raw_json_exists': 'Yes' if result['raw_json_exists'] else 'No',
                    'expected_attachments': result['expected_attachments'],
                    'found_attachments': result['found_attachments'],
                    'attachment_files_ok': result['attachment_files_ok'],
                    'attachment_files_missing': result['attachment_files_missing'],
                    'issues': '; '.join(result['issues']) if result['issues'] else 'None',
                    'text_file_path': result['text_file_path']
                }
                writer.writerow(row)
                
        self.logger.info(f"Detailed CSV: {output_path}")
        
    def generate_by_status_report(self, output_path: Path):
        """Generate validation results grouped by processing status"""
        with open(output_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write(f"{self.full_name.upper()} VALIDATION BY PROCESSING STATUS\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            for status in sorted(self.stats_by_status.keys()):
                stats = self.stats_by_status[status]
                total = stats['total']
                
                f.write(f"PROCESSING STATUS: {status.upper()}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Total Records:              {total:,}\n")
                if total > 0:
                    f.write(f"Text Files Found:           {stats['text_file_exists']:,} ({stats['text_file_exists']/total*100:.1f}%)\n")
                    f.write(f"Raw JSON Present:           {stats['raw_json_exists']:,} ({stats['raw_json_exists']/total*100:.1f}%)\n")
                    f.write(f"All Attachments OK:         {stats['attachment_files_ok']:,} ({stats['attachment_files_ok']/total*100:.1f}%)\n")
                    f.write(f"Fully Valid:                {stats['fully_valid']:,} ({stats['fully_valid']/total*100:.1f}%)\n")
                f.write("\n")
                
        self.logger.info(f"By-status report: {output_path}")
        
    def generate_error_log(self, output_path: Path):
        """Generate error log with issues grouped by type"""
        with open(output_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write(f"{self.full_name.upper()} DATA VALIDATION - ERROR LOG\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            if not self.errors:
                f.write("No errors found - all records validated successfully\n")
                return
                
            for error_type, error_list in self.errors.items():
                f.write(f"\n{error_type.replace('_', ' ').upper()}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Total Records: {len(error_list)}\n\n")
                
                if error_type == 'text_file_missing':
                    for err in error_list:
                        f.write(f"  TIP: {err['tip']}\n")
                        f.write(f"  Inspection ID: {err['inspection_id']}\n")
                        f.write(f"  Processing Status: {err['processing_status']}\n")
                        f.write(f"  Expected Folder: {err['expected_folder']}\n")
                        f.write("\n")
                        
                elif error_type == 'raw_json_missing':
                    for err in error_list:
                        f.write(f"  TIP: {err['tip']}\n")
                        f.write(f"  Inspection ID: {err['inspection_id']}\n")
                        f.write(f"  Processing Status: {err['processing_status']}\n")
                        f.write("\n")
                        
                elif error_type == 'attachment_files_missing':
                    for err in error_list:
                        f.write(f"  TIP: {err['tip']}\n")
                        f.write(f"  Inspection ID: {err['inspection_id']}\n")
                        f.write(f"  Processing Status: {err['processing_status']}\n")
                        f.write(f"  Missing Files: {err['missing_count']}\n")
                        for missing_file in err['missing_files']:
                            f.write(f"    - {missing_file}\n")
                        f.write("\n")
                        
        self.logger.info(f"Error log: {output_path}")
        
    def generate_remediation_csv(self, output_path: Path):
        """Generate CSV of TIPs that need reprocessing"""
        failed_tips = [
            result['tip'] 
            for result in self.results 
            if result['validation_status'] in ('INVALID', 'PARTIAL')
        ]
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['TIP'])
            for tip in failed_tips:
                writer.writerow([tip])
                
        self.logger.info(f"Remediation CSV: {output_path} ({len(failed_tips)} TIPs)")
        
        return len(failed_tips)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate Noggin inspection data integrity',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Object types:
  LCD  Load Compliance Check (Driver/Loader)
  LCS  Load Compliance Check (Supervisor/Manager)
  CCC  Coupling Compliance Check
  FPI  Forklift Prestart Inspection
  SO   Site Observations
  TA   Trailer Audits

Example:
  %(prog)s LCD
  %(prog)s CCC
        """
    )
    
    parser.add_argument(
        'object_type',
        choices=list(CONFIG_FILES.keys()),
        help='Object type abbreviation to validate'
    )
    
    args = parser.parse_args()
    
    try:
        script_dir = Path(__file__).parent
        base_dir = script_dir.parent
        
        specific_config_file = CONFIG_FILES[args.object_type]
        
        config = ConfigLoader(
            str(base_dir / 'config' / 'base_config.ini'),
            str(base_dir / 'config' / specific_config_file)
        )
        
        logger_manager = LoggerManager(config, script_name=f'validate_{args.object_type.lower()}_data')
        logger_manager.configure_application_logger()
        logger = logging.getLogger(__name__)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        object_type_config = config.get_object_type_config()
        abbreviation = object_type_config.get('abbreviation', args.object_type)
        full_name = object_type_config.get('full_name', args.object_type)
        
        base_output_path = Path(config.get('paths', 'base_output_path'))
        output_dir = base_output_path / abbreviation / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        validator = NogginDataValidator(config, logger)
        validator.run_validation()
        
        logger.info("Generating reports...")
        validator.generate_executive_summary(output_dir / f'{abbreviation.lower()}_validation_summary_{timestamp}.txt')
        validator.generate_detailed_csv(output_dir / f'{abbreviation.lower()}_validation_detailed_{timestamp}.csv')
        validator.generate_by_status_report(output_dir / f'{abbreviation.lower()}_validation_by_status_{timestamp}.txt')
        validator.generate_error_log(output_dir / f'{abbreviation.lower()}_validation_errors_{timestamp}.txt')
        
        failed_count = validator.generate_remediation_csv(output_dir / f'{abbreviation.lower()}_remediation_tips_{timestamp}.csv')
        
        logger.info("=" * 80)
        logger.info("Validation complete")
        logger.info(f"Reports saved to: {output_dir}")
        logger.info(f"Failed/Partial records: {failed_count}")
        if failed_count > 0:
            logger.info(f"To reprocess failed records, run:")
            logger.info(f"  python noggin_processor_unified.py {abbreviation} --csv {output_dir / f'{abbreviation.lower()}_remediation_tips_{timestamp}.csv'}")
        logger.info("=" * 80)
        
        return 0
        
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"Validation error: {e}")
        if 'logger' in locals():
            logger.error(f"Validation error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())