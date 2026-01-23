"""
Noggin Data Processor - Web Dashboard

Flask application providing:
- Dashboard with processing statistics
- Inspection list with filtering
- Inspection detail view with attachments
- Hash management interface
- Service status monitoring
- EML export functionality
"""
import os
import sys
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from flask import Flask, render_template, request, flash, send_file, redirect, url_for
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

# Add parent directory to path for common module access
sys.path.insert(0, str(Path(__file__).parent.parent))

from common import ConfigLoader, DatabaseConnectionManager, HashManager
from email_manager import EmailManager


# ==========================================
# 1. CONFIGURATION & LOGGING
# ==========================================

CONFIG_PATH = '../config/base_config.ini'

config = ConfigLoader(CONFIG_PATH)
db_manager = DatabaseConnectionManager(config)
hash_manager = HashManager(config, db_manager)
email_mgr = EmailManager()

LOG_DIR = Path(config.get('paths', 'base_log_path', fallback='/mnt/data/noggin/log'))
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_filename = f"web_app_{datetime.now().strftime('%Y%m%d')}.log"
log_file_path = LOG_DIR / log_filename

file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger('NogginWeb')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
))
logger.addHandler(console_handler)


# ==========================================
# 2. FLASK APP & AUTHENTICATION
# ==========================================

app = Flask(__name__)
app.secret_key = 'a1b5a507e8d554cd54f506f3b1056a71f237309a9f4565b6cc9632d4d3352faa'
app.logger.addHandler(file_handler)

auth = HTTPBasicAuth()

users = {
    "tifunction": generate_password_hash("BankFreePlay13")
}


@auth.verify_password
def verify_password(username: str, password: str) -> Optional[str]:
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================

def get_filter_options() -> Dict[str, List[str]]:
    """Fetch distinct values for filter dropdowns"""
    try:
        object_types = db_manager.execute_query_dict(
            "SELECT DISTINCT object_type FROM noggin_schema.noggin_data WHERE object_type IS NOT NULL ORDER BY object_type"
        )
        vehicles = db_manager.execute_query_dict(
            "SELECT DISTINCT vehicle FROM noggin_schema.noggin_data WHERE vehicle IS NOT NULL AND vehicle != '' ORDER BY vehicle LIMIT 200"
        )
        return {
            'object_types': [r['object_type'] for r in object_types],
            'vehicles': [r['vehicle'] for r in vehicles]
        }
    except Exception as e:
        logger.warning(f"Could not fetch filter options: {e}")
        return {'object_types': [], 'vehicles': []}


def parse_filters(args) -> Dict[str, Any]:
    """Extract and sanitise filter parameters from request args"""
    return {
        'object_type': args.get('object_type', '').strip(),
        'status': args.get('status', '').strip(),
        'vehicle': args.get('vehicle', '').strip(),
        'trailer': args.get('trailer', '').strip(),
        'date_from': args.get('date_from', '').strip(),
        'date_to': args.get('date_to', '').strip(),
        'search_text': args.get('search', '').strip()
    }


# ==========================================
# 4. ROUTES
# ==========================================

@app.route('/')
@auth.login_required
def index():
    """Dashboard with processing statistics and recent activity"""
    try:
        # Processing status counts (for stats grid iteration)
        status_query = """
            SELECT processing_status, COUNT(*) as count
            FROM noggin_schema.noggin_data
            GROUP BY processing_status
        """
        status_results = db_manager.execute_query_dict(status_query)
        # Convert to dict: {'complete': 100, 'pending': 5, ...}
        stats = {r['processing_status']: r['count'] for r in status_results}

        # Object type breakdown
        type_query = """
            SELECT object_type, COUNT(*) as count
            FROM noggin_schema.noggin_data
            WHERE object_type IS NOT NULL
            GROUP BY object_type
            ORDER BY count DESC
        """
        type_stats = db_manager.execute_query_dict(type_query)

        # Today's activity
        today_query = """
            SELECT
                COUNT(*) as total_today,
                SUM(CASE WHEN processing_status = 'complete' THEN 1 ELSE 0 END) as completed_today
            FROM noggin_schema.noggin_data
            WHERE updated_at >= CURRENT_DATE
        """
        today_results = db_manager.execute_query_dict(today_query)
        today_stats = today_results[0] if today_results else {'total_today': 0, 'completed_today': 0}

        # Recent activity with user/team info
        recent_query = """
            SELECT
                tip,
                noggin_reference,
                object_type,
                inspection_date,
                processing_status,
                total_attachments,
                completed_attachment_count,
                retry_count,
                updated_at,
                team,
                department,
                has_unknown_hashes,
                COALESCE(inspected_by, driver_loader_name, person_completing, persons_completing) as derived_user
            FROM noggin_schema.noggin_data
            ORDER BY updated_at DESC
            LIMIT 20
        """
        recent = db_manager.execute_query_dict(recent_query)

        return render_template(
            'dashboard.html',
            stats=stats,
            type_stats=type_stats,
            today_stats=today_stats,
            recent=recent
        )

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        return "Internal Server Error - Check Logs", 500


