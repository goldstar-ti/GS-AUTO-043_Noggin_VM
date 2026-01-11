from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common import ConfigLoader, DatabaseConnectionManager, HashManager

app = Flask(__name__)
app.secret_key = 'a1b5a507e8d554cd54f506f3b1056a71f237309a9f4565b6cc9632d4d3352faa'

auth = HTTPBasicAuth()

config = ConfigLoader(
    '../config/base_config.ini',
    '../config/load_compliance_check_driver_loader_config.ini'
)
db_manager = DatabaseConnectionManager(config)
hash_manager = HashManager(config, db_manager)

# Users (in production, use database)
users = {
    "tifunction": generate_password_hash("BankFreePlay13")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

@app.route('/')
# @auth.login_required
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
        
        # Today's activity
        today_query = """
            SELECT 
                COUNT(*) as total_today,
                SUM(CASE WHEN processing_status = 'complete' THEN 1 ELSE 0 END) as completed_today
            FROM noggin_data
            WHERE updated_at >= CURRENT_DATE
        """
        today_stats = db_manager.execute_query_dict(today_query)[0]
        
        # Recent activity
        recent_query = """
            SELECT 
                tip,
                lcd_inspection_id,
                inspection_date,
                processing_status,
                total_attachments,
                completed_attachment_count,
                updated_at
            FROM noggin_data
            ORDER BY updated_at DESC
            LIMIT 20
        """
        recent = db_manager.execute_query_dict(recent_query)
        
        return render_template(
            'dashboard.html',
            stats=stats,
            today_stats=today_stats,
            recent=recent,
            current_time=datetime.now()
        )
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/api/stats')
@auth.login_required
def api_stats():
    """API endpoint for statistics"""
    try:
        stats_query = """
            SELECT 
                processing_status,
                COUNT(*) as count
            FROM noggin_data
            GROUP BY processing_status
        """
        stats = db_manager.execute_query_dict(stats_query)
        
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/inspections')
@auth.login_required
def inspections():
    """List all inspections"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    
    # Get filter parameters
    status = request.args.get('status', '')
    search = request.args.get('search', '')
    
    # Build query
    where_clauses = []
    params = []
    
    if status:
        where_clauses.append("processing_status = %s")
        params.append(status)
    
    if search:
        where_clauses.append("(lcd_inspection_id ILIKE %s OR vehicle ILIKE %s OR trailer ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    
    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Get total count
    count_query = f"SELECT COUNT(*) as total FROM noggin_data{where_sql}"
    total = db_manager.execute_query_dict(count_query, tuple(params))[0]['total']
    
    # Get inspections
    params.extend([per_page, offset])
    inspections_query = f"""
        SELECT 
            tip,
            lcd_inspection_id,
            inspection_date,
            vehicle,
            trailer,
            department,
            team,
            processing_status,
            total_attachments,
            completed_attachment_count,
            retry_count,
            updated_at
        FROM noggin_data
        {where_sql}
        ORDER BY updated_at DESC
        LIMIT %s OFFSET %s
    """
    inspections_list = db_manager.execute_query_dict(inspections_query, tuple(params))
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        'inspections.html',
        inspections=inspections_list,
        page=page,
        total_pages=total_pages,
        total=total,
        status=status,
        search=search
    )

@app.route('/inspection/<tip>')
@auth.login_required
def inspection_detail(tip):
    """Inspection detail page"""
    try:
        # Get inspection
        inspection_query = """
            SELECT * FROM noggin_data WHERE tip = %s
        """
        inspection = db_manager.execute_query_dict(inspection_query, (tip,))
        
        if not inspection:
            return "Inspection not found", 404
        
        inspection = inspection[0]
        
        # Get attachments
        attachments_query = """
            SELECT 
                filename,
                file_path,
                attachment_status,
                file_size_bytes,
                download_duration_seconds,
                attachment_validation_status
            FROM attachments
            WHERE record_tip = %s
            ORDER BY attachment_sequence
        """
        attachments = db_manager.execute_query_dict(attachments_query, (tip,))
        
        # Get errors
        errors_query = """
            SELECT 
                error_type,
                error_message,
                created_at
            FROM processing_errors
            WHERE tip = %s
            ORDER BY created_at DESC
            LIMIT 10
        """
        errors = db_manager.execute_query_dict(errors_query, (tip,))
        
        return render_template(
            'inspection_detail.html',
            inspection=inspection,
            attachments=attachments,
            errors=errors
        )
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/hashes')
@auth.login_required
def hashes():
    """Hash management page"""
    try:
        stats = hash_manager.get_hash_statistics()
        
        # Get unknown hashes count by type
        unknown_query = """
            SELECT 
                entity_type,
                COUNT(*) as count
            FROM unknown_hashes
            WHERE resolved_at IS NULL
            GROUP BY entity_type
        """
        unknown_counts = db_manager.execute_query_dict(unknown_query)
        
        return render_template(
            'hashes.html',
            stats=stats,
            unknown_counts=unknown_counts
        )
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/service-status')
@auth.login_required
def service_status():
    """Service status page"""
    import subprocess
    
    try:
        # Check service status
        result = subprocess.run(
            ['systemctl', 'is-active', 'noggin-processor'],
            capture_output=True,
            text=True
        )
        service_active = result.stdout.strip() == 'active'
        
        # Get recent logs
        log_result = subprocess.run(
            ['journalctl', '-u', 'noggin-processor', '-n', '50', '--no-pager'],
            capture_output=True,
            text=True
        )
        recent_logs = log_result.stdout
        
        return render_template(
            'service_status.html',
            service_active=service_active,
            recent_logs=recent_logs
        )
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)