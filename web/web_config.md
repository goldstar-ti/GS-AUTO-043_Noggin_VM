For Your Noggin Web Interface
You have three options:
Option 1: Use Existing Web Server (Recommended)
If you have Apache or Nginx already running:
bash# Check which one you have
systemctl status apache2
# or
systemctl status nginx
Advantages:

Already configured and running
Can host multiple applications
Better performance for production

Option 2: Use Flask's Built-in Server (Development Only)
bash# Simple, but not for production
python app.py
# Runs on http://localhost:5000
Advantages:

Quick setup
No web server configuration needed

Disadvantages:

Not secure for production
Single-threaded
No SSL by default

Option 3: Use Gunicorn + Nginx (Production Recommended)
bashpip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
Advantages:

Production-ready
Multiple workers
Better performance


Quick Detection Commands
Run these to get instant answers:
bash# What's on port 80?
sudo lsof -i :80 | awk 'NR>1 {print $1}' | uniq

# What's on port 443?
sudo lsof -i :443 | awk 'NR>1 {print $1}' | uniq

# Show me everything web-related
sudo netstat -tlnp | grep -E ':(80|443|5050|8080|10000)' | \
    awk '{print $4 " -> " $7}' | \
    sed 's/.*:/Port /' | \
    sed 's/\// -> /'
```

---

## Expected Output Examples

### If Apache is Running:
```
Port 80 -> apache2
Port 443 -> apache2
```

### If Nginx is Running:
```
Port 80 -> nginx
Port 443 -> nginx
```

### If Webmin Only:
```
Port 10000 -> perl (webmin)

Next Steps
Once you run the detection commands and tell me what you find, I can help you:

Configure existing web server to host Noggin interface
Set up new Flask application on appropriate port
Integrate with Apache/Nginx using reverse proxy
Secure with SSL (Let's Encrypt)
Set up authentication for web access

Run the detection script above and share the output, then we'll proceed with the best approach for your setup!RetryPGPorts in use:
0.0.0.0:10000 0.0.0.0:* 
[::]:10000 [::]:* 
*:80 *:*Apache:
Installed: Server version: Apache/2.4.58 (Ubuntu)
active
Status: RUNNINGNginx:
Not installedWebmin:
active
Status: RUNNING on port 10000
Access: https://192.168.0.236:10000pgAdmin:
Not runningActive web listeners:
perl *:10000
perl *:10000
apache2 *:80
apache2 *:80
apache2 *:80can we setup port 443? i've tried to setup a certificate with webminPerfect! You have Apache running on port 80 and Webmin on port 10000. Let's set up SSL (port 443) and create a proper web interface for your Noggin system.

Stage 12: Web Interface with SSL
Step 1: Enable SSL on Apache
bash# Enable SSL module
sudo a2enmod ssl

# Enable headers module (for security)
sudo a2enmod headers

# Enable proxy modules (for Flask/Python apps)
sudo a2enmod proxy
sudo a2enmod proxy_http

# Restart Apache
sudo systemctl restart apache2

# Verify port 443 is listening
sudo ss -tlnp | grep :443

Step 2: Generate Self-Signed Certificate (For Testing)
bash# Create directory for certificates
sudo mkdir -p /etc/apache2/ssl

# Generate self-signed certificate (valid for 1 year)
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/apache2/ssl/noggin.key -out /etc/apache2/ssl/noggin.crt -subj "/C=AU/ST=WA/L=Perth/O=GoldstarTransport/OU=IT/CN=gs-sv-011.internal.goldstargroup.au"

# Set proper permissions
sudo chmod 600 /etc/apache2/ssl/noggin.key
sudo chmod 644 /etc/apache2/ssl/noggin.crt
Note: For production, use Let's Encrypt (we'll set that up after testing)

Step 3: Create Flask Web Application
Create /home/noggin_admin/scripts/web/app.py:
python
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
app.secret_key = 'your-secret-key-change-this'  # CHANGE THIS!

auth = HTTPBasicAuth()

# Initialize
config = ConfigLoader(
    '../config/base_config.ini',
    '../config/load_compliance_check_driver_loader_config.ini'
)
db_manager = DatabaseConnectionManager(config)
hash_manager = HashManager(config, db_manager)

