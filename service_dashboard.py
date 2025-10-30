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
        'complete': 0,
        'pending': 0,
        'failed': 0,
        'partial': 0,
        'interrupted': 0,
        'api_failed': 0
    }
    
    for row in results:
        status: str = row['processing_status']
        count: int = row['count']
        if status in stats:
            stats[status] = count
    
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


def main() -> None:
    """Display service dashboard"""
    config: ConfigLoader = ConfigLoader(
        'config/base_config.ini',
        'config/load_compliance_check_config.ini'
    )
    
    db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
    
    try:
        print("\n" + "="*80)
        print("NOGGIN PROCESSOR SERVICE DASHBOARD")
        print("="*80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        service_info: Dict[str, str] = get_service_status()
        print("\nSERVICE STATUS:")
        print(f"  Active:  {service_info['status'].upper()}")
        print(f"  Enabled: {service_info['enabled'].upper()}")
        
        stats: Dict[str, int] = get_database_statistics(db_manager)
        total: int = sum(stats.values())
        
        print("\nPROCESSING STATISTICS:")
        print(f"  Total Records:     {total:,}")
        print(f"  Complete:          {stats['complete']:,}")
        print(f"  Pending:           {stats['pending']:,}")
        print(f"  Failed:            {stats['failed']:,}")
        print(f"  Partial:           {stats['partial']:,}")
        print(f"  Interrupted:       {stats['interrupted']:,}")
        print(f"  API Failed:        {stats['api_failed']:,}")
        
        activity: Dict[str, Any] = get_recent_activity(db_manager)
        print("\nTODAY'S ACTIVITY:")
        print(f"  Total Processed:   {activity['total_today']:,}")
        print(f"  Completed:         {activity['completed_today']:,}")
        
        work_remaining: int = (stats['pending'] + stats['failed'] + 
                              stats['partial'] + stats['interrupted'] + 
                              stats['api_failed'])
        print("\nWORK QUEUE:")
        print(f"  Remaining:         {work_remaining:,}")
        
        if total > 0:
            completion_rate: float = (stats['complete'] / total) * 100
            print(f"  Completion Rate:   {completion_rate:.1f}%")
        
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db_manager.close_all()


if __name__ == "__main__":
    main()