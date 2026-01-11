"""
Test Script for SFTP TIP Downloader

Tests the file parsing and object type detection without requiring
an actual SFTP connection. Useful for development and verification.

Usage:
    python test_sftp_downloader.py
    python test_sftp_downloader.py --csv-file /path/to/test.csv
"""

from __future__ import annotations
import argparse
import csv
import logging
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Any

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# Import functions from main module (with fallback for testing)
try:
    from sftp_download_tips import (
        OBJECT_TYPE_SIGNATURES,
        detect_object_type,
        extract_tips_from_csv,
        find_column_index,
        parse_date
    )
except ImportError:
    logger.warning("Could not import from sftp_download_tips, using inline definitions")
    
    OBJECT_TYPE_SIGNATURES = {
        'couplingId': {'abbreviation': 'CCC', 'full_name': 'Coupling Compliance Check', 'id_prefix': 'C - '},
        'forkliftPrestartInspectionId': {'abbreviation': 'FPI', 'full_name': 'Forklift Prestart Inspection', 'id_prefix': 'FL - Inspection - '},
        'lcsInspectionId': {'abbreviation': 'LCS', 'full_name': 'Load Compliance Check Supervisor/Manager', 'id_prefix': 'LCS - '},
        'lcdInspectionId': {'abbreviation': 'LCC', 'full_name': 'Load Compliance Check Driver/Loader', 'id_prefix': 'LCD - '},
        'siteObservationId': {'abbreviation': 'SO', 'full_name': 'Site Observations', 'id_prefix': 'SO - '},
        'trailerAuditId': {'abbreviation': 'TA', 'full_name': 'Trailer Audits', 'id_prefix': 'TA - '}
    }


def create_test_csv(object_type: str, num_rows: int = 5) -> Path:
    """Create a test CSV file for specified object type"""
    signatures = {
        'CCC': {
            'headers': ['nogginId', 'couplingId', 'personCompleting', 'date', 'team', 'vehicleId'],
            'id_prefix': 'C - ',
            'id_num_format': '012510'
        },
        'FPI': {
            'headers': [' ', 'goldstarAsset', 'preStartStatus', 'assetType', 'assetId', 'assetName', 
                       'personsCompleting', 'team', 'forkliftPrestartInspectionId', 'date'],
            'id_prefix': 'FL - Inspection - ',
            'id_num_format': '00477'
        },
        'LCS': {
            'headers': ['nogginId', 'lcsInspectionId', 'trailer', 'trailer2', 'trailer3', 'trailerId',
                       'trailerId2', 'trailerId3', 'jobNumber', 'customerClient', 'runNumber',
                       'driverLoaderName', 'vehicleId', 'vehicle', 'goldstarOrContactorList',
                       'contractorName', 'whichDepartmentDoesTheLoadBelongTo', 'team', 'inspectedBy', 'date'],
            'id_prefix': 'LCS - ',
            'id_num_format': '000004'
        },
        'LCC': {
            'headers': ['nogginId', 'lcdInspectionId', 'date', 'inspectedBy', 'vehicle', 'vehicleId'],
            'id_prefix': 'LCD - ',
            'id_num_format': '047985'
        },
        'SO': {
            'headers': ['nogginId', 'siteObservationId', 'date', 'siteManager', 'department', 'personInvolved'],
            'id_prefix': 'SO - ',
            'id_num_format': '00057'
        },
        'TA': {
            'headers': [' ', 'trailerAuditId', 'team', 'date', 'inspectedBy', 'regularDriver'],
            'id_prefix': 'TA - ',
            'id_num_format': '00003'
        }
    }
    
    if object_type not in signatures:
        raise ValueError(f"Unknown object type: {object_type}")
    
    sig = signatures[object_type]
    
    temp_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8'
    )
    
    writer = csv.writer(temp_file)
    writer.writerow(sig['headers'])
    
    # Generate test data rows
    import hashlib
    for i in range(num_rows):
        tip = hashlib.sha256(f"test_tip_{object_type}_{i}".encode()).hexdigest()
        inspection_id = f"{sig['id_prefix']}{int(sig['id_num_format']) + i:06d}"
        date = f"{15 + i}-Jun-25"
        
        # Build row based on header count
        row = [tip]
        for j, header in enumerate(sig['headers'][1:], start=1):
            if 'Id' in header and header.lower() != 'nogginid':
                if header == sig['headers'][1] if object_type in ['FPI', 'TA'] else False:
                    row.append(f"hash_{j}")
                elif 'Inspection' in header or header in ['couplingId', 'lcsInspectionId', 'lcdInspectionId', 
                                                          'siteObservationId', 'trailerAuditId']:
                    row.append(inspection_id)
                else:
                    row.append(f"ID_{j}")
            elif header.lower() == 'date':
                row.append(date)
            elif header == ' ':
                continue  # First column is already TIP
            else:
                row.append(f"value_{j}")
        
        # Adjust row if first header is blank (TIP is in first column)
        if sig['headers'][0] == ' ':
            writer.writerow(row)
        else:
            writer.writerow(row)
    
    temp_file.close()
    return Path(temp_file.name)


