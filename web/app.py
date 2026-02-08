"""
Noggin Object Binary Backup Ingestion Engine (NOBBIE)
Web Application

Flask application providing:
- Dashboard with processing statistics
- Records list with filtering
- Record detail view with attachments
- Hash management interface
- Service status monitoring
- Utility tools for hash analysis
- Reports section
- EML export functionality
"""
import os
import sys
import logging
import subprocess
import configparser
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from io import BytesIO
import random

from flask import (
    Flask, render_template, request, flash, send_file,
    redirect, url_for, Response, make_response, jsonify, abort
)
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException

from jinja2 import TemplateNotFound

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import ConfigLoader, DatabaseConnectionManager, HashManager, LoggerManager
from email_manager import EmailManager
from display_config_manager import DisplayConfigManager, format_value

RESULTS_PER_PAGE = 100
CONFIG_PATH = '../config/base_config.ini'
WEB_CONFIG_PATH = '../config/web_config.ini'

config = ConfigLoader(CONFIG_PATH)
db_manager = DatabaseConnectionManager(config)
hash_manager = HashManager(config, db_manager)
email_mgr = EmailManager()
display_config_mgr = DisplayConfigManager('../config', config)

logger: logging.Logger = logging.getLogger(__name__)


def load_web_config() -> configparser.ConfigParser:
    """Load web-specific configuration"""
    web_config = configparser.ConfigParser()
    web_config_path = Path(__file__).parent / WEB_CONFIG_PATH
    if web_config_path.exists():
        web_config.read(web_config_path)
    return web_config


web_config = load_web_config()

HIDE_EMPTY_FIELDS = config.getboolean('web_display', 'hide_empty_fields', fallback=True)
THUMBNAIL_WIDTH = config.getint('web_display', 'thumbnail_width', fallback=120)
THUMBNAIL_HEIGHT = config.getint('web_display', 'thumbnail_height', fallback=90)
DATE_FORMAT = config.get('web_display', 'date_format', fallback='%d %b %Y')
DATETIME_FORMAT = config.get('web_display', 'datetime_format', fallback='%d %b %Y %H:%M')

app = Flask(__name__)
app.secret_key = 'a1b5a507e8d554cd54f506f3b1056a71f237309a9f4565b6cc9632d4d3352faa'
auth = HTTPBasicAuth()

users = {
    "tifunction": generate_password_hash("BankFreePlay13"),
    "hseq": generate_password_hash("hseq")
}


def get_object_type_display(object_type: str) -> Tuple[str, str]:
    """
    Get abbreviation and full name for an object type from web_config.ini
    Returns (abbreviation, full_name) tuple
    """
    if web_config.has_option('object_types', object_type):
        value = web_config.get('object_types', object_type)
        parts = value.split('|')
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    # Fallback: generate from object_type string
    abbrev = ''.join(word[0].upper() for word in object_type.split()[:3])
    return abbrev, object_type


@auth.verify_password
def verify_password(username: str, password: str) -> Optional[str]:
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


def get_filter_options() -> Dict[str, List[str]]:
    """Fetch distinct values for filter dropdowns"""
    try:
        object_types = db_manager.execute_query_dict(
            "SELECT DISTINCT object_type FROM noggin_schema.noggin_data WHERE object_type IS NOT NULL ORDER BY object_type"
        )
        vehicles = db_manager.execute_query_dict(
            "SELECT DISTINCT vehicle FROM noggin_schema.noggin_data WHERE vehicle IS NOT NULL AND vehicle != '' ORDER BY vehicle"
        )
        trailers = db_manager.execute_query_dict(
            """SELECT DISTINCT trailer FROM noggin_schema.noggin_data 
               WHERE trailer IS NOT NULL AND trailer != '' 
               UNION 
               SELECT DISTINCT trailer2 FROM noggin_schema.noggin_data 
               WHERE trailer2 IS NOT NULL AND trailer2 != ''
               UNION
               SELECT DISTINCT trailer3 FROM noggin_schema.noggin_data 
               WHERE trailer3 IS NOT NULL AND trailer3 != ''
               ORDER BY trailer"""
        )
        teams = db_manager.execute_query_dict(
            "SELECT DISTINCT team FROM noggin_schema.noggin_data WHERE team IS NOT NULL AND team != '' ORDER BY team"
        )
        departments = db_manager.execute_query_dict(
            "SELECT DISTINCT department FROM noggin_schema.noggin_data WHERE department IS NOT NULL AND department != '' ORDER BY department"
        )
        # Get drivers from multiple possible columns
        drivers = db_manager.execute_query_dict(
            """SELECT DISTINCT driver_name FROM (
                SELECT inspected_by AS driver_name FROM noggin_schema.noggin_data WHERE inspected_by IS NOT NULL AND inspected_by != ''
                UNION
                SELECT driver_loader_name FROM noggin_schema.noggin_data WHERE driver_loader_name IS NOT NULL AND driver_loader_name != ''
            ) AS drivers ORDER BY driver_name"""
        )
        return {
            'object_types': [r['object_type'] for r in object_types],
            'vehicles': [r['vehicle'] for r in vehicles],
            'trailers': [r['trailer'] for r in trailers],
            'teams': [r['team'] for r in teams],
            'departments': [r['department'] for r in departments],
            'drivers': [r['driver_name'] for r in drivers]
        }
    except Exception as e:
        logger.warning(f"Could not fetch filter options: {e}")
        return {
            'object_types': [], 'vehicles': [], 'trailers': [],
            'teams': [], 'departments': [], 'drivers': []
        }


