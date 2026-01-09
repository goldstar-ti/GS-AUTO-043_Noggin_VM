"""
Hash Management CLI Tool

Simple command-line interface for hash lookup operations.
For bulk imports, use hash_lookup_sync.py instead.

Commands:
    stats   - Display hash statistics
    search  - Search for hash or name
    lookup  - Lookup a specific hash
"""

from __future__ import annotations
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

from tabulate import tabulate

logger: logging.Logger = logging.getLogger(__name__)


def cmd_stats(args: argparse.Namespace, hash_manager: 'HashManager') -> int:
    """Display hash statistics"""
    
    logger.info("Generating hash statistics")
    
    try:
        stats = hash_manager.get_hash_statistics()
        
        print("\n" + "=" * 60)
        print("HASH LOOKUP STATISTICS")
        print("=" * 60)
        
        print("\nBy Lookup Type:")
        print("-" * 40)
        
        table_data = []
        for lookup_type in ['vehicle', 'trailer', 'team', 'department', 'uhf', 'unknown']:
            type_stats = stats.get(lookup_type, {})
            count = type_stats.get('count', 0) if isinstance(type_stats, dict) else 0
            
            if count > 0:
                table_data.append([lookup_type.capitalize(), count])
        
        if table_data:
            print(tabulate(table_data, headers=['Type', 'Count'], tablefmt='simple'))
        
        print(f"\nTotal: {stats.get('total', 0)}")
        
        # Source type breakdown
        by_source = stats.get('by_source_type', {})
        if by_source:
            print("\nBy Source Type (Noggin classification):")
            print("-" * 40)
            
            source_data = [[source, count] for source, count in sorted(by_source.items())]
            print(tabulate(source_data, headers=['Source Type', 'Count'], tablefmt='simple'))
        
        # Cache stats
        cache_stats = hash_manager.get_cache_stats()
        print(f"\nCache: {'loaded' if cache_stats['cache_loaded'] else 'not loaded'}, "
              f"{cache_stats['cache_size']} entries")
        
        print("=" * 60 + "\n")
        return 0
        
    except Exception as e:
        print(f"\nError getting statistics: {e}")
        logger.error(f"Stats failed: {e}", exc_info=True)
        return 1


def cmd_search(args: argparse.Namespace, hash_manager: 'HashManager') -> int:
    """Search for hash or name"""
    
    search_term = args.search_term
    logger.info(f"Searching for: {search_term}")
    
    try:
        results = hash_manager.search_hash(search_term)
        
        if not results:
            print(f"\nNo results found for: {search_term}")
            return 0
        
        print(f"\nSEARCH RESULTS ({len(results)} found):")
        print("=" * 80)
        
        table_data = []
        for r in results:
            table_data.append([
                r['lookup_type'].capitalize(),
                r['source_type'] or '-',
                r['resolved_value'],
                r['tip_hash'][:20] + '...'
            ])
        
        print(tabulate(
            table_data,
            headers=['Type', 'Source', 'Name', 'Hash (truncated)'],
            tablefmt='simple'
        ))
        
        if len(results) >= 50:
            print("\n(Results limited to 50. Refine your search for more specific results.)")
        
        return 0
        
    except Exception as e:
        print(f"\nSearch failed: {e}")
        logger.error(f"Search failed: {e}", exc_info=True)
        return 1


def cmd_lookup(args: argparse.Namespace, hash_manager: 'HashManager') -> int:
    """Lookup a specific hash"""
    
    tip_hash = args.hash_value
    logger.info(f"Looking up hash: {tip_hash}")
    
    try:
        metadata = hash_manager.lookup_hash_with_metadata(tip_hash)
        
        if not metadata:
            print(f"\nHash not found: {tip_hash}")
            return 1
        
        print(f"\nHASH LOOKUP RESULT:")
        print("=" * 60)
        print(f"  Hash:          {tip_hash}")
        print(f"  Resolved Name: {metadata['resolved_value']}")
        print(f"  Lookup Type:   {metadata['lookup_type']}")
        print(f"  Source Type:   {metadata['source_type'] or '-'}")
        print("=" * 60 + "\n")
        
        return 0
        
    except Exception as e:
        print(f"\nLookup failed: {e}")
        logger.error(f"Lookup failed: {e}", exc_info=True)
        return 1


def cmd_list_type(args: argparse.Namespace, hash_manager: 'HashManager') -> int:
    """List all entries of a specific lookup_type"""
    
    lookup_type = args.lookup_type
    logger.info(f"Listing all {lookup_type} entries")
    
    try:
        results = hash_manager.get_by_type(lookup_type)
        
        if not results:
            print(f"\nNo {lookup_type} entries found")
            return 0
        
        print(f"\n{lookup_type.upper()} ENTRIES ({len(results)} total):")
        print("=" * 80)
        
        # Apply limit
        display_results = results[:args.limit]
        
        table_data = []
        for r in display_results:
            table_data.append([
                r['resolved_value'],
                r['source_type'] or '-',
                r['tip_hash'][:24] + '...'
            ])
        
        print(tabulate(
            table_data,
            headers=['Name', 'Source Type', 'Hash (truncated)'],
            tablefmt='simple'
        ))
        
        if len(results) > args.limit:
            print(f"\n(Showing {args.limit} of {len(results)}. Use --limit to see more.)")
        
        return 0
        
    except Exception as e:
        print(f"\nList failed: {e}")
        logger.error(f"List failed: {e}", exc_info=True)
        return 1


def main() -> int:
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description='Hash lookup CLI tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show statistics
    python manage_hashes.py stats
    
    # Search for a name
    python manage_hashes.py search "MB26"
    python manage_hashes.py search "Air Liquide"
    
    # Lookup a specific hash
    python manage_hashes.py lookup 02409bd3dd8355a53b3cef56e0eb6440b653bfad9579e7e602528db25cfbdc34
    
    # List all vehicles
    python manage_hashes.py list vehicle
    
    # List all trailers (first 100)
    python manage_hashes.py list trailer --limit 100

Note: For importing/syncing hash data, use hash_lookup_sync.py instead.
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Stats command
    subparsers.add_parser('stats', help='Display hash statistics')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for hash or name')
    search_parser.add_argument('search_term', help='Search term (name or partial hash)')
    
    # Lookup command
    lookup_parser = subparsers.add_parser('lookup', help='Lookup a specific hash')
    lookup_parser.add_argument('hash_value', help='Full hash value to lookup')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all entries of a type')
    list_parser.add_argument('lookup_type', 
                            choices=['vehicle', 'trailer', 'team', 'department', 'uhf'],
                            help='Lookup type to list')
    list_parser.add_argument('--limit', type=int, default=50, 
                            help='Maximum results to show (default: 50)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Import dependencies
    sys.path.insert(0, str(Path(__file__).parent))
    from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, HashManager
    
    # Initialise components
    config = ConfigLoader(
        'config/base_config.ini',
        'config/load_compliance_check_config.ini'
    )
    
    logger_manager = LoggerManager(config, script_name='manage_hashes')
    logger_manager.configure_application_logger()
    
    db_manager = DatabaseConnectionManager(config)
    hash_manager = HashManager(config, db_manager)
    
    try:
        if args.command == 'stats':
            return cmd_stats(args, hash_manager)
        elif args.command == 'search':
            return cmd_search(args, hash_manager)
        elif args.command == 'lookup':
            return cmd_lookup(args, hash_manager)
        elif args.command == 'list':
            return cmd_list_type(args, hash_manager)
        else:
            print(f"Unknown command: {args.command}")
            return 1
    
    finally:
        db_manager.close_all()


if __name__ == "__main__":
    sys.exit(main())