def test_object_type_detection():
    """Test object type detection for all known types"""
    logger.info("=" * 60)
    logger.info("TEST: Object Type Detection")
    logger.info("=" * 60)
    
    results = []
    
    for abbrev in ['CCC', 'FPI', 'LCS', 'LCC', 'SO', 'TA']:
        try:
            csv_path = create_test_csv(abbrev, num_rows=3)
            
            # Read headers to show what we're testing
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
            
            logger.info(f"\nTesting {abbrev}:")
            logger.info(f"  Headers: {headers[:5]}...")
            
            # Test detection
            try:
                from sftp_download_tips import detect_object_type
                id_column, metadata = detect_object_type(csv_path)
                detected = metadata['abbreviation']
            except ImportError:
                # Fallback detection
                clean_headers = [h.strip() for h in headers]
                detected = None
                for id_col, meta in OBJECT_TYPE_SIGNATURES.items():
                    if id_col in clean_headers:
                        detected = meta['abbreviation']
                        id_column = id_col
                        break
            
            if detected == abbrev:
                logger.info(f"  Result: PASS - Detected {detected} via column '{id_column}'")
                results.append((abbrev, True, detected))
            else:
                logger.error(f"  Result: FAIL - Expected {abbrev}, got {detected}")
                results.append((abbrev, False, detected))
            
            csv_path.unlink()
            
        except Exception as e:
            logger.error(f"  Result: ERROR - {e}")
            results.append((abbrev, False, str(e)))
    
    passed = sum(1 for _, success, _ in results if success)
    logger.info(f"\nObject Type Detection: {passed}/{len(results)} tests passed")
    
    return all(success for _, success, _ in results)


def test_tip_extraction():
    """Test TIP extraction from CSV files"""
    logger.info("=" * 60)
    logger.info("TEST: TIP Extraction")
    logger.info("=" * 60)
    
    for abbrev in ['CCC', 'LCS']:
        try:
            csv_path = create_test_csv(abbrev, num_rows=5)
            
            logger.info(f"\nTesting extraction from {abbrev} CSV:")
            
            # Find ID column
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = [h.strip() for h in next(reader)]
            
            id_column = None
            metadata = None
            for col, meta in OBJECT_TYPE_SIGNATURES.items():
                if col in headers:
                    id_column = col
                    metadata = meta
                    break
            
            if id_column is None:
                logger.error("  Could not find ID column")
                continue
            
            # Extract TIPs
            try:
                from sftp_download_tips import extract_tips_from_csv
                tips = extract_tips_from_csv(csv_path, id_column, metadata)
            except ImportError:
                # Manual extraction for testing
                tips = []
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    headers = [h.strip() for h in next(reader)]
                    
                    id_idx = headers.index(id_column) if id_column in headers else -1
                    date_idx = headers.index('date') if 'date' in [h.lower() for h in headers] else -1
                    
                    for row in reader:
                        if row and row[0].strip():
                            tips.append({
                                'tip': row[0].strip(),
                                'inspection_id': row[id_idx] if id_idx >= 0 else None,
                                'inspection_date': row[date_idx] if date_idx >= 0 else None
                            })
            
            logger.info(f"  Extracted {len(tips)} TIPs")
            
            if tips:
                logger.info(f"  First TIP:")
                logger.info(f"    tip: {tips[0]['tip'][:32]}...")
                logger.info(f"    inspection_id: {tips[0].get('inspection_id')}")
                logger.info(f"    inspection_date: {tips[0].get('inspection_date')}")
            
            csv_path.unlink()
            
        except Exception as e:
            logger.error(f"  Error: {e}")
            import traceback
            traceback.print_exc()


