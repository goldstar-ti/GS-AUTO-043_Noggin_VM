#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any

from common import ConfigLoader, LoggerManager, DatabaseConnectionManager
from common.hash_manager import HashManager
import logging

logger: logging.Logger = logging.getLogger(__name__)


def list_unknown_hashes(hash_manager: HashManager, resolved: bool = False) -> None:
    """List unknown hashes"""
    unknown: List[Dict[str, Any]] = hash_manager.get_unknown_hashes(resolved=resolved)
    
    if not unknown:
        status: str = "resolved" if resolved else "unresolved"
        print(f"No {status} unknown hashes found")
        return
    
    print(f"\n{'='*80}")
    print(f"{'RESOLVED' if resolved else 'UNRESOLVED'} UNKNOWN HASHES ({len(unknown)})")
    print(f"{'='*80}\n")
    
    for item in unknown:
        print(f"Type:       {item['lookup_type']}")
        print(f"Hash:       {item['tip_hash']}")
        print(f"First seen: {item['first_encountered']}")
        if resolved:
            print(f"Resolved:   {item['resolved_at']}")
            print(f"Value:      {item['resolved_value']}")
        print("-" * 80)


def resolve_hash(hash_manager: HashManager, tip_hash: str, lookup_type: str, resolved_value: str) -> None:
    """Resolve an unknown hash"""
    success: bool = hash_manager.resolve_unknown_hash(tip_hash, lookup_type, resolved_value)
    
    if success:
        print(f"✓ Successfully resolved: {lookup_type}={tip_hash} -> {resolved_value}")
    else:
        print(f"✗ Failed to resolve hash")
        sys.exit(1)


def search_hashes(hash_manager: HashManager, search_value: str) -> None:
    """Search for hashes by value"""
    results: List[Dict[str, Any]] = hash_manager.search_hash(search_value)
    
    if not results:
        print(f"No hashes found matching: {search_value}")
        return
    
    print(f"\n{'='*80}")
    print(f"SEARCH RESULTS ({len(results)} found)")
    print(f"{'='*80}\n")
    
    for item in results:
        print(f"Type:    {item['lookup_type']}")
        print(f"Hash:    {item['tip_hash']}")
        print(f"Value:   {item['resolved_value']}")
        print(f"Created: {item['created_at']}")
        print(f"Updated: {item['updated_at']}")
        print("-" * 80)


def import_csv(hash_manager: HashManager, csv_file: str) -> None:
    """Import hashes from CSV file"""
    if not Path(csv_file).exists():
        print(f"✗ CSV file not found: {csv_file}")
        sys.exit(1)
    
    print(f"Importing from {csv_file}...")
    imported, skipped = hash_manager.migrate_lookup_table_from_csv(csv_file)
    print(f"✓ Import complete: {imported} imported, {skipped} skipped")


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Manage Noggin hash lookups',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List unresolved unknown hashes
  python manage_hashes.py list
  
  # List resolved unknown hashes
  python manage_hashes.py list --resolved
  
  # Resolve an unknown hash
  python manage_hashes.py resolve --hash abc123def456 --type vehicle --value "RC89"
  
  # Search for hashes by value
  python manage_hashes.py search "RC89"
  
  # Import hashes from CSV
  python manage_hashes.py import lookup_table.csv
        """
    )
    
    parser.add_argument('command', choices=['list', 'resolve', 'search', 'import'],
                       help='Command to execute')
    parser.add_argument('--resolved', action='store_true',
                       help='List resolved hashes (use with list command)')
    parser.add_argument('--hash', type=str,
                       help='Hash value (use with resolve command)')
    parser.add_argument('--type', type=str, choices=['vehicle', 'trailer', 'department', 'team'],
                       help='Lookup type (use with resolve command)')
    parser.add_argument('--value', type=str,
                       help='Resolved value (use with resolve command)')
    parser.add_argument('search_value', nargs='?',
                       help='Search value (use with search command)')
    parser.add_argument('csv_file', nargs='?',
                       help='CSV file path (use with import command)')
    
    args: argparse.Namespace = parser.parse_args()
    
    config: ConfigLoader = ConfigLoader(
        'config/base_config.ini',
        'config/load_compliance_check_config.ini'
    )
    
    logger_manager: LoggerManager = LoggerManager(config, script_name='manage_hashes')
    logger_manager.configure_application_logger()
    
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
    hash_manager: HashManager = HashManager(config, db_manager)
    
    try:
        if args.command == 'list':
            list_unknown_hashes(hash_manager, resolved=args.resolved)
        
        elif args.command == 'resolve':
            if not all([args.hash, args.type, args.value]):
                print("✗ Error: --hash, --type, and --value are required for resolve command")
                sys.exit(1)
            resolve_hash(hash_manager, args.hash, args.type, args.value)
        
        elif args.command == 'search':
            if not args.search_value:
                print("✗ Error: search_value is required for search command")
                sys.exit(1)
            search_hashes(hash_manager, args.search_value)
        
        elif args.command == 'import':
            if not args.csv_file:
                print("✗ Error: csv_file is required for import command")
                sys.exit(1)
            import_csv(hash_manager, args.csv_file)
    
    finally:
        db_manager.close_all()


if __name__ == "__main__":
    main()