def parse_filters(args) -> Dict[str, Any]:
    """Extract and sanitise filter parameters from request args"""
    return {
        'object_type': args.get('object_type', '').strip(),
        'status': args.get('status', '').strip(),
        'vehicle': args.get('vehicle', '').strip(),
        'trailer': args.get('trailer', '').strip(),
        'team': args.get('team', '').strip(),
        'department': args.get('department', '').strip(),
        'driver': args.get('driver', '').strip(),
        'date_from': args.get('date_from', '').strip(),
        'date_to': args.get('date_to', '').strip(),
        'search_text': args.get('search', '').strip()
    }


def format_inspection_date(dt: datetime) -> str:
    """Format inspection date, hiding time if midnight"""
    if dt is None:
        return ''
    if isinstance(dt, str):
        return dt
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        return dt.strftime(DATE_FORMAT)
    return dt.strftime(DATETIME_FORMAT)


def is_image_file(filename: str) -> bool:
    """Check if file is an image based on extension"""
    if not filename:
        return False
    ext = filename.lower().split('.')[-1]
    return ext in ('jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp')


def get_theme_from_cookie() -> str:
    """Get theme preference from cookie, default to light"""
    return request.cookies.get('theme', 'light')


@app.context_processor
def inject_theme():
    """Inject theme into all templates"""
    return {'theme': get_theme_from_cookie()}


@app.route('/toggle-theme')
@auth.login_required
def toggle_theme():
    """Toggle between light and dark theme"""
    current_theme = get_theme_from_cookie()
    new_theme = 'dark' if current_theme == 'light' else 'light'
    
    referrer = request.referrer or url_for('index')
    response = make_response(redirect(referrer))
    response.set_cookie('theme', new_theme, max_age=31536000)  # 1 year
    return response


@app.route('/')
@auth.login_required
def index():
    """Dashboard with processing statistics and recent activity"""
    try:
        status_query = """
            SELECT processing_status, COUNT(*) as count
            FROM noggin_schema.noggin_data
            GROUP BY processing_status
        """
        status_results = db_manager.execute_query_dict(status_query)
        stats = {r['processing_status']: r['count'] for r in status_results}

        type_query = """
            SELECT object_type, COUNT(*) as count
            FROM noggin_schema.noggin_data
            WHERE object_type IS NOT NULL
            GROUP BY object_type
            ORDER BY count DESC
        """
        type_stats = db_manager.execute_query_dict(type_query)

        today_query = """
            SELECT
                COUNT(*) as total_today,
                SUM(CASE WHEN processing_status = 'complete' THEN 1 ELSE 0 END) as completed_today
            FROM noggin_schema.noggin_data
            WHERE updated_at >= CURRENT_DATE
        """
        today_results = db_manager.execute_query_dict(today_query)
        today_stats = today_results[0] if today_results else {'total_today': 0, 'completed_today': 0}

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
        abort(500, description="Dashboard failed to load")