# Users (in production, use database)
users = {
    "admin": generate_password_hash("admin123")  # CHANGE THIS!
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

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
                object_type,
                COUNT(*) as count
            FROM unknown_hashes
            WHERE resolved_at IS NULL
            GROUP BY object_type
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

Step 4: Create Templates
Create directory structure:
bash
mkdir -p ~/scripts/web/templates
mkdir -p ~/scripts/web/static/css
Create ~/scripts/web/templates/base.html:
html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Noggin Processor{% endblock %}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        
        .header {
            background: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 1.5rem;
            font-weight: 500;
        }
        
        .nav {
            background: #34495e;
            padding: 0.5rem 2rem;
        }
        
        .nav a {
            color: white;
            text-decoration: none;
            padding: 0.5rem 1rem;
            display: inline-block;
            transition: background 0.2s;
        }
        
        .nav a:hover {
            background: #2c3e50;
        }
        
        .nav a.active {
            background: #2c3e50;
            border-bottom: 2px solid #3498db;
        }
        
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            padding: 0 2rem;
        }
        
        .card {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .card h2 {
            margin-bottom: 1rem;
            color: #2c3e50;
            font-size: 1.3rem;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .stat-card .number {
            font-size: 2.5rem;
            font-weight: bold;
            color: #3498db;
            margin: 0.5rem 0;
        }
        
        .stat-card .label {
            color: #7f8c8d;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .stat-card.success .number { color: #27ae60; }
        .stat-card.warning .number { color: #f39c12; }
        .stat-card.danger .number { color: #e74c3c; }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table th {
            background: #ecf0f1;
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #2c3e50;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tr:hover {
            background: #f8f9fa;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        
        .badge.success { background: #d4edda; color: #155724; }
        .badge.warning { background: #fff3cd; color: #856404; }
        .badge.danger { background: #f8d7da; color: #721c24; }
        .badge.info { background: #d1ecf1; color: #0c5460; }
        .badge.secondary { background: #e2e3e5; color: #383d41; }
        
        .btn {
            display: inline-block;
            padding: 0.5rem 1rem;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            border: none;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .btn:hover {
            background: #2980b9;
        }
        
        .btn.danger {
            background: #e74c3c;
        }
        
        .btn.danger:hover {
            background: #c0392b;
        }
        
        .pagination {
            display: flex;
            justify-content: center;
            gap: 0.5rem;
            margin-top: 2rem;
        }
        
        .pagination a {
            padding: 0.5rem 1rem;
            background: white;
            border: 1px solid #ddd;
            text-decoration: none;
            color: #333;
            border-radius: 4px;
        }
        
        .pagination a.active {
            background: #3498db;
            color: white;
            border-color: #3498db;
        }
        
        .filter-form {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .filter-form input,
        .filter-form select {
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1rem;
        }
        
        .filter-form input {
            flex: 1;
        }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <div class="header">
        <h1>🔧 Noggin Data Processor</h1>
    </div>
    
    <nav class="nav">
        <a href="{{ url_for('index') }}" class="{% if request.endpoint == 'index' %}active{% endif %}">Dashboard</a>
        <a href="{{ url_for('inspections') }}" class="{% if request.endpoint == 'inspections' %}active{% endif %}">Inspections</a>
        <a href="{{ url_for('hashes') }}" class="{% if request.endpoint == 'hashes' %}active{% endif %}">Hashes</a>
        <a href="{{ url_for('service_status') }}" class="{% if request.endpoint == 'service_status' %}active{% endif %}">Service Status</a>
    </nav>
    
    <div class="container">
        {% block content %}{% endblock %}
    </div>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
Create ~/scripts/web/templates/dashboard.html:
html{% extends "base.html" %}

{% block title %}Dashboard - Noggin Processor{% endblock %}

{% block content %}
<div class="stats-grid">
    {% set status_mapping = {
        'complete': ('success', '✓'),
        'pending': ('info', '⏳'),
        'failed': ('danger', '✗'),
        'partial': ('warning', '⚠'),
        'api_failed': ('danger', '🔌'),
        'interrupted': ('warning', '⏸')
    } %}
    
    {% for stat in stats %}
        {% set status_class, icon = status_mapping.get(stat.processing_status, ('secondary', '•')) %}
        <div class="stat-card {{ status_class }}">
            <div class="label">{{ icon }} {{ stat.processing_status|upper }}</div>
            <div class="number">{{ stat.count }}</div>
        </div>
    {% endfor %}
</div>

<div class="card">
    <h2>Today's Activity</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">Total Processed</div>
            <div class="number">{{ today_stats.total_today or 0 }}</div>
        </div>
        <div class="stat-card success">
            <div class="label">Completed</div>
            <div class="number">{{ today_stats.completed_today or 0 }}</div>
        </div>
        <div class="stat-card">
            <div class="label">Success Rate</div>
            <div class="number">
                {% if today_stats.total_today and today_stats.total_today > 0 %}
                    {{ "%.1f"|format((today_stats.completed_today / today_stats.total_today) * 100) }}%
                {% else %}
                    0%
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div class="card">
    <h2>Recent Activity</h2>
    <table>
        <thead>
            <tr>
                <th>LCD Inspection ID</th>
                <th>Date</th>
                <th>Status</th>
                <th>Attachments</th>
                <th>Updated</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for item in recent %}
            <tr>
                <td>{{ item.lcd_inspection_id or 'N/A' }}</td>
                <td>{{ item.inspection_date.strftime('%Y-%m-%d') if item.inspection_date else 'N/A' }}</td>
                <td>
                    {% set status_class = {
                        'complete': 'success',
                        'pending': 'info',
                        'failed': 'danger',
                        'partial': 'warning'
                    }.get(item.processing_status, 'secondary') %}
                    <span class="badge {{ status_class }}">{{ item.processing_status }}</span>
                </td>
                <td>{{ item.completed_attachment_count or 0 }} / {{ item.total_attachments or 0 }}</td>
                <td>{{ item.updated_at.strftime('%Y-%m-%d %H:%M') if item.updated_at else 'N/A' }}</td>
                <td>
                    <a href="{{ url_for('inspection_detail', tip=item.tip) }}" class="btn">View</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}

Step 5: Install Flask Dependencies
bash
cd ~/scripts
source .venv/bin/activate

pip install flask flask-httpauth gunicorn

Step 6: Configure Apache Virtual Host with SSL
Create /etc/apache2/sites-available/noggin-ssl.conf:
apache
<VirtualHost *:443>
    ServerName gs-sv-011.internal.goldstargroup.au
    ServerAlias 192.168.0.236

    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /etc/apache2/ssl/noggin.crt
    SSLCertificateKeyFile /etc/apache2/ssl/noggin.key

    # Security headers
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"

    # Proxy to Flask app
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/

    # Logs
    ErrorLog ${APACHE_LOG_DIR}/noggin-error.log
    CustomLog ${APACHE_LOG_DIR}/noggin-access.log combined
</VirtualHost>

# Redirect HTTP to HTTPS
<VirtualHost *:80>
    ServerName gs-sv-011.internal.goldstargroup.au
    ServerAlias 192.168.0.236
    
    Redirect permanent / https://192.168.0.236/
</VirtualHost>
Enable the site:
bash
sudo a2ensite noggin-ssl
sudo systemctl reload apache2

Step 7: Create Systemd Service for Flask App
Create /etc/systemd/system/noggin-web.service:
ini
[Unit]
Description=Noggin Web Interface
After=network.target postgresql.service

[Service]
Type=notify
User=noggin_admin
Group=noggin_admin
WorkingDirectory=/home/noggin_admin/scripts/web
Environment="PATH=/home/noggin_admin/scripts/.venv/bin"
ExecStart=/home/noggin_admin/scripts/.venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --access-logfile /mnt/data/noggin/log/web-access.log \
    --error-logfile /mnt/data/noggin/log/web-error.log \
    app:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
Enable and start:
bash
sudo systemctl daemon-reload
sudo systemctl enable noggin-web
sudo systemctl start noggin-web
sudo systemctl status noggin-web

Step 8: Test the Setup
bash# Check if Flask app is running
curl http://127.0.0.1:5000

# Check if Apache is proxying correctly
curl -k https://192.168.0.236/

# Check port 443 is listening
sudo ss -tlnp | grep :443

Step 9: Access Web Interface
Open browser:

HTTPS: https://192.168.0.236/
HTTP: http://192.168.0.236/ (redirects to HTTPS)

Login:

Username: admin
Password: admin123 (CHANGE THIS!)


You should now see your Noggin dashboard! Let me know if you hit any issues and we'll troubleshoot together.
Would you like me to continue with the remaining templates (inspections.html, inspection_detail.html, etc.) in the next message?