@app.route('/inspections')
@auth.login_required
def inspections():
    """Inspections list with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page

    filters = parse_filters(request.args)
    options = get_filter_options()

    try:
        where_clauses = []
        params = []

        if filters['object_type']:
            where_clauses.append("object_type = %s")
            params.append(filters['object_type'])

        if filters['status']:
            where_clauses.append("processing_status = %s")
            params.append(filters['status'])

        if filters['vehicle']:
            where_clauses.append("vehicle ILIKE %s")
            params.append(f"%{filters['vehicle']}%")

        if filters['trailer']:
            where_clauses.append("(trailer ILIKE %s OR trailer2 ILIKE %s OR trailer3 ILIKE %s)")
            params.extend([f"%{filters['trailer']}%"] * 3)

        if filters['date_from']:
            where_clauses.append("inspection_date >= %s")
            params.append(filters['date_from'])

        if filters['date_to']:
            where_clauses.append("inspection_date <= %s")
            params.append(filters['date_to'])

        if filters['search_text']:
            where_clauses.append("""
                (noggin_reference ILIKE %s OR team ILIKE %s OR department ILIKE %s OR vehicle ILIKE %s)
            """)
            search_pattern = f"%{filters['search_text']}%"
            params.extend([search_pattern] * 4)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Total count
        count_query = f"SELECT COUNT(*) as total FROM noggin_schema.noggin_data{where_sql}"
        count_result = db_manager.execute_query_dict(count_query, tuple(params) if params else None)
        total = count_result[0]['total'] if count_result else 0

        # Paginated results
        params_with_pagination = params + [per_page, offset]
        data_query = f"""
            SELECT
                tip,
                noggin_reference,
                object_type,
                inspection_date,
                vehicle,
                trailer,
                team,
                department,
                processing_status,
                total_attachments,
                completed_attachment_count,
                retry_count,
                updated_at
            FROM noggin_schema.noggin_data
            {where_sql}
            ORDER BY inspection_date DESC NULLS LAST, updated_at DESC
            LIMIT %s OFFSET %s
        """
        inspections_list = db_manager.execute_query_dict(
            data_query,
            tuple(params_with_pagination) if params_with_pagination else None
        )

        total_pages = (total + per_page - 1) // per_page

        return render_template(
            'inspections.html',
            inspections=inspections_list,
            page=page,
            total_pages=total_pages,
            total=total,
            filters=filters,
            options=options
        )

    except Exception as e:
        logger.error(f"Error listing inspections: {e}", exc_info=True)
        return "Error loading inspections", 500


@app.route('/inspection/<tip>')
@auth.login_required
def inspection_detail(tip: str):
    """Detailed view for a single inspection record"""
    try:
        inspection_query = "SELECT * FROM noggin_schema.noggin_data WHERE tip = %s"
        inspection_results = db_manager.execute_query_dict(inspection_query, (tip,))

        if not inspection_results:
            return "Inspection not found", 404

        inspection = inspection_results[0]

        attachments_query = """
            SELECT
                attachment_tip,
                filename,
                file_path,
                attachment_status,
                file_size_bytes,
                download_duration_seconds,
                created_at
            FROM noggin_schema.attachments
            WHERE record_tip = %s
            ORDER BY attachment_sequence, created_at
        """
        attachments = db_manager.execute_query_dict(attachments_query, (tip,))

        errors = []
        try:
            errors_query = """
                SELECT error_type, error_message, error_timestamp as created_at
                FROM noggin_schema.processing_errors
                WHERE tip = %s
                ORDER BY error_timestamp DESC
                LIMIT 10
            """
            errors = db_manager.execute_query_dict(errors_query, (tip,))
        except Exception:
            pass

        # Build display fields from inspection data
        # Exclude internal/system columns
        exclude_columns = {
            'tip', 'raw_data', 'created_at', 'updated_at', 'processing_status',
            'retry_count', 'last_error', 'total_attachments', 'completed_attachment_count'
        }
        fields = []
        for key, value in inspection.items():
            if key not in exclude_columns and value is not None and value != '':
                label = key.replace('_', ' ').title()
                fields.append({'label': label, 'value': value})

        return render_template(
            'inspection_detail.html',
            inspection=inspection,
            inspection_id=inspection.get('noggin_reference') or tip,
            type_label=inspection.get('object_type', 'Inspection'),
            object_type=inspection.get('object_type'),
            fields=fields,
            attachments=attachments,
            errors=errors
        )

    except Exception as e:
        logger.error(f"Error loading detail for {tip}: {e}", exc_info=True)
        return "Error loading details", 500


@app.route('/inspection/<tip>/attachment/<attachment_tip>')
@auth.login_required
def serve_attachment(tip: str, attachment_tip: str):
    """Serve an attachment file for preview or download"""
    try:
        query = """
            SELECT file_path, filename
            FROM noggin_schema.attachments
            WHERE record_tip = %s AND attachment_tip = %s
        """
        result = db_manager.execute_query_dict(query, (tip, attachment_tip))

        if not result:
            return "Attachment not found", 404

        file_path = result[0]['file_path']
        filename = result[0]['filename']

        if not file_path or not os.path.exists(file_path):
            return "File not found on disk", 404

        return send_file(file_path, download_name=filename)

    except Exception as e:
        logger.error(f"Error serving attachment {attachment_tip}: {e}")
        return "Error retrieving file", 500


@app.route('/inspection/<tip>/eml')
@auth.login_required
def download_eml(tip: str):
    """Generate and download EML file with attachments"""
    try:
        inspection_query = """
            SELECT noggin_reference, object_type FROM noggin_schema.noggin_data WHERE tip = %s
        """
        inspection_results = db_manager.execute_query_dict(inspection_query, (tip,))

        if not inspection_results:
            return "Inspection not found", 404

        inspection = inspection_results[0]

        attachments_query = """
            SELECT file_path, filename
            FROM noggin_schema.attachments
            WHERE record_tip = %s AND attachment_status = 'complete'
        """
        attachments = db_manager.execute_query_dict(attachments_query, (tip,))

        eml_bytes = email_mgr.generate_inspection_eml(
            {
                'id': inspection.get('noggin_reference') or tip,
                'type_label': inspection.get('object_type', 'Inspection')
            },
            attachments
        )

        filename = f"{inspection.get('noggin_reference') or tip}.eml"
        return send_file(
            eml_bytes,
            as_attachment=True,
            download_name=filename,
            mimetype='message/rfc822'
        )

    except Exception as e:
        logger.error(f"EML generation failed for {tip}: {e}", exc_info=True)
        return "Error creating export", 500


@app.route('/hashes')
@auth.login_required
def hashes():
    """Hash management page with statistics"""
    try:
        stats = hash_manager.get_statistics()

        unknown_query = """
            SELECT lookup_type, COUNT(*) as count
            FROM noggin_schema.unknown_hashes
            WHERE resolved_at IS NULL
            GROUP BY lookup_type
            ORDER BY count DESC
        """
        unknown_counts = db_manager.execute_query_dict(unknown_query)

        return render_template(
            'hashes.html',
            stats=stats,
            unknown_counts=unknown_counts
        )

    except Exception as e:
        logger.error(f"Error loading hashes page: {e}", exc_info=True)
        return "Error loading hash statistics", 500


@app.route('/service-status')
@auth.login_required
def service_status():
    """Check status of both web and processor services"""
    
    def get_service_info(service_name: str, log_lines: int = 50) -> dict:
        """Helper to fetch service status and logs"""
        try:
            status_result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True
            )
            is_active = status_result.stdout.strip() == 'active'
            
            log_result = subprocess.run(
                ['journalctl', '-u', service_name, '-n', str(log_lines), '--no-pager'],
                capture_output=True,
                text=True
            )
            logs = log_result.stdout or log_result.stderr or 'No logs available'
            
            # Get more detailed status
            detail_result = subprocess.run(
                ['systemctl', 'show', service_name, '--property=ActiveState,SubState,MainPID,MemoryCurrent'],
                capture_output=True,
                text=True
            )
            details = {}
            for line in detail_result.stdout.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    details[key] = value
            
            return {
                'name': service_name,
                'active': is_active,
                'state': details.get('ActiveState', 'unknown'),
                'substate': details.get('SubState', 'unknown'),
                'pid': details.get('MainPID', 'N/A'),
                'memory': details.get('MemoryCurrent', 'N/A'),
                'logs': logs
            }
        except Exception as e:
            logger.warning(f"Could not get status for {service_name}: {e}")
            return {
                'name': service_name,
                'active': False,
                'state': 'error',
                'substate': str(e),
                'pid': 'N/A',
                'memory': 'N/A',
                'logs': f'Error fetching logs: {e}'
            }
    
    try:
        web_service = get_service_info('noggin-web')
        processor_service = get_service_info('noggin-processor')
        
        active_tab = request.args.get('tab', 'web')
        
        return render_template(
            'service_status.html',
            web_service=web_service,
            processor_service=processor_service,
            active_tab=active_tab
        )
    
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return "Status check failed", 500


# ==========================================
# 5. ERROR HANDLERS
# ==========================================

@app.errorhandler(404)
def not_found(e):
    return render_template('base.html', content="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    return "Internal server error", 500


# ==========================================
# 6. APPLICATION ENTRY
# ==========================================

if __name__ == '__main__':
    logger.info("Starting Noggin Web Dashboard")
    app.run(host='0.0.0.0', port=5000, debug=True)