@app.route('/records')
@auth.login_required
def records():
    """Records list with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * RESULTS_PER_PAGE

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

        if filters['team']:
            where_clauses.append("team ILIKE %s")
            params.append(f"%{filters['team']}%")

        if filters['department']:
            where_clauses.append("department ILIKE %s")
            params.append(f"%{filters['department']}%")

        if filters['driver']:
            where_clauses.append("(inspected_by ILIKE %s OR driver_loader_name ILIKE %s)")
            params.extend([f"%{filters['driver']}%"] * 2)

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

        count_query = f"SELECT COUNT(*) as total FROM noggin_schema.noggin_data{where_sql}"
        count_result = db_manager.execute_query_dict(count_query, tuple(params) if params else None)
        total = count_result[0]['total'] if count_result else 0

        params_with_pagination = params + [RESULTS_PER_PAGE, offset]
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
        records_list = db_manager.execute_query_dict(
            data_query,
            tuple(params_with_pagination) if params_with_pagination else None
        )

        total_pages = (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE

        return render_template(
            'records.html',
            records=records_list,
            page=page,
            total_pages=total_pages,
            total=total,
            filters=filters,
            options=options
        )

    except Exception as e:
        logger.error(f"Error listing records: {e}", exc_info=True)
        abort(500, description="Records listing failed")


# Keep old route for backwards compatibility
@app.route('/inspections')
@auth.login_required
def inspections():
    """Redirect to records"""
    return redirect(url_for('records', **request.args))


@app.route('/record/<tip>')
@auth.login_required
def record_detail(tip: str):
    """Detailed view for a single record"""
    try:
        inspection_query = "SELECT * FROM noggin_schema.noggin_data WHERE tip = %s"
        inspection_results = db_manager.execute_query_dict(inspection_query, (tip,))

        if not inspection_results:
            abort(404, description=f"Record not found: {tip}")

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

        for att in attachments:
            att['is_image'] = is_image_file(att.get('filename', ''))

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

        display_data = display_config_mgr.build_display_data(
            inspection,
            hide_empty=HIDE_EMPTY_FIELDS,
            date_format=DATE_FORMAT,
            datetime_format=DATETIME_FORMAT
        )

        object_type = inspection.get('object_type', '')
        # abbreviation, full_type_name = get_object_type_display(object_type)
        # show full object type name under the noggin_reference on record_detail.html
        try:
            obj_config = display_config_mgr.get_config(object_type)
            abbreviation = obj_config.get('object_type', 'abbreviation', fallback='')
            full_type_name = obj_config.get('object_type', 'full_name', fallback=object_type)
        except:
            abbreviation, full_type_name = get_object_type_display(object_type)
        
        # Check if department should be hidden (same as team)
        team_value = inspection.get('team', '')
        dept_value = inspection.get('department', '')
        hide_department = (team_value and dept_value and team_value == dept_value)
        
        inspection_date = inspection.get('inspection_date')
        formatted_date = format_inspection_date(inspection_date)

        return render_template(
            'record_detail.html',
            inspection=inspection,
            inspection_id=inspection.get('noggin_reference') or tip,
            type_label=abbreviation,
            full_type_name=full_type_name,
            object_type=object_type,
            display_data=display_data,
            attachments=attachments,
            errors=errors,
            formatted_date=formatted_date,
            thumbnail_width=THUMBNAIL_WIDTH,
            thumbnail_height=THUMBNAIL_HEIGHT,
            hide_department=hide_department,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading detail for {tip}: {e}", exc_info=True)
        abort(500, description=f"Record detail failed for {tip}")


# Keep old route for backwards compatibility
@app.route('/inspection/<tip>')
@auth.login_required
def inspection_detail(tip: str):
    """Redirect to record_detail"""
    return redirect(url_for('record_detail', tip=tip))


@app.route('/record/<tip>/attachment/<attachment_tip>')
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
            abort(404, description="Attachment record not found")

        file_path = result[0]['file_path']
        filename = result[0]['filename']

        if not file_path or not os.path.exists(file_path):
            abort(404, description="Attachment file not found on disk")

        return send_file(file_path, download_name=filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving attachment {attachment_tip}: {e}")
        abort(500, description="Attachment retrieval failed")


# Keep old route for backwards compatibility
@app.route('/inspection/<tip>/attachment/<attachment_tip>')
@auth.login_required
def serve_attachment_old(tip: str, attachment_tip: str):
    return serve_attachment(tip, attachment_tip)


@app.route('/record/<tip>/attachment/<attachment_tip>/thumbnail')
@auth.login_required
def serve_thumbnail(tip: str, attachment_tip: str):
    """Serve a thumbnail of an image attachment"""
    try:
        query = """
            SELECT file_path, filename
            FROM noggin_schema.attachments
            WHERE record_tip = %s AND attachment_tip = %s
        """
        result = db_manager.execute_query_dict(query, (tip, attachment_tip))

        if not result:
            abort(404, description="Attachment record not found")

        file_path = result[0]['file_path']
        filename = result[0]['filename']

        if not file_path or not os.path.exists(file_path):
            abort(404, description="Attachment file not found on disk")

        if not is_image_file(filename):
            abort(400, description="Requested file is not an image")

        try:
            from PIL import Image
            
            img = Image.open(file_path)
            img.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
            
            thumb_io = BytesIO()
            img_format = 'JPEG' if filename.lower().endswith(('.jpg', '.jpeg')) else 'PNG'
            img.save(thumb_io, format=img_format, quality=85)
            thumb_io.seek(0)
            
            mime_type = 'image/jpeg' if img_format == 'JPEG' else 'image/png'
            return send_file(thumb_io, mimetype=mime_type)
            
        except ImportError:
            return send_file(file_path, download_name=filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving thumbnail {attachment_tip}: {e}")
        abort(500, description="Thumbnail generation failed")


# Keep old route for backwards compatibility
@app.route('/inspection/<tip>/attachment/<attachment_tip>/thumbnail')
@auth.login_required
def serve_thumbnail_old(tip: str, attachment_tip: str):
    return serve_thumbnail(tip, attachment_tip)


@app.route('/record/<tip>/eml')
@auth.login_required
def download_eml(tip: str):
    """Generate and download EML file with attachments"""
    try:
        inspection_query = """
            SELECT noggin_reference, object_type FROM noggin_schema.noggin_data WHERE tip = %s
        """
        inspection_results = db_manager.execute_query_dict(inspection_query, (tip,))

        if not inspection_results:
            abort(404, description=f"Record not found: {tip}")

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
                'type_label': inspection.get('object_type', 'Record')
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"EML generation failed for {tip}: {e}", exc_info=True)
        abort(500, description="EML file generation failed")


# Keep old route for backwards compatibility
@app.route('/inspection/<tip>/eml')
@auth.login_required
def download_eml_old(tip: str):
    return download_eml(tip)


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
        abort(500, description="Hash statistics failed to load")


@app.route('/utility')
@auth.login_required
def utility():
    """Utility page for hash analysis and maintenance"""
    try:
        # Orphaned hashes: in hash_lookup but no matching values in noggin_data
        orphaned_vehicles_query = """
            SELECT hl.tip_hash, hl.resolved_value, hl.lookup_type, hl.source_type, hl.created_at
            FROM noggin_schema.hash_lookup hl
            WHERE hl.lookup_type = 'vehicle'
              AND NOT EXISTS (
                  SELECT 1 FROM noggin_schema.noggin_data nd 
                  WHERE nd.vehicle_hash = hl.tip_hash
              )
            ORDER BY hl.resolved_value
            LIMIT 100
        """
        orphaned_vehicles = db_manager.execute_query_dict(orphaned_vehicles_query)
        
        orphaned_trailers_query = """
            SELECT hl.tip_hash, hl.resolved_value, hl.lookup_type, hl.source_type, hl.created_at
            FROM noggin_schema.hash_lookup hl
            WHERE hl.lookup_type = 'trailer'
              AND NOT EXISTS (
                  SELECT 1 FROM noggin_schema.noggin_data nd 
                  WHERE nd.trailer_hash = hl.tip_hash 
                     OR nd.trailer2_hash = hl.tip_hash 
                     OR nd.trailer3_hash = hl.tip_hash
              )
            ORDER BY hl.resolved_value
            LIMIT 100
        """
        orphaned_trailers = db_manager.execute_query_dict(orphaned_trailers_query)
        
        orphaned_teams_query = """
            SELECT hl.tip_hash, hl.resolved_value, hl.lookup_type, hl.source_type, hl.created_at
            FROM noggin_schema.hash_lookup hl
            WHERE hl.lookup_type = 'team'
              AND NOT EXISTS (
                  SELECT 1 FROM noggin_schema.noggin_data nd 
                  WHERE nd.team_hash = hl.tip_hash
              )
            ORDER BY hl.resolved_value
            LIMIT 100
        """
        orphaned_teams = db_manager.execute_query_dict(orphaned_teams_query)
        
        orphaned_depts_query = """
            SELECT hl.tip_hash, hl.resolved_value, hl.lookup_type, hl.source_type, hl.created_at
            FROM noggin_schema.hash_lookup hl
            WHERE hl.lookup_type = 'department'
              AND NOT EXISTS (
                  SELECT 1 FROM noggin_schema.noggin_data nd 
                  WHERE nd.department_hash = hl.tip_hash
              )
            ORDER BY hl.resolved_value
            LIMIT 100
        """
        orphaned_depts = db_manager.execute_query_dict(orphaned_depts_query)
        
        # Hash distribution summary
        distribution_query = """
            SELECT 
                lookup_type,
                source_type,
                COUNT(*) as count
            FROM noggin_schema.hash_lookup
            GROUP BY lookup_type, source_type
            ORDER BY lookup_type, source_type
        """
        distribution = db_manager.execute_query_dict(distribution_query)
        
        # Team/Department assignment analysis
        team_assignment_query = """
            SELECT 
                team,
                COUNT(DISTINCT vehicle) as vehicle_count,
                COUNT(DISTINCT COALESCE(inspected_by, driver_loader_name)) as driver_count,
                COUNT(*) as record_count
            FROM noggin_schema.noggin_data
            WHERE team IS NOT NULL AND team != ''
            GROUP BY team
            ORDER BY record_count DESC
            LIMIT 50
        """
        team_assignments = db_manager.execute_query_dict(team_assignment_query)
        
        dept_assignment_query = """
            SELECT 
                department,
                COUNT(DISTINCT vehicle) as vehicle_count,
                COUNT(DISTINCT COALESCE(inspected_by, driver_loader_name)) as driver_count,
                COUNT(*) as record_count
            FROM noggin_schema.noggin_data
            WHERE department IS NOT NULL AND department != ''
            GROUP BY department
            ORDER BY record_count DESC
            LIMIT 50
        """
        dept_assignments = db_manager.execute_query_dict(dept_assignment_query)
        
        # Detailed vehicle assignments by team
        team_vehicles_query = """
            SELECT 
                team,
                vehicle,
                COUNT(*) as record_count,
                MAX(inspection_date) as last_seen
            FROM noggin_schema.noggin_data
            WHERE team IS NOT NULL AND team != '' 
              AND vehicle IS NOT NULL AND vehicle != ''
            GROUP BY team, vehicle
            ORDER BY team, record_count DESC
        """
        team_vehicles = db_manager.execute_query_dict(team_vehicles_query)
        
        # Detailed driver assignments by team
        team_drivers_query = """
            SELECT 
                team,
                COALESCE(inspected_by, driver_loader_name) as driver,
                COUNT(*) as record_count,
                MAX(inspection_date) as last_seen
            FROM noggin_schema.noggin_data
            WHERE team IS NOT NULL AND team != ''
              AND COALESCE(inspected_by, driver_loader_name) IS NOT NULL
              AND COALESCE(inspected_by, driver_loader_name) != ''
            GROUP BY team, COALESCE(inspected_by, driver_loader_name)
            ORDER BY team, record_count DESC
        """
        team_drivers = db_manager.execute_query_dict(team_drivers_query)
        
        orphan_counts = {
            'vehicle': len(orphaned_vehicles),
            'trailer': len(orphaned_trailers),
            'team': len(orphaned_teams),
            'department': len(orphaned_depts)
        }

        return render_template(
            'utility.html',
            orphaned_vehicles=orphaned_vehicles,
            orphaned_trailers=orphaned_trailers,
            orphaned_teams=orphaned_teams,
            orphaned_depts=orphaned_depts,
            orphan_counts=orphan_counts,
            distribution=distribution,
            team_assignments=team_assignments,
            dept_assignments=dept_assignments,
            team_vehicles=team_vehicles,
            team_drivers=team_drivers
        )

    except Exception as e:
        logger.error(f"Error loading utility page: {e}", exc_info=True)
        abort(500, description="Utility page failed to load")


@app.route('/utility/export-orphaned/<lookup_type>')
@auth.login_required
def export_orphaned_hashes(lookup_type: str):
    """Export orphaned hashes as CSV"""
    try:
        if lookup_type == 'vehicle':
            query = """
                SELECT hl.tip_hash, hl.resolved_value, hl.lookup_type, hl.source_type, hl.created_at
                FROM noggin_schema.hash_lookup hl
                WHERE hl.lookup_type = 'vehicle'
                  AND NOT EXISTS (
                      SELECT 1 FROM noggin_schema.noggin_data nd 
                      WHERE nd.vehicle_hash = hl.tip_hash
                  )
                ORDER BY hl.resolved_value
            """
        elif lookup_type == 'trailer':
            query = """
                SELECT hl.tip_hash, hl.resolved_value, hl.lookup_type, hl.source_type, hl.created_at
                FROM noggin_schema.hash_lookup hl
                WHERE hl.lookup_type = 'trailer'
                  AND NOT EXISTS (
                      SELECT 1 FROM noggin_schema.noggin_data nd 
                      WHERE nd.trailer_hash = hl.tip_hash 
                         OR nd.trailer2_hash = hl.tip_hash 
                         OR nd.trailer3_hash = hl.tip_hash
                  )
                ORDER BY hl.resolved_value
            """
        elif lookup_type == 'team':
            query = """
                SELECT hl.tip_hash, hl.resolved_value, hl.lookup_type, hl.source_type, hl.created_at
                FROM noggin_schema.hash_lookup hl
                WHERE hl.lookup_type = 'team'
                  AND NOT EXISTS (
                      SELECT 1 FROM noggin_schema.noggin_data nd 
                      WHERE nd.team_hash = hl.tip_hash
                  )
                ORDER BY hl.resolved_value
            """
        elif lookup_type == 'department':
            query = """
                SELECT hl.tip_hash, hl.resolved_value, hl.lookup_type, hl.source_type, hl.created_at
                FROM noggin_schema.hash_lookup hl
                WHERE hl.lookup_type = 'department'
                  AND NOT EXISTS (
                      SELECT 1 FROM noggin_schema.noggin_data nd 
                      WHERE nd.department_hash = hl.tip_hash
                  )
                ORDER BY hl.resolved_value
            """
        else:
            abort(400, description=f"Invalid lookup type: {lookup_type}")
        
        results = db_manager.execute_query_dict(query)
        
        # Build CSV
        csv_lines = ['tip_hash,resolved_value,lookup_type,source_type,created_at']
        for r in results:
            created = r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if r['created_at'] else ''
            csv_lines.append(f"{r['tip_hash']},{r['resolved_value']},{r['lookup_type']},{r['source_type'] or ''},{created}")
        
        csv_content = '\n'.join(csv_lines)
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=orphaned_{lookup_type}_hashes.csv'}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting orphaned hashes: {e}")
        abort(500, description="Orphaned hash export failed")


@app.route('/reports')
@auth.login_required
def reports():
    """Reports landing page"""
    return render_template('reports.html')


@app.route('/reports/processing-summary')
@auth.login_required
def report_processing_summary():
    """Processing summary report"""
    try:
        days = request.args.get('days', 30, type=int)
        
        daily_query = """
            SELECT 
                DATE(inspection_date) as date,
                object_type,
                processing_status,
                COUNT(*) as count
            FROM noggin_schema.noggin_data
            WHERE inspection_date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY DATE(inspection_date), object_type, processing_status
            ORDER BY date DESC, object_type
        """
        daily_stats = db_manager.execute_query_dict(daily_query, (days,))
        
        totals_query = """
            SELECT 
                object_type,
                processing_status,
                COUNT(*) as count
            FROM noggin_schema.noggin_data
            WHERE inspection_date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY object_type, processing_status
            ORDER BY object_type
        """
        totals = db_manager.execute_query_dict(totals_query, (days,))
        
        return render_template(
            'reports/processing_summary.html',
            daily_stats=daily_stats,
            totals=totals,
            days=days
        )
    except Exception as e:
        logger.error(f"Error generating processing summary: {e}")
        abort(500, description="Processing summary report failed")


@app.route('/reports/vehicle-activity')
@auth.login_required
def report_vehicle_activity():
    """Vehicle activity report"""
    try:
        vehicle = request.args.get('vehicle', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        options = get_filter_options()
        
        records = []
        if vehicle:
            params = [f"%{vehicle}%"]
            where_clauses = ["vehicle ILIKE %s"]
            
            if date_from:
                where_clauses.append("inspection_date >= %s")
                params.append(date_from)
            if date_to:
                where_clauses.append("inspection_date <= %s")
                params.append(date_to)
            
            query = f"""
                SELECT 
                    tip, noggin_reference, object_type, inspection_date,
                    vehicle, trailer, team, department, processing_status,
                    total_attachments, completed_attachment_count,
                    COALESCE(inspected_by, driver_loader_name) as driver
                FROM noggin_schema.noggin_data
                WHERE {' AND '.join(where_clauses)}
                ORDER BY inspection_date DESC
                LIMIT 500
            """
            records = db_manager.execute_query_dict(query, tuple(params))
        
        return render_template(
            'reports/vehicle_activity.html',
            records=records,
            vehicle=vehicle,
            date_from=date_from,
            date_to=date_to,
            options=options
        )
    except Exception as e:
        logger.error(f"Error generating vehicle activity report: {e}")
        abort(500, description="Vehicle activity report failed")


@app.route('/reports/trailer-activity')
@auth.login_required
def report_trailer_activity():
    """Trailer activity report"""
    try:
        trailer = request.args.get('trailer', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        options = get_filter_options()
        
        records = []
        if trailer:
            params = [f"%{trailer}%"] * 3
            where_clauses = ["(trailer ILIKE %s OR trailer2 ILIKE %s OR trailer3 ILIKE %s)"]
            
            if date_from:
                where_clauses.append("inspection_date >= %s")
                params.append(date_from)
            if date_to:
                where_clauses.append("inspection_date <= %s")
                params.append(date_to)
            
            query = f"""
                SELECT 
                    tip, noggin_reference, object_type, inspection_date,
                    vehicle, trailer, trailer2, trailer3, team, department, processing_status,
                    total_attachments, completed_attachment_count,
                    COALESCE(inspected_by, driver_loader_name) as driver
                FROM noggin_schema.noggin_data
                WHERE {' AND '.join(where_clauses)}
                ORDER BY inspection_date DESC
                LIMIT 500
            """
            records = db_manager.execute_query_dict(query, tuple(params))
        
        return render_template(
            'reports/trailer_activity.html',
            records=records,
            trailer=trailer,
            date_from=date_from,
            date_to=date_to,
            options=options
        )
    except Exception as e:
        logger.error(f"Error generating trailer activity report: {e}")
        abort(500, description="Trailer activity report failed")


@app.route('/reports/team-performance')
@auth.login_required
def report_team_performance():
    """Team/Department performance report"""
    try:
        query = """
            SELECT 
                team,
                department,
                COUNT(*) as total_records,
                SUM(CASE WHEN processing_status = 'complete' THEN 1 ELSE 0 END) as complete,
                SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN processing_status = 'pending' THEN 1 ELSE 0 END) as pending,
                COUNT(DISTINCT vehicle) as unique_vehicles,
                COUNT(DISTINCT COALESCE(inspected_by, driver_loader_name)) as unique_drivers
            FROM noggin_schema.noggin_data
            WHERE team IS NOT NULL AND team != ''
            GROUP BY team, department
            ORDER BY total_records DESC
        """
        team_stats = db_manager.execute_query_dict(query)
        
        return render_template(
            'reports/team_performance.html',
            team_stats=team_stats
        )
    except Exception as e:
        logger.error(f"Error generating team performance report: {e}")
        abort(500, description="Team performance report failed")


@app.route('/reports/driver-activity')
@auth.login_required
def report_driver_activity():
    """Driver activity report"""
    try:
        driver = request.args.get('driver', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        options = get_filter_options()
        
        records = []
        summary = None
        
        if driver:
            params = [f"%{driver}%"] * 2
            where_clauses = ["(inspected_by ILIKE %s OR driver_loader_name ILIKE %s)"]
            
            if date_from:
                where_clauses.append("inspection_date >= %s")
                params.append(date_from)
            if date_to:
                where_clauses.append("inspection_date <= %s")
                params.append(date_to)
            
            where_sql = ' AND '.join(where_clauses)
            
            query = f"""
                SELECT 
                    tip, noggin_reference, object_type, inspection_date,
                    vehicle, trailer, team, department, processing_status,
                    total_attachments, completed_attachment_count,
                    COALESCE(inspected_by, driver_loader_name) as driver
                FROM noggin_schema.noggin_data
                WHERE {where_sql}
                ORDER BY inspection_date DESC
                LIMIT 500
            """
            records = db_manager.execute_query_dict(query, tuple(params))
            
            # Get summary
            summary_query = f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT vehicle) as unique_vehicles,
                    COUNT(DISTINCT team) as unique_teams,
                    MIN(inspection_date) as first_record,
                    MAX(inspection_date) as last_record
                FROM noggin_schema.noggin_data
                WHERE {where_sql}
            """
            summary_result = db_manager.execute_query_dict(summary_query, tuple(params))
            summary = summary_result[0] if summary_result else None
        
        return render_template(
            'reports/driver_activity.html',
            records=records,
            summary=summary,
            driver=driver,
            date_from=date_from,
            date_to=date_to,
            options=options
        )
    except Exception as e:
        logger.error(f"Error generating driver activity report: {e}")
        abort(500, description="Driver activity report failed")


