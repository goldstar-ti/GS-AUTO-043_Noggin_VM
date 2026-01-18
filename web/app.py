import os
import logging
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, abort, send_file, request, Response
from config_manager import ConfigManager
from email_manager import EmailManager

# --- Logging Setup ---
# Use standard system path or local fallback
LOG_DIR = '/mnt/data/noggin/log'
if not os.path.exists(LOG_DIR):
    LOG_DIR = '.' # Fallback to current dir

logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'web_app_enhanced.log'),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('NogginWeb')

app = Flask(__name__)

# --- Initialization ---
# Assuming base_config.ini is in the same directory or config/
config_mgr = ConfigManager('base_config.ini')
email_mgr = EmailManager()

def get_db_connection():
    """Factory to create a database connection using base_config.ini."""
    try:
        db_conf = config_mgr.get_db_config()
        if not db_conf:
            raise ValueError("Database configuration not found in base_config.ini")

        conn = psycopg2.connect(
            host=db_conf.get('host'),
            port=db_conf.get('port'),
            database=db_conf.get('database'),
            user=db_conf.get('user'),
            password=db_conf.get('password')
        )
        return conn
    except Exception as e:
        logger.error(f"DB Connection failed: {e}")
        raise

@app.route('/inspection/<inspection_id>')
def inspection_details(inspection_id):
    """
    Renders the enhanced inspection details page.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Fetch Inspection Core Data
        # We query unknown_hashes as the registry. 
        cursor.execute("""
            SELECT * FROM noggin_schema.unknown_hashes 
            WHERE first_seen_inspection_id = %s 
            LIMIT 1
        """, (inspection_id,))
        
        record = cursor.fetchone()
        
        if not record:
            logger.warning(f"Inspection {inspection_id} not found.")
            # Basic fallback to infer type from ID (e.g. LCD-123 -> LCD)
            object_type = inspection_id.split('-')[0] if '-' in inspection_id else 'Unknown'
        else:
            object_type = record.get('lookup_type', 'Unknown')

        # 2. Get Configuration
        display_type_label = config_mgr.get_inspection_type_label(object_type)
        display_fields = config_mgr.get_display_fields(object_type)

        # 3. Parse Data Payload
        # We prioritize:
        #   a) The 'resolved_value' JSON blob (if available)
        #   b) Columns in the 'unknown_hashes' table
        
        data_payload = {}
        if record and record.get('resolved_value'):
            try:
                # Check if it looks like JSON
                val = record['resolved_value']
                if val and val.strip().startswith('{'):
                    data_payload = json.loads(val)
            except json.JSONDecodeError:
                pass

        # 4. Map Fields to Values
        rendered_fields = []
        for field in display_fields:
            db_col = field['db_column']
            # Try to find value in JSON payload first, then record column
            val = data_payload.get(db_col)
            if val is None and record:
                val = record.get(db_col)
            
            # If still None, placeholder
            if val is None:
                val = '-'
            
            # Formatting: If boolean, make it readable
            if isinstance(val, bool):
                val = 'Yes' if val else 'No'

            rendered_fields.append({
                'label': field['label'],
                'value': val
            })

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
        if conn: conn.close()

@app.route('/inspection/<inspection_id>/attachment/<attachment_tip>')
def view_attachment(inspection_id, attachment_tip):
    """
    Serves an attachment file for the popup modal.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT file_path, filename 
            FROM noggin_schema.attachments 
            WHERE attachment_tip = %s
        """, (attachment_tip,))
        result = cursor.fetchone()
        
        if not result:
            abort(404)
            
        file_path = result['file_path']
        filename = result['filename']
        
        if not os.path.exists(file_path):
            abort(404, description="File not found on disk")
            
        return send_file(file_path, download_name=filename)
        
    except Exception as e:
        logger.error(f"Error fetching attachment: {e}")
        abort(500)
    finally:
        if conn: conn.close()

@app.route('/inspection/<inspection_id>/eml')
def download_eml(inspection_id):
    """
    Generates and downloads the .eml export.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get basic info
        cursor.execute("""
            SELECT lookup_type FROM noggin_schema.unknown_hashes 
            WHERE first_seen_inspection_id = %s LIMIT 1
        """, (inspection_id,))
        row = cursor.fetchone()
        object_type = row['lookup_type'] if row else 'Unknown'
        type_label = config_mgr.get_inspection_type_label(object_type)
        
        # Get attachments
        cursor.execute("""
            SELECT file_path, filename 
            FROM noggin_schema.attachments 
            WHERE record_tip = (
                SELECT tip_hash FROM noggin_schema.unknown_hashes 
                WHERE first_seen_inspection_id = %s LIMIT 1
            )
        """, (inspection_id,))
        attachments = cursor.fetchall()
        
        # Generate EML
        eml_bytes = email_mgr.generate_inspection_eml(
            {'id': inspection_id, 'type_label': type_label},
            attachments
        )
        
        return send_file(
            eml_bytes,
            as_attachment=True,
            download_name=f"{object_type}_{inspection_id}.eml",
            mimetype='message/rfc822'
        )

    except Exception as e:
        logger.error(f"EML generation failed: {e}", exc_info=True)
        return "Error creating export", 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    # Production: Use Gunicorn. Development: Use this.
    app.run(host='0.0.0.0', port=5000, debug=True)