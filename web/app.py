import os
import logging
import json
import io  # Added for BytesIO
import psycopg2
from psycopg2 import pool # Added for connection pooling
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, abort, send_file, redirect, url_for

from config_manager import ConfigManager
from email_manager import EmailManager

LOG_DIR = '/mnt/data/noggin/log'
if not os.path.exists(LOG_DIR):
    LOG_DIR = '.' 

logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'web_app_enhanced.log'),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('NogginWeb')

app = Flask(__name__)

config_mgr = ConfigManager('../config/base_config.ini')
email_mgr = EmailManager()

# --- Database Connection Pool ---
# We use a global variable to hold the pool. 
# In Gunicorn, this runs once per worker process.
try:
    db_conf = config_mgr.get_db_config()
    if not db_conf:
        raise ValueError("Database configuration not found")

    # Create a pool of connections (min=1, max=10)
    pg_pool = psycopg2.pool.ThreadedConnectionPool(
        1, 10,
        host=db_conf.get('host'),
        port=db_conf.get('port'),
        database=db_conf.get('database'),
        user=db_conf.get('user'),
        password=db_conf.get('password')
    )
    logger.info("Database connection pool created successfully.")
except Exception as e:
    logger.error(f"Failed to create DB pool: {e}")
    pg_pool = None

def get_db_connection():
    """Retrieves a connection from the pool."""
    if not pg_pool:
        raise RuntimeError("Database pool is not initialized.")
    return pg_pool.getconn()

def return_db_connection(conn):
    """Returns a connection to the pool."""
    if pg_pool and conn:
        pg_pool.putconn(conn)

# --- Routes ---

@app.route('/')
def index():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # FIX: Updated status checks to match lowercase PostgreSQL ENUM values
        cursor.execute("""
            SELECT 
                COUNT(*) as total_inspections,
                COUNT(CASE WHEN processing_status = 'complete' THEN 1 END) as completed_inspections,
                COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending_inspections,
                COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_inspections
            FROM noggin_schema.noggin_data
        """)
        stats = cursor.fetchone()

        # FIX: Updated status checks for attachments to match lowercase ENUM values
        cursor.execute("""
            SELECT 
                COUNT(*) as total_attachments,
                COUNT(CASE WHEN a.attachment_status = 'complete' THEN 1 END) as completed_count,
                COUNT(CASE WHEN a.attachment_status = 'downloading' THEN 1 END) as downloading_count,
                COUNT(CASE WHEN a.attachment_status = 'failed' THEN 1 END) as failed_count,
                SUM(COALESCE(a.file_size_bytes, 0)) as total_bytes
            FROM noggin_schema.attachments a
        """)
        attachment_stats = cursor.fetchone()

        # Fetch recent activity
        cursor.execute("""
            SELECT tip, object_type, processing_status, updated_at
            FROM noggin_schema.noggin_data
            ORDER BY updated_at DESC
            LIMIT 5
        """)
        recent_activity = cursor.fetchall()

        return render_template(
            'dashboard.html',
            stats=stats,
            attachment_stats=attachment_stats,
            recent_activity=recent_activity
        )

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        # In production, return a custom error page 500.html
        return "Internal Server Error", 500
    finally:
        if conn:
            # Return connection to the pool
            pg_pool.putconn(conn)
        
@app.route('/inspection/<inspection_id>')
def inspection_details(inspection_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Fetch Inspection Core Data
        cursor.execute("""
            SELECT * FROM noggin_schema.unknown_hashes 
            WHERE first_seen_inspection_id = %s 
            LIMIT 1
        """, (inspection_id,))
        
        record = cursor.fetchone()
        
        if not record:
            logger.warning(f"Inspection {inspection_id} not found.")
            object_type = inspection_id.split('-')[0] if '-' in inspection_id else 'Unknown'
        else:
            object_type = record.get('lookup_type', 'Unknown')

        # 2. Get Configuration
        display_type_label = config_mgr.get_inspection_type_label(object_type)
        display_fields = config_mgr.get_display_fields(object_type)

        # 3. Parse Data Payload
        data_payload = {}
        if record and record.get('resolved_value'):
            try:
                val = record['resolved_value']
                if val and val.strip().startswith('{'):
                    data_payload = json.loads(val)
            except json.JSONDecodeError:
                pass

        # 4. Map Fields
        rendered_fields = []
        for field in display_fields:
            db_col = field['db_column']
            val = data_payload.get(db_col)
            if val is None and record:
                val = record.get(db_col)
            
            if val is None: val = '-'
            if isinstance(val, bool): val = 'Yes' if val else 'No'

            rendered_fields.append({'label': field['label'], 'value': val})

        # 5. Fetch Attachments
        cursor.execute("""
            SELECT record_tip, attachment_tip, filename, file_path 
            FROM noggin_schema.attachments 
            WHERE record_tip = (
                SELECT tip_hash FROM noggin_schema.unknown_hashes 
                WHERE first_seen_inspection_id = %s LIMIT 1
            )
        """, (inspection_id,))
        attachments = cursor.fetchall()

        return render_template(
            'inspection_details.html',
            inspection_id=inspection_id,
            type_label=display_type_label,
            fields=rendered_fields,
            attachments=attachments,
            object_type=object_type
        )

    except Exception as e:
        logger.error(f"Error serving inspection page: {e}", exc_info=True)
        return "Internal Server Error", 500
    finally:
        if conn: return_db_connection(conn)

@app.route('/inspection/<inspection_id>/attachment/<attachment_tip>')
def view_attachment(inspection_id, attachment_tip):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT file_path, filename FROM noggin_schema.attachments WHERE attachment_tip = %s", (attachment_tip,))
        result = cursor.fetchone()
        
        if not result: abort(404)
            
        file_path = result['file_path']
        if not os.path.exists(file_path):
            abort(404, description="File not found on disk")
            
        return send_file(file_path, download_name=result['filename'])
        
    except Exception as e:
        logger.error(f"Error fetching attachment: {e}")
        abort(500)
    finally:
        if conn: return_db_connection(conn)

@app.route('/inspection/<inspection_id>/eml')
def download_eml(inspection_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT lookup_type FROM noggin_schema.unknown_hashes WHERE first_seen_inspection_id = %s LIMIT 1", (inspection_id,))
        row = cursor.fetchone()
        object_type = row['lookup_type'] if row else 'Unknown'
        type_label = config_mgr.get_inspection_type_label(object_type)
        
        cursor.execute("""
            SELECT file_path, filename 
            FROM noggin_schema.attachments 
            WHERE record_tip = (
                SELECT tip_hash FROM noggin_schema.unknown_hashes 
                WHERE first_seen_inspection_id = %s LIMIT 1
            )
        """, (inspection_id,))
        attachments = cursor.fetchall()
        
        eml_bytes = email_mgr.generate_inspection_eml(
            {'id': inspection_id, 'type_label': type_label},
            attachments
        )
        
        # FIX: Wrap bytes in BytesIO
        return send_file(
            io.BytesIO(eml_bytes),
            as_attachment=True,
            download_name=f"{object_type}_{inspection_id}.eml",
            mimetype='message/rfc822'
        )

    except Exception as e:
        logger.error(f"EML generation failed: {e}", exc_info=True)
        return "Error creating export", 500
    finally:
        if conn: return_db_connection(conn)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)