@app.route('/reports/attachment-status')
@auth.login_required
def report_attachment_status():
    """Attachment status report - records with missing/incomplete attachments"""
    try:
        query = """
            SELECT 
                nd.tip, nd.noggin_reference, nd.object_type, nd.inspection_date,
                nd.vehicle, nd.team, nd.processing_status,
                nd.total_attachments, nd.completed_attachment_count,
                (nd.total_attachments - nd.completed_attachment_count) as missing_count
            FROM noggin_schema.noggin_data nd
            WHERE nd.total_attachments > nd.completed_attachment_count
               OR nd.total_attachments = 0
            ORDER BY missing_count DESC, nd.inspection_date DESC
            LIMIT 200
        """
        records = db_manager.execute_query_dict(query)
        
        summary_query = """
            SELECT 
                COUNT(*) as total_incomplete,
                SUM(total_attachments - completed_attachment_count) as total_missing
            FROM noggin_schema.noggin_data
            WHERE total_attachments > completed_attachment_count
        """
        summary = db_manager.execute_query_dict(summary_query)
        
        return render_template(
            'reports/attachment_status.html',
            records=records,
            summary=summary[0] if summary else {}
        )
    except Exception as e:
        logger.error(f"Error generating attachment status report: {e}")
        abort(500, description="Attachment status report failed")


