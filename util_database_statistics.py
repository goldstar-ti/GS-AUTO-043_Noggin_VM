"""
Database Statistics and Processing Progress

Displays comprehensive status including:
- Service status
- Processing statistics by status
- Object type breakdown
- Hash resolution statistics
- Today's activity
"""

from __future__ import annotations
from common import UNKNOWN_TEXT
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any, List

from common import ConfigLoader, DatabaseConnectionManager


def get_service_status() -> Dict[str, str]:
    """Get systemd service status"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'noggin-processor'],
            capture_output=True,
            text=True
        )
        status: str = result.stdout.strip()
        
        result = subprocess.run(
            ['systemctl', 'is-enabled', 'noggin-processor'],
            capture_output=True,
            text=True
        )
        enabled: str = result.stdout.strip()
        
        return {'status': status, 'enabled': enabled}
    except Exception as e:
        return {'status': 'unknown', 'enabled': 'unknown', 'error': str(e)}


def get_database_statistics(db_manager: DatabaseConnectionManager) -> Dict[str, int]:
    """Get processing statistics from database"""
    query: str = """
        SELECT 
            processing_status,
            COUNT(*) as count
        FROM noggin_data
        GROUP BY processing_status
    """
    
    results: List[Dict[str, Any]] = db_manager.execute_query_dict(query)
    
    stats: Dict[str, int] = {
        'api_error': 0,
        'api_failed': 0,
        'api_retrying': 0,
        'api_success': 0,
        'complete': 0,
        'csv_imported': 0,
        'downloading': 0,
        'failed': 0,
        'ignore': 0,
        'interrupted': 0,
        'not_found': 0,
        'partial': 0,
        'pending': 0,
        'permanently_failed': 0,
        'retrying': 0
    }
    
    for row in results:
        status: str = row['processing_status']
        count: int = row['count']
        if status in stats:
            stats[status] = count
        else:
            stats[status] = count

    return stats


def get_object_type_statistics(db_manager: DatabaseConnectionManager) -> Dict[str, Dict[str, int]]:
    """Get processing statistics by object type"""
    query: str = """
        SELECT 
            object_type,
            processing_status,
            COUNT(*) as count
        FROM noggin_data
        GROUP BY object_type, processing_status
        ORDER BY object_type
    """
    
    results: List[Dict[str, Any]] = db_manager.execute_query_dict(query)
    
    stats: Dict[str, Dict[str, int]] = {}
    
    for row in results:
        obj_type = row['object_type'] or 'Unknown'
        status = row['processing_status']
        count = row['count']
        
        if obj_type not in stats:
            # stats[obj_type] = {'total': 0, 'complete': 0, 'pending': 0, 'failed': 0}
            stats[obj_type] = {'api_error': 0, 'api_failed': 0, 'api_retrying': 0, 'api_success': 0, 'complete': 0, 'csv_imported': 0, 'downloading': 0, 'failed': 0, 'ignore': 0, 'interrupted': 0, 'not_found': 0, 'partial': 0, 'pending': 0, 'permanently_failed': 0, 'retrying': 0}
        
        stats[obj_type]['total'] += count
        if status in stats[obj_type]:
            stats[obj_type][status] = count
    
    return stats

def get_hash_statistics(db_manager: DatabaseConnectionManager) -> Dict[str, Dict[str, int]]:
    """Get hash lookup statistics"""
    stats: Dict[str, Dict[str, int]] = {}
    
    try:
        known_query = """
            SELECT lookup_type, COUNT(*) as count 
            FROM hash_lookup 
            GROUP BY lookup_type
        """
        known_results = db_manager.execute_query_dict(known_query)
        
        for row in known_results:
            lookup_type = row['lookup_type']
            if lookup_type not in stats:
                stats[lookup_type] = {'known': 0, 'unknown': 0}
            stats[lookup_type]['known'] = row['count']

        # TODO unknown_hashes table not being used at the moment. need to update code to use it and remove fallback to hash_lookup_unknown
        # Try unknown_hashes first, fall back to hash_lookup_unknown
        try:
            unknown_query = """
                SELECT lookup_type, COUNT(*) as count 
                FROM unknown_hashes 
                WHERE resolved_at IS NULL
                GROUP BY lookup_type
            """
            unknown_results = db_manager.execute_query_dict(unknown_query)
        except:
            unknown_query = """
                SELECT lookup_type, COUNT(*) as count 
                FROM hash_lookup_unknown 
                WHERE resolved_at IS NULL
                GROUP BY lookup_type
            """
            unknown_results = db_manager.execute_query_dict(unknown_query)
        
        for row in unknown_results:
            lookup_type = row['lookup_type']
            if lookup_type not in stats:
                stats[lookup_type] = {'known': 0, 'unknown': 0}
            stats[lookup_type]['unknown'] = row['count']
        
    except Exception as e:
        pass
    
    return stats


def get_recent_activity(db_manager: DatabaseConnectionManager) -> Dict[str, Any]:
    """Get recent processing activity"""
    query: str = """
        SELECT 
            COUNT(*) as total_today,
            SUM(CASE WHEN processing_status = 'complete' THEN 1 ELSE 0 END) as completed_today
        FROM noggin_data
        WHERE updated_at >= CURRENT_DATE
    """
    
    result: List[Dict[str, Any]] = db_manager.execute_query_dict(query)
    return result[0] if result else {'total_today': 0, 'completed_today': 0}


def get_sftp_activity(db_manager: DatabaseConnectionManager) -> Dict[str, int]:
    """Get SFTP import activity if source_filename column exists"""
    try:
        query = """
            SELECT COUNT(*) as count
            FROM noggin_data
            WHERE source_filename IS NOT NULL
              AND csv_imported_at >= CURRENT_DATE
        """
        result = db_manager.execute_query_dict(query)
        return {'sftp_today': result[0]['count'] if result else 0}
    except:
        return {'sftp_today': 0}


def main() -> None:
    """Display service dashboard"""
    config: ConfigLoader = ConfigLoader(
        'config/base_config.ini',
        'config/load_compliance_check_driver_loader_config.ini'
    )
    
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
    
    try:
        print("\n" + "=" * 80)
        print()
        
        print("NOGGIN PROCESSOR SERVICE DASHBOARD")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Service Status
        service_info: Dict[str, str] = get_service_status()
        print("\nSERVICE STATUS:")
        print(f"  Active:  {service_info['status'].upper()}")
        print(f"  Enabled: {service_info['enabled'].upper()}")
        
        # Processing Statistics
        stats: Dict[str, int] = get_database_statistics(db_manager)
        total: int = sum(stats.values())
        
        print("\nPROCESSING STATISTICS:")
        print(f"  Total Records:     {total:,}")
        print(f"  Complete:          {stats.get('complete', 0):,}")
        print(f"  Pending:           {stats.get('pending', 0):,}")
        print(f"  Failed:            {stats.get('failed', 0):,}")
        print(f"  Partial:           {stats.get('partial', 0):,}")
        print(f"  Interrupted:       {stats.get('interrupted', 0):,}")
        print(f"  API Failed:        {stats.get('api_failed', 0):,}")
        
        # Object Type Breakdown
        obj_stats = get_object_type_statistics(db_manager)
        if obj_stats:
            print("\nOBJECT TYPE BREAKDOWN:")
            print(f"  {'Type':<45} {'Total':>8} {'Done':>8} {'Pending':>8}")
            print(f"  {'-'*45} {'-'*8} {'-'*8} {'-'*8}")
            for obj_type, counts in sorted(obj_stats.items()):
                print(f"  {obj_type:<45} {counts['total']:>8,} {counts.get('complete', 0):>8,} {counts.get('pending', 0):>8,}")
        
        # Hash Statistics
        hash_stats = get_hash_statistics(db_manager)
        if hash_stats:
            print("\nHASH LOOKUP STATUS:")
            total_known = sum(s.get('known', 0) for s in hash_stats.values())
            total_unknown = sum(s.get('unknown', 0) for s in hash_stats.values())
            print(f"  Total Known:       {total_known:,}")
            print(f"  Total Unknown:     {total_unknown:,}")
            
            if total_unknown > 0:
                print("\n  Unknown by Type:")
                for lookup_type, counts in sorted(hash_stats.items()):
                    unknown = counts.get('unknown', 0)
                    if unknown > 0:
                        print(f"    {lookup_type}: {unknown}")
        
        # Today's Activity
        activity: Dict[str, Any] = get_recent_activity(db_manager)
        sftp_activity = get_sftp_activity(db_manager)
        
        print("\nTODAY'S ACTIVITY:")
        print(f"  Total Updated:     {activity.get('total_today', 0):,}")
        print(f"  Completed:         {activity.get('completed_today', 0):,}")
        if sftp_activity.get('sftp_today', 0) > 0:
            print(f"  From SFTP:         {sftp_activity['sftp_today']:,}")
        
        # Work Queue
        work_remaining: int = (
            stats.get('pending', 0) + 
            stats.get('failed', 0) + 
            stats.get('partial', 0) + 
            stats.get('interrupted', 0) + 
            stats.get('api_failed', 0)
        )
        print("\nWORK QUEUE:")
        print(f"  Remaining:         {work_remaining:,}")
        
        if total > 0:
            completion_rate: float = (stats.get('complete', 0) / total) * 100
            print(f"  Completion Rate:   {completion_rate:.1f}%")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db_manager.close_all()


if __name__ == "__main__":
    main()