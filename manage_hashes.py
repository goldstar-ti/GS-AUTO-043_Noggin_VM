#!/usr/bin/env python3
"""
Hash Management CLI Tool with File Selection Support

Manages entity hash imports, exports, and lookups with optional GUI file picker.
"""

from __future__ import annotations
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional
from tabulate import tabulate

from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, HashManager

logger: logging.Logger = logging.getLogger(__name__)


def select_file_gui(title: str = "Select CSV File", filetypes: list = None) -> Optional[Path]:
    """
    Open GUI file picker dialog
    
    Args:
        title: Dialog window title
        filetypes: List of (description, pattern) tuples
        
    Returns:
        Selected file path or None if cancelled
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("Error: tkinter not available. Install with: sudo apt install python3-tk")
        return None
    
    # Set default filetypes
    if filetypes is None:
        filetypes = [
            ("CSV files", "*.csv"),
            ("All files", "*.*")
        ]
    
    # Create root window (hidden)
    root = tk.Tk()
    root.withdraw()  # Hide main window
    root.attributes('-topmost', True)  # Bring dialog to front
    
    # Open file dialog
    file_path = filedialog.askopenfilename(
        title=title,
        filetypes=filetypes,
        initialdir=str(Path.cwd())
    )
    
    root.destroy()
    
    if file_path:
        return Path(file_path)
    return None


def get_file_path(provided_path: Optional[str], use_gui: bool, operation: str, entity_type: str) -> Optional[Path]:
    """
    Get file path from argument, GUI, or prompt
    
    Args:
        provided_path: Path provided via command line
        use_gui: Whether to use GUI file picker
        operation: Operation name (for prompts)
        entity_type: Entity type (for prompts)
        
    Returns:
        Path object or None
    """
    # If path provided via CLI, use it
    if provided_path:
        file_path = Path(provided_path)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            return None
        return file_path
    
    # If GUI requested, open file picker
    if use_gui:
        print(f"Opening file picker for {operation} {entity_type} hashes...")
        file_path = select_file_gui(
            title=f"Select CSV file to {operation} {entity_type} hashes",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            print(f"Selected: {file_path}")
            return file_path
        else:
            print("No file selected")
            return None
    
    # Otherwise, prompt for path
    path_input = input(f"Enter path to CSV file for {operation} {entity_type} hashes: ").strip()
    if not path_input:
        print("No file path provided")
        return None
    
    file_path = Path(path_input)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return None
    
    return file_path


def cmd_import(args: argparse.Namespace, hash_manager: HashManager) -> int:
    """Import entity hashes from CSV file"""
    
    # Get file path
    csv_path = get_file_path(
        args.csv_file,
        args.gui,
        "import",
        args.entity_type
    )
    
    if not csv_path:
        return 1
    
    # Confirm import
    if not args.yes:
        response = input(f"Import {args.entity_type} hashes from {csv_path.name}? (y/n): ")
        if response.lower() != 'y':
            print("Import cancelled")
            return 0
    
    logger.info(f"Importing {args.entity_type} hashes from {csv_path}")
    
    try:
        imported, duplicates, errors = hash_manager.import_hashes_from_csv(
            args.entity_type,
            csv_path,
            source=args.source or 'manual_import'
        )
        
        print(f"\n✓ Import Complete:")
        print(f"  Imported:   {imported}")
        print(f"  Duplicates: {duplicates}")
        print(f"  Errors:     {errors}")
        
        if errors > 0:
            print(f"\n⚠ Warning: {errors} errors occurred during import")
            return 1
        
        return 0
    
    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        logger.error(f"Import failed: {e}", exc_info=True)
        return 1


def cmd_export_unknown(args: argparse.Namespace, hash_manager: HashManager) -> int:
    """Export unknown hashes to CSV file"""
    
    # Determine output path
    if args.output_file:
        output_path = Path(args.output_file)
    elif args.gui:
        print(f"Opening save dialog for {args.entity_type} unknown hashes...")
        
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ImportError:
            print("Error: tkinter not available")
            return 1
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        default_filename = f"unknown_{args.entity_type}_{Path.cwd().stem}.csv"
        
        file_path = filedialog.asksaveasfilename(
            title=f"Save unknown {args.entity_type} hashes",
            defaultextension=".csv",
            initialfile=default_filename,
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )
        
        root.destroy()
        
        if not file_path:
            print("Export cancelled")
            return 0
        
        output_path = Path(file_path)
    else:
        # Prompt for path
        default = f"unknown_{args.entity_type}.csv"
        path_input = input(f"Enter output file path [{default}]: ").strip()
        output_path = Path(path_input) if path_input else Path(default)
    
    logger.info(f"Exporting unknown {args.entity_type} hashes to {output_path}")
    
    try:
        count = hash_manager.export_unknown_hashes(args.entity_type, output_path)
        
        if count > 0:
            print(f"\n✓ Exported {count} unknown {args.entity_type} hashes to:")
            print(f"  {output_path.absolute()}")
            print(f"\nNext steps:")
            print(f"  1. Open the CSV file and fill in the 'name' column")
            print(f"  2. Re-import with: python manage_hashes.py import {args.entity_type} {output_path}")
        else:
            print(f"\n✓ No unknown {args.entity_type} hashes found")
        
        return 0
    
    except Exception as e:
        print(f"\n✗ Export failed: {e}")
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


def cmd_list(args: argparse.Namespace, hash_manager: HashManager) -> int:
    """List all known hashes for entity type"""
    
    logger.info(f"Listing {args.entity_type} hashes")
    
    try:
        hashes = hash_manager.db_manager.execute_query_dict(
            """
            SELECT hash_value, entity_name, source, created_at
            FROM entity_hashes
            WHERE entity_type = %s
            ORDER BY entity_name
            LIMIT %s
            """,
            (args.entity_type, args.limit)
        )
        
        if not hashes:
            print(f"\nNo {args.entity_type} hashes found")
            return 0
        
        print(f"\n{args.entity_type.upper()} HASHES ({len(hashes)} shown):")
        print("="*80)
        
        table_data = [
            [
                h['hash_value'][:16] + '...',
                h['entity_name'],
                h['source'],
                h['created_at'].strftime('%Y-%m-%d') if h['created_at'] else 'N/A'
            ]
            for h in hashes
        ]
        
        print(tabulate(
            table_data,
            headers=['Hash (truncated)', 'Name', 'Source', 'Created'],
            tablefmt='simple'
        ))
        
        if len(hashes) == args.limit:
            print(f"\n(Showing first {args.limit} results. Use --limit to see more)")
        
        return 0
    
    except Exception as e:
        print(f"\n✗ List failed: {e}")
        logger.error(f"List failed: {e}", exc_info=True)
        return 1


def cmd_stats(args: argparse.Namespace, hash_manager: HashManager) -> int:
    """Display hash statistics"""
    
    logger.info("Generating hash statistics")
    
    try:
        stats = hash_manager.get_hash_statistics()
        
        print("\nHASH STATISTICS:")
        print("="*80)
        
        table_data = []
        for entity_type in ['vehicle', 'trailer', 'department', 'team']:
            known = stats.get(entity_type, {}).get('known', 0)
            unknown = stats.get(entity_type, {}).get('unknown', 0)
            total = known + unknown
            
            if total > 0:
                coverage = (known / total) * 100
                status = "✓" if coverage == 100 else "⚠" if coverage > 90 else "✗"
            else:
                coverage = 0
                status = "-"
            
            table_data.append([
                status,
                entity_type.capitalize(),
                known,
                unknown,
                total,
                f"{coverage:.1f}%"
            ])
        
        print(tabulate(
            table_data,
            headers=['', 'Entity Type', 'Known', 'Unknown', 'Total', 'Coverage'],
            tablefmt='simple'
        ))
        
        # Show warnings
        print()
        for entity_type in ['vehicle', 'trailer', 'department', 'team']:
            unknown = stats.get(entity_type, {}).get('unknown', 0)
            if unknown > 0:
                print(f"⚠ {unknown} unknown {entity_type} hashes need resolution")
                print(f"  Export with: python manage_hashes.py export-unknown {entity_type} --gui")
        
        return 0
    
    except Exception as e:
        print(f"\n✗ Stats failed: {e}")
        logger.error(f"Stats failed: {e}", exc_info=True)
        return 1


def cmd_search(args: argparse.Namespace, hash_manager: HashManager) -> int:
    """Search for hash or name"""
    
    search_term = args.search_term.lower()
    
    logger.info(f"Searching for: {search_term}")
    
    try:
        results = hash_manager.db_manager.execute_query_dict(
            """
            SELECT entity_type, hash_value, entity_name, source
            FROM entity_hashes
            WHERE LOWER(entity_name) LIKE %s
               OR LOWER(hash_value) LIKE %s
            ORDER BY entity_type, entity_name
            LIMIT 50
            """,
            (f"%{search_term}%", f"%{search_term}%")
        )
        
        if not results:
            print(f"\nNo results found for: {args.search_term}")
            return 0
        
        print(f"\nSEARCH RESULTS ({len(results)} found):")
        print("="*80)
        
        table_data = [
            [
                r['entity_type'].capitalize(),
                r['hash_value'][:20] + '...',
                r['entity_name'],
                r['source']
            ]
            for r in results
        ]
        
        print(tabulate(
            table_data,
            headers=['Type', 'Hash (truncated)', 'Name', 'Source'],
            tablefmt='simple'
        ))
        
        return 0
    
    except Exception as e:
        print(f"\n✗ Search failed: {e}")
        logger.error(f"Search failed: {e}", exc_info=True)
        return 1


def main() -> int:
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description='Manage entity hash lookups for Noggin data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import with GUI file picker
  python manage_hashes.py import vehicle --gui
  
  # Import from specific file
  python manage_hashes.py import vehicle vehicles.csv
  
  # Export unknown hashes with save dialog
  python manage_hashes.py export-unknown trailer --gui
  
  # List all vehicles
  python manage_hashes.py list vehicle
  
  # Show statistics
  python manage_hashes.py stats
  
  # Search for a hash or name
  python manage_hashes.py search "TRUCK-001"
        """
    )
    
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Use GUI file picker (requires tkinter)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import entity hashes from CSV')
    import_parser.add_argument('entity_type', choices=['vehicle', 'trailer', 'department', 'team'])
    import_parser.add_argument('csv_file', nargs='?', help='Path to CSV file (optional with --gui)')
    import_parser.add_argument('--source', help='Source identifier for import')
    import_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompt')
    
    # Export unknown command
    export_parser = subparsers.add_parser('export-unknown', help='Export unknown hashes to CSV')
    export_parser.add_argument('entity_type', choices=['vehicle', 'trailer', 'department', 'team'])
    export_parser.add_argument('output_file', nargs='?', help='Output CSV file path (optional with --gui)')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all known hashes')
    list_parser.add_argument('entity_type', choices=['vehicle', 'trailer', 'department', 'team'])
    list_parser.add_argument('--limit', type=int, default=50, help='Maximum results to show (default: 50)')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Display hash statistics')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for hash or name')
    search_parser.add_argument('search_term', help='Search term (hash or name)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize components
    config = ConfigLoader(
        'config/base_config.ini',
        'config/load_compliance_check_config.ini'
    )
    
    logger_manager = LoggerManager(config, script_name='manage_hashes')
    logger_manager.configure_application_logger()
    
    db_manager = DatabaseConnectionManager(config)
    hash_manager = HashManager(config, db_manager)
    
    try:
        # Execute command
        if args.command == 'import':
            return cmd_import(args, hash_manager)
        elif args.command == 'export-unknown':
            return cmd_export_unknown(args, hash_manager)
        elif args.command == 'list':
            return cmd_list(args, hash_manager)
        elif args.command == 'stats':
            return cmd_stats(args, hash_manager)
        elif args.command == 'search':
            return cmd_search(args, hash_manager)
        else:
            print(f"Unknown command: {args.command}")
            return 1
    
    finally:
        db_manager.close_all()


if __name__ == "__main__":
    sys.exit(main())