@app.route('/reports/unknown-hashes')
@auth.login_required
def report_unknown_hashes():
    """Unknown hash summary report"""
    try:
        query = """
            SELECT 
                uh.tip_hash,
                uh.lookup_type,
                uh.occurrence_count,
                uh.first_seen_at,
                uh.last_seen_at,
                uh.first_seen_inspection_id,
                nd.object_type,
                nd.team,
                nd.department
            FROM noggin_schema.unknown_hashes uh
            LEFT JOIN noggin_schema.noggin_data nd ON uh.first_seen_tip = nd.tip
            WHERE uh.resolved_at IS NULL
            ORDER BY uh.occurrence_count DESC, uh.last_seen_at DESC
            LIMIT 200
        """
        unknown = db_manager.execute_query_dict(query)
        
        summary_query = """
            SELECT 
                lookup_type,
                COUNT(*) as count,
                SUM(occurrence_count) as total_occurrences
            FROM noggin_schema.unknown_hashes
            WHERE resolved_at IS NULL
            GROUP BY lookup_type
            ORDER BY count DESC
        """
        summary = db_manager.execute_query_dict(summary_query)
        
        return render_template(
            'reports/unknown_hashes.html',
            unknown=unknown,
            summary=summary
        )
    except Exception as e:
        logger.error(f"Error generating unknown hashes report: {e}")
        abort(500, description="Unknown hashes report failed")