def test_date_parsing():
    """Test date parsing for various formats"""
    logger.info("=" * 60)
    logger.info("TEST: Date Parsing")
    logger.info("=" * 60)
    
    test_dates = [
        ('16-Jun-25', '2025-06-16'),
        ('4-Jun-24', '2024-06-04'),
        ('20-Jun-25', '2025-06-20'),
        ('3-Oct-24', '2024-10-03'),
        ('2025-01-15', '2025-01-15'),
        ('15/06/2025', '2025-06-15'),
        ('invalid', None),
    ]
    
    try:
        from sftp_download_tips import parse_date
    except ImportError:
        from datetime import datetime
        def parse_date(date_str):
            formats = ['%d-%b-%y', '%d-%b-%Y', '%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                except ValueError:
                    continue
            return None
    
    passed = 0
    for input_date, expected in test_dates:
        result = parse_date(input_date)
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        logger.info(f"  {input_date:15} -> {result or 'None':12} (expected: {expected or 'None':12}) [{status}]")
    
    logger.info(f"\nDate Parsing: {passed}/{len(test_dates)} tests passed")


def test_with_real_file(csv_path: str):
    """Test with a real CSV file"""
    logger.info("=" * 60)
    logger.info(f"TEST: Real File - {csv_path}")
    logger.info("=" * 60)
    
    path = Path(csv_path)
    if not path.exists():
        logger.error(f"File not found: {csv_path}")
        return
    
    # Read and display headers
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = [h.strip() for h in next(reader)]
    
    logger.info(f"Headers ({len(headers)} columns):")
    for i, h in enumerate(headers[:10]):
        logger.info(f"  [{i}] {h}")
    if len(headers) > 10:
        logger.info(f"  ... and {len(headers) - 10} more")
    
    # Detect object type
    id_column = None
    metadata = None
    for col, meta in OBJECT_TYPE_SIGNATURES.items():
        if col in headers:
            id_column = col
            metadata = meta
            logger.info(f"\nDetected object type: {meta['abbreviation']} ({meta['full_name']})")
            logger.info(f"ID column: {col}")
            break
    
    if id_column is None:
        logger.warning("Could not detect object type from headers")
        return
    
    # Count rows and show sample
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        
        tip_idx = 0
        id_idx = headers.index(id_column) if id_column in headers else -1
        date_idx = -1
        for i, h in enumerate(headers):
            if h.lower() == 'date':
                date_idx = i
                break
        
        row_count = 0
        sample_rows = []
        
        for row in reader:
            if row and row[tip_idx].strip():
                row_count += 1
                if len(sample_rows) < 3:
                    sample_rows.append({
                        'tip': row[tip_idx][:32] + '...',
                        'id': row[id_idx] if id_idx >= 0 and len(row) > id_idx else None,
                        'date': row[date_idx] if date_idx >= 0 and len(row) > date_idx else None
                    })
    
    logger.info(f"\nTotal data rows: {row_count}")
    logger.info("\nSample rows:")
    for i, sample in enumerate(sample_rows, 1):
        logger.info(f"  Row {i}: tip={sample['tip']}, id={sample['id']}, date={sample['date']}")


def main():
    parser = argparse.ArgumentParser(description='Test SFTP TIP Downloader functions')
    parser.add_argument('--csv-file', type=str, help='Path to real CSV file to test')
    parser.add_argument('--skip-synthetic', action='store_true', help='Skip synthetic tests')
    
    args = parser.parse_args()
    
    logger.info("SFTP TIP Downloader Test Suite")
    logger.info("=" * 60)
    
    if not args.skip_synthetic:
        test_object_type_detection()
        print()
        
        test_date_parsing()
        print()
        
        test_tip_extraction()
        print()
    
    if args.csv_file:
        test_with_real_file(args.csv_file)
    
    logger.info("\nTest suite complete")


if __name__ == "__main__":
    main()
