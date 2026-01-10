"""
Unified Noggin Processor

Processes any object type based on command line argument.
This is the recommended script for the continuous processor and manual invocations.

Usage:
    python noggin_processor_unified.py LCD                    # Process LCD from default CSV
    python noggin_processor_unified.py CCC --csv tips.csv     # Process CCC from specific CSV
    python noggin_processor_unified.py FPI --database         # Process FPI from database queue
    python noggin_processor_unified.py TA --tip ABC123...     # Process single TA TIP
    
Supported object types:
    LCD - Load Compliance Check (Driver/Loader)
    LCS - Load Compliance Check (Supervisor/Manager)
    CCC - Coupling Compliance Check
    FPI - Forklift Prestart Inspection
    SO  - Site Observations
    TA  - Trailer Audits
"""

import sys
import argparse
import logging
from pathlib import Path

from processors import ObjectProcessor

logger = logging.getLogger(__name__)

# Map abbreviations to config files
CONFIG_FILES = {
    'LCD': 'config/load_compliance_check_config.ini',
    'LCS': 'config/load_compliance_check_supervisor_manager_config.ini',
    'CCC': 'config/coupling_compliance_check_config.ini',
    'FPI': 'config/forklift_prestart_inspection_config.ini',
    'SO': 'config/site_observations_config.ini',
    'TA': 'config/trailer_audits_config.ini',
}

# Full names for help text
OBJECT_TYPE_NAMES = {
    'LCD': 'Load Compliance Check (Driver/Loader)',
    'LCS': 'Load Compliance Check (Supervisor/Manager)',
    'CCC': 'Coupling Compliance Check',
    'FPI': 'Forklift Prestart Inspection',
    'SO': 'Site Observations',
    'TA': 'Trailer Audits',
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Process Noggin inspection records',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Object types:
  LCD  Load Compliance Check (Driver/Loader)
  LCS  Load Compliance Check (Supervisor/Manager)
  CCC  Coupling Compliance Check
  FPI  Forklift Prestart Inspection
  SO   Site Observations
  TA   Trailer Audits

Examples:
  %(prog)s LCD                         Process LCD from default CSV
  %(prog)s CCC --csv ccc_tips.csv      Process CCC from specific CSV
  %(prog)s FPI --database              Process FPI from database queue
  %(prog)s TA --tip abc123def456...    Process single TA TIP
        """
    )
    
    parser.add_argument(
        'object_type',
        choices=list(CONFIG_FILES.keys()),
        help='Object type abbreviation'
    )
    parser.add_argument(
        '--csv',
        help='Path to CSV file containing TIPs'
    )
    parser.add_argument(
        '--database',
        action='store_true',
        help='Process TIPs from database queue instead of CSV'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Batch size when processing from database (default: 10)'
    )
    parser.add_argument(
        '--tip',
        help='Process a single TIP'
    )
    parser.add_argument(
        '--base-config',
        default='config/base_config.ini',
        help='Path to base config file (default: config/base_config.ini)'
    )
    
    args = parser.parse_args()
    
    specific_config = CONFIG_FILES[args.object_type]
    
    if not Path(specific_config).exists():
        logger.error(f"Config file not found: {specific_config}")
        print(f"Error: Config file not found: {specific_config}")
        return 1
    
    if not Path(args.base_config).exists():
        logger.error(f"Base config file not found: {args.base_config}")
        print(f"Error: Base config file not found: {args.base_config}")
        return 1
    
    try:
        processor = ObjectProcessor(
            base_config_path=args.base_config,
            specific_config_path=specific_config
        )
        
        object_type_name = OBJECT_TYPE_NAMES[args.object_type]
        logger.info(f"Starting processor for: {object_type_name}")
        
        if args.tip:
            success = processor.process_single(args.tip)
            return 0 if success else 1
        
        processed = processor.run(
            csv_file_path=args.csv,
            batch_size=args.batch_size,
            from_database=args.database
        )
        
        logger.info(f"Processing complete: {processed} TIPs processed for {args.object_type}")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        return 0
        
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        print(f"Error: {e}")
        return 1


def process_object_type(object_type: str, csv_path: str = None, 
                       from_database: bool = False,
                       batch_size: int = 10) -> int:
    """
    Programmatic interface for processing an object type
    
    Args:
        object_type: Abbreviation (LCD, CCC, etc.)
        csv_path: Path to CSV file (optional)
        from_database: Process from database queue
        batch_size: Batch size for database processing
        
    Returns:
        Number of TIPs processed
    """
    if object_type not in CONFIG_FILES:
        raise ValueError(f"Unknown object type: {object_type}. Valid: {list(CONFIG_FILES.keys())}")
    
    processor = ObjectProcessor(
        base_config_path='config/base_config.ini',
        specific_config_path=CONFIG_FILES[object_type]
    )
    
    return processor.run(
        csv_file_path=csv_path,
        batch_size=batch_size,
        from_database=from_database
    )


if __name__ == "__main__":
    sys.exit(main())