@app.route('/reports/failed-processing')
@auth.login_required
def report_failed_processing():
    """Failed processing report"""
    try:
        query = """
            SELECT 
                nd.tip, nd.noggin_reference, nd.object_type, nd.inspection_date,
                nd.vehicle, nd.team, nd.processing_status,
                nd.retry_count, nd.last_error_message,
                nd.updated_at
            FROM noggin_schema.noggin_data nd
            WHERE nd.processing_status IN ('failed', 'api_error')
               OR nd.permanently_failed = true
            ORDER BY nd.updated_at DESC
            LIMIT 200
        """
        records = db_manager.execute_query_dict(query)
        
        return render_template(
            'reports/failed_processing.html',
            records=records
        )
    except Exception as e:
        logger.error(f"Error generating failed processing report: {e}")
        abort(500, description="Failed processing report failed")


@app.route('/reports/compliance-summary')
@auth.login_required
def report_compliance_summary():
    """Compliance summary report for LCD/LCS types"""
    try:
        query = """
            SELECT 
                object_type,
                DATE(inspection_date) as date,
                team,
                COUNT(*) as total,
                SUM(CASE WHEN compliance_yes = true THEN 1 ELSE 0 END) as compliant,
                SUM(CASE WHEN compliance_no = true THEN 1 ELSE 0 END) as non_compliant
            FROM noggin_schema.noggin_data
            WHERE object_type IN ('Load Compliance Check (Driver/Loader)', 'Load Compliance Check (Supervisor/Manager)')
              AND inspection_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY object_type, DATE(inspection_date), team
            ORDER BY date DESC, object_type, team
        """
        compliance_data = db_manager.execute_query_dict(query)
        
        # Overall summary
        summary_query = """
            SELECT 
                object_type,
                COUNT(*) as total,
                SUM(CASE WHEN compliance_yes = true THEN 1 ELSE 0 END) as compliant,
                SUM(CASE WHEN compliance_no = true THEN 1 ELSE 0 END) as non_compliant
            FROM noggin_schema.noggin_data
            WHERE object_type IN ('Load Compliance Check (Driver/Loader)', 'Load Compliance Check (Supervisor/Manager)')
              AND inspection_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY object_type
        """
        summary = db_manager.execute_query_dict(summary_query)
        
        return render_template(
            'reports/compliance_summary.html',
            compliance_data=compliance_data,
            summary=summary
        )
    except Exception as e:
        logger.error(f"Error generating compliance summary report: {e}")
        abort(500, description="Compliance summary report failed")


