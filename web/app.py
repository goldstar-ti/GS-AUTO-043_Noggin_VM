from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path to import common modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from common import ConfigLoader, DatabaseConnectionManager, HashManager

app = Flask(__name__)
# Keep your existing secret key
app.secret_key = 'a1b5a507e8d554cd54f506f3b1056a71f237309a9f4565b6cc9632d4d3352faa'

auth = HTTPBasicAuth()

# Load Config - using the relative paths from your directory structure
config = ConfigLoader(
    '../config/base_config.ini',
    '../config/load_compliance_check_driver_loader_config.ini'
)
db_manager = DatabaseConnectionManager(config)
hash_manager = HashManager(config, db_manager)

# Users dictionary - NEW Web Interface credentials
users = {
    "tifunction": generate_password_hash("BankFreePlay13")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

# --- HELPER FUNCTIONS ---

def get_filter_options():
    """Fetch distinct values for dropdowns to make search easier."""
    options = {
        'object_types': [],
        'vehicles': []
    }
    try:
        # Get Object Types (e.g., LCD, GII, SO)
        q_obj = "SELECT DISTINCT object_type FROM noggin_data WHERE object_type IS NOT NULL ORDER BY object_type"
        objs = db_manager.execute_query_dict(q_obj)
        options['object_types'] = [r['object_type'] for r in objs]

        # Get Vehicles (Using DISTINCT to avoid massive lists)
        q_veh = "SELECT DISTINCT vehicle FROM noggin_data WHERE vehicle IS NOT NULL ORDER BY vehicle"
        vehs = db_manager.execute_query_dict(q_veh)
        options['vehicles'] = [r['vehicle'] for r in vehs]
        
    except Exception as e:
        print(f"Error fetching filter options: {e}")
    
    return options

# --- ROUTES ---

@app.route('/')
@auth.login_required
def index():
    """Dashboard home page"""
    try:
        # Get statistics
        stats_query = """
            SELECT 
                processing_status,
                COUNT(*) as count
            FROM noggin_data
            GROUP BY processing_status
        """
        stats = db_manager.execute_query_dict(stats_query)
        
        # Get today's stats
        today_query = """
            SELECT 
                COUNT(*) as total_today,
                COUNT(*) FILTER (WHERE processing_status = 'COMPLETE') as completed_today
            FROM noggin_data
            WHERE updated_at >= CURRENT_DATE
        """
        today_stats_list = db_manager.execute_query_dict(today_query)
        today_stats = today_stats_list[0] if today_stats_list else {'total_today': 0, 'completed_today': 0}
        
        # Recent activity
        recent_query = """
            SELECT * FROM noggin_data 
            ORDER BY updated_at DESC 
            LIMIT 10
        """
        recent = db_manager.execute_query_dict(recent_query)
        
        return render_template(
            'dashboard.html',
            stats=stats,
            today_stats=today_stats,
            recent=recent
        )
    except Exception as e:
        return f"Dashboard Error: {e}", 500

@app.route('/inspections')
@auth.login_required
def inspections():
    """
    Advanced Search Interface for Inspections.
    Supports filtering by Object Type, Date, Entity, and Status.
    """
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    # --- Capture Search Parameters ---
    filters = {
        'status': request.args.get('status', ''),
        'object_type': request.args.get('object_type', ''),
        'vehicle': request.args.get('vehicle', ''),
        'trailer': request.args.get('trailer', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
        'search_text': request.args.get('search', '')
    }

    # --- Build Query Dynamically ---
    query_parts = ["SELECT * FROM noggin_data WHERE 1=1"]
    params = []
    
    if filters['status']:
        query_parts.append("AND processing_status = %s")
        params.append(filters['status'])
        
    if filters['object_type']:
        query_parts.append("AND object_type = %s")
        params.append(filters['object_type'])

    if filters['vehicle']:
        query_parts.append("AND vehicle ILIKE %s")
        params.append(f"%{filters['vehicle']}%")

    if filters['trailer']:
        query_parts.append("AND trailer ILIKE %s")
        params.append(f"%{filters['trailer']}%")

    if filters['date_from']:
        query_parts.append("AND inspection_date >= %s")
        params.append(filters['date_from'])
        
    if filters['date_to']:
        query_parts.append("AND inspection_date <= %s")
        params.append(filters['date_to'])

    if filters['search_text']:
        search_term = f"%{filters['search_text']}%"
        query_parts.append("""
            AND (
                record_tip ILIKE %s OR 
                noggin_reference ILIKE %s OR 
                department ILIKE %s OR 
                team ILIKE %s
            )
        """)
        params.extend([search_term] * 4)

    # --- Count Total (for Pagination) ---
    count_sql = "SELECT COUNT(*) as total FROM noggin_data WHERE 1=1 " + " ".join(query_parts[1:])
    try:
        total_result = db_manager.execute_query_dict(count_sql, tuple(params))
        total = total_result[0]['total']
    except Exception as e:
        total = 0
        print(f"Count Query Error: {e}")

    # --- Finalize Main Query ---
    query_parts.append("ORDER BY inspection_date DESC NULLS LAST, updated_at DESC")
    query_parts.append("LIMIT %s OFFSET %s")
    params.extend([per_page, offset])
    
    sql = " ".join(query_parts)
    
    try:
        inspections = db_manager.execute_query_dict(sql, tuple(params))
    except Exception as e:
        inspections = []
        flash(f"Error loading inspections: {e}", "error")

    # Get options for the dropdowns
    filter_options = get_filter_options()

    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        'inspections.html',
        inspections=inspections,
        page=page,
        total_pages=total_pages,
        total=total,
        filters=filters,
        options=filter_options
    )

@app.route('/inspection/<tip>')
@auth.login_required
def inspection_detail(tip):
    """Detail view for a single inspection"""
    try:
        # Get inspection details
        query = "SELECT * FROM noggin_data WHERE record_tip = %s"
        results = db_manager.execute_query_dict(query, (tip,))
        
        if not results:
            return "Inspection not found", 404
            
        inspection = results[0]
        
        # Get attachments
        att_query = "SELECT * FROM attachments WHERE record_tip = %s ORDER BY created_at"
        attachments = db_manager.execute_query_dict(att_query, (tip,))
        
        # Get processing errors
        err_query = "SELECT * FROM processing_errors WHERE record_tip = %s ORDER BY created_at DESC"
        errors = db_manager.execute_query_dict(err_query, (tip,))
        
        return render_template(
            'inspection_detail.html',
            inspection=inspection,
            attachments=attachments,
            errors=errors
        )
    except Exception as e:
        return f"Detail Error: {e}", 500

@app.route('/hashes')
@auth.login_required
def hashes():
    """Hash management interface"""
    try:
        stats = hash_manager.get_statistics()
        unknown_query = """
            SELECT entity_type, COUNT(*) as count
            FROM unknown_hashes
            WHERE resolved_at IS NULL
            GROUP BY entity_type
        """
        unknown_counts = db_manager.execute_query_dict(unknown_query)
        return render_template('hashes.html', stats=stats, unknown_counts=unknown_counts)
    except Exception as e:
        return f"Hashes Error: {e}", 500

@app.route('/service-status')
@auth.login_required
def service_status():
    """Service status page"""
    import subprocess
    try:
        result = subprocess.run(['systemctl', 'is-active', 'noggin-processor'], capture_output=True, text=True)
        service_active = result.stdout.strip() == 'active'
        log_result = subprocess.run(['journalctl', '-u', 'noggin-processor', '-n', '50', '--no-pager'], capture_output=True, text=True)
        recent_logs = log_result.stdout
        return render_template('service_status.html', service_active=service_active, recent_logs=recent_logs)
    except Exception as e:
        return f"Status Error: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)