@app.route('/reports/export')
@auth.login_required
def report_export():
    """Export filtered records to CSV"""
    try:
        filters = parse_filters(request.args)
        
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

        if filters['team']:
            where_clauses.append("team ILIKE %s")
            params.append(f"%{filters['team']}%")

        if filters['department']:
            where_clauses.append("department ILIKE %s")
            params.append(f"%{filters['department']}%")

        if filters['driver']:
            where_clauses.append("(inspected_by ILIKE %s OR driver_loader_name ILIKE %s)")
            params.extend([f"%{filters['driver']}%"] * 2)

        if filters['date_from']:
            where_clauses.append("inspection_date >= %s")
            params.append(filters['date_from'])

        if filters['date_to']:
            where_clauses.append("inspection_date <= %s")
            params.append(filters['date_to'])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        query = f"""
            SELECT 
                noggin_reference, object_type, inspection_date,
                vehicle, trailer, trailer2, trailer3,
                team, department,
                COALESCE(inspected_by, driver_loader_name) as driver,
                processing_status, total_attachments, completed_attachment_count
            FROM noggin_schema.noggin_data
            {where_sql}
            ORDER BY inspection_date DESC
            LIMIT 10000
        """
        records = db_manager.execute_query_dict(query, tuple(params) if params else None)
        
        # Build CSV
        headers = ['noggin_reference', 'object_type', 'inspection_date', 'vehicle', 
                   'trailer', 'trailer2', 'trailer3', 'team', 'department', 'driver',
                   'processing_status', 'total_attachments', 'completed_attachment_count']
        csv_lines = [','.join(headers)]
        
        for r in records:
            row = []
            for h in headers:
                val = r.get(h, '')
                if val is None:
                    val = ''
                elif isinstance(val, datetime):
                    val = val.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    val = str(val).replace('"', '""')
                    if ',' in val or '"' in val:
                        val = f'"{val}"'
                row.append(val)
            csv_lines.append(','.join(row))
        
        csv_content = '\n'.join(csv_lines)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=noggin_export_{timestamp}.csv'}
        )
        
    except Exception as e:
        logger.error(f"Error exporting records: {e}")
        abort(500, description="Record export failed")


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
            logger.warning(f"NOBBIE SAYS: unable to retrieve status for {service_name}: {e}")
            return {
                'name': service_name,
                'active': False,
                'state': 'error',
                'substate': str(e),
                'pid': 'N/A',
                'memory': 'N/A',
                'logs': f'NOBBIE SAYS: error fetching logs: {e}'
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
        abort(500, description="Service status check failed")

# NOBBIE complaint department
def get_nobbie_excuse(error_type):
    """Returns a random, humorous excuse based on the error type."""
    
    excuses = {
        404: [
            "NOBBIE SAYS: 404. I looked everywhere. Behind the fridge, under the rug... it's gone.",
            "NOBBIE SAYS: 404. Noggin probably ate this page. It was looking hungry.",
            "NOBBIE SAYS: 404. This isn't the page you're looking for. Move along.",
            "NOBBIE SAYS: 404. I swear I left that page right here a second ago!",
            "NOBBIE SAYS: 404. ¯\\_(ツ)_/¯"
        ],
        500: [
            "NOBBIE SAYS: 500. I tried to think too hard and hurt myself.",
            "NOBBIE SAYS: 500. Something went 'bang' in the server room. I'm hiding under the desk.",
            "NOBBIE SAYS: 500. Computer says no.",
            "NOBBIE SAYS: 500. I've decided to take a nap. Please try again when I wake up.",
            "NOBBIE SAYS: 500. It's not a bug, it's a feature! (Okay, it's a bug)."
        ],
        403: [
            "NOBBIE SAYS: 403. Ah, ah, ah! You didn't say the magic word.",
            "NOBBIE SAYS: 403. My boss said you're not allowed in here.",
            "NOBBIE SAYS: 403. Nice try, but I see you.",
            "NOBBIE SAYS: 403. Access Denied. Don't take it personally."
        ]
    }
    return random.choice(excuses.get(error_type, ["NOBBIE SAYS: I'm confused."]))

@app.errorhandler(404)
def not_found_error(error):
    detail = getattr(error, 'description', None) or f"Could not find: {request.path}"
    return render_template('error.html', 
        error_code=404,
        error_title="Lost in the Void",
        error_message=get_nobbie_excuse(404),
        error_detail=detail
    ), 404

@app.errorhandler(TemplateNotFound)
def template_missing_error(error):
    # Special specific humour for missing files
    msg = f"NOBBIE SAYS: Whoops. I seem to have misplaced the '{error.name}' file. It was probably important."
    
    return render_template('error.html',
        error_code=500,
        error_title=" wardrobe malfunction",
        error_message=msg,
        error_detail=f"Missing Resource: {error.name}" 
    ), 500

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Server Error on {request.path}: {error}")
    description = getattr(error, 'description', '') or ''
    # Use abort description if provided, otherwise fall back to route path
    if description and not description.startswith('The server encountered'):
        detail = description
    else:
        detail = f"Failed Route: {request.path}"
    return render_template('error.html',
        error_code=500,
        error_title="I broke it",
        error_message=get_nobbie_excuse(500),
        error_detail=detail
    ), 500

@app.errorhandler(403)
def forbidden_error(error):
    detail = getattr(error, 'description', None) or f"Restricted Path: {request.path}"
    return render_template('error.html',
        error_code=403,
        error_title="Verboten",
        error_message=get_nobbie_excuse(403),
        error_detail=detail
    ), 403


@app.errorhandler(400)
def bad_request_error(error):
    detail = getattr(error, 'description', None) or f"Bad Request: {request.path}"
    return render_template('error.html',
        error_code=400,
        error_title="Bad Request",
        error_message="NOBBIE SAYS: That request did not make sense. Try again with feeling.",
        error_detail=detail
    ), 400

if __name__ == '__main__':
    logger.info("Starting Noggin Object Binary Backup & Ingestion Engine")
    app.run(host='0.0.0.0', port=5000, debug=True)