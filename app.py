import os
import time
import requests
import yaml
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

CONFIG_FILE = 'config.yml'

# In-memory tracking for failed login rate-limiting / webhook updating
failed_login_tracker = {
    'count': 0,
    'last_attempt': 0,
    'webhook_message_id': None
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            "config.yml not found! Please ensure setup.sh has been run to configure admin credentials."
        )
    with open(CONFIG_FILE, 'r') as f:
        return yaml.safe_load(f)

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(data, f)

def send_discord_security_alert(failed_count, client_ip):
    config = load_config()
    webhook_url = config.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        return

    now = time.time()
    # Reset count if it's been more than 10 minutes since the last failure
    if now - failed_login_tracker['last_attempt'] > 600:
        failed_login_tracker['count'] = 0
        failed_login_tracker['webhook_message_id'] = None

    failed_login_tracker['count'] = failed_count
    failed_login_tracker['last_attempt'] = now

    payload = {
        "content": f"🚨 **Security Alert**: Detected multiple failed admin login attempts!\n- **Failed Count**: `{failed_login_tracker['count']}`\n- **Last Source IP**: `{client_ip}`"
    }

    try:
        if failed_login_tracker['webhook_message_id']:
            # Edit the existing message instead of sending a new one
            edit_url = f"{webhook_url}/messages/{failed_login_tracker['webhook_message_id']}"
            response = requests.patch(edit_url, json=payload, timeout=5)
            if response.status_code != 200:
                failed_login_tracker['webhook_message_id'] = None
        
        if not failed_login_tracker['webhook_message_id']:
            # Send a new message and save its ID
            response = requests.post(f"{webhook_url}?wait=true", json=payload, timeout=5)
            if response.status_code in [200, 201]:
                data = response.json()
                failed_login_tracker['webhook_message_id'] = data.get('id')
    except Exception as e:
        print(f"Failed to send Discord webhook: {e}")

# HTML Template with Public View, Modal, Admin Login, and Dashboard Management
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Proxmox VE Custom Scripts</title>
    <style>
        :root {
            --bg-base: #090d16;
            --bg-card: #111827;
            --bg-card-hover: #162032;
            --border-color: #1f293d;
            --text-main: #f9fafb;
            --text-muted: #9ca3af;
            --accent: #00e676;
            --accent-glow: rgba(0, 230, 118, 0.15);
            --tag-bg: #142820;
            --tag-text: #00e676;
            --danger: #ff5252;
        }
        body { font-family: system-ui, -apple-system, sans-serif; background-color: var(--bg-base); color: var(--text-main); margin: 0; padding: 0; min-height: 100vh; }
        nav { display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; border-bottom: 1px solid var(--border-color); background-color: rgba(9, 13, 22, 0.8); backdrop-filter: blur(10px); }
        .logo-area { display: flex; align-items: center; gap: 12px; font-weight: bold; font-size: 1.1rem; }
        .logo-box { background-color: var(--accent); color: #000; padding: 6px 10px; border-radius: 6px; font-weight: 900; box-shadow: 0 0 15px var(--accent-glow); }
        .nav-links a { color: var(--text-muted); text-decoration: none; margin-left: 20px; font-size: 0.9rem; transition: color 0.2s; }
        .nav-links a:hover { color: var(--accent); }
        .hero { text-align: center; padding: 50px 20px 30px; }
        .hero h1 { font-size: 2.8rem; margin-bottom: 10px; font-weight: 800; }
        .hero h1 span { color: var(--accent); text-shadow: 0 0 20px var(--accent-glow); }
        .hero p { color: var(--text-muted); font-size: 1.1rem; max-width: 600px; margin: 0 auto; }
        
        .grid-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; padding: 20px 40px 60px; }
        .card { background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 22px; cursor: pointer; transition: all 0.3s ease; display: flex; flex-direction: column; justify-content: space-between; }
        .card:hover { background-color: var(--bg-card-hover); border-color: var(--accent); transform: translateY(-5px); box-shadow: 0 10px 30px -10px var(--accent-glow); }
        .card-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
        .card-icon { width: 36px; height: 36px; background: var(--tag-bg); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: var(--accent); }
        .card h3 { margin: 0; font-size: 1.25rem; }
        .card p { color: var(--text-muted); font-size: 0.9rem; line-height: 1.4; margin: 0 0 16px 0; }
        .tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px; }
        .tag { background-color: var(--tag-bg); color: var(--tag-text); font-size: 0.75rem; padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(0, 230, 118, 0.1); }
        .card-footer { display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: var(--text-muted); border-top: 1px solid var(--border-color); padding-top: 12px; }

        /* Modal */
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(8px); display: none; justify-content: center; align-items: center; z-index: 1000; padding: 20px; }
        .modal { background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 16px; width: 100%; max-width: 850px; max-height: 90vh; overflow-y: auto; padding: 30px; position: relative; }
        .close-btn { position: absolute; top: 20px; right: 20px; background: none; border: none; color: var(--text-muted); font-size: 1.5rem; cursor: pointer; }
        
        /* Admin Dashboard Container */
        .admin-container { max-width: 1000px; margin: 40px auto; padding: 0 20px; }
        .admin-table { width: 100%; border-collapse: collapse; background: var(--bg-card); border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color); margin-top: 20px; }
        .admin-table th, .admin-table td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border-color); font-size: 0.9rem; }
        .admin-table th { background: rgba(0,0,0,0.2); color: var(--text-muted); }
        .btn { background: var(--accent); color: #000; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-danger { background: var(--danger); color: #fff; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: var(--text-muted); font-size: 0.85rem; }
        .form-group input, .form-group textarea { width: 100%; padding: 10px; background: #04060a; border: 1px solid var(--border-color); color: #fff; border-radius: 6px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
    </style>
</head>
<body>
    <nav>
        <div class="logo-area">
            <div class="logo-box">PVE</div>
            <span>Custom Script Manager</span>
        </div>
        <div class="nav-links">
            <a href="/">Home</a>
            {% if session.get('logged_in') %}
                <a href="/admin">Dashboard</a>
                <a href="/logout">Logout</a>
            {% else %}
                <a href="/login">Admin Login</a>
            {% endif %}
        </div>
    </nav>

    {% block content %}{% endblock %}
</body>
</html>
"""

INDEX_PAGE = TEMPLATE.replace('{% block content %}{% endblock %}', """
    <div class="hero">
        <h1>Your homelab, <span>automated.</span></h1>
        <p>Personal Proxmox VE LXC container deployment scripts, fully managed and self-hosted.</p>
    </div>

    <div class="grid-container">
        {% for s in scripts %}
            <div class="card" onclick="openModal('{{ s.id }}')">
                <div>
                    <div class="card-header">
                        <div class="card-icon">💻</div>
                        <h3>{{ s.title }}</h3>
                    </div>
                    <p>{{ s.description }}</p>
                    <div class="tags">
                        {% for tag in s.tags.split(',') %}
                            <span class="tag">{{ tag.strip() }}</span>
                        {% endfor %}
                    </div>
                </div>
                <div class="card-footer">
                    <span>Category: {{ s.category }}</span>
                    <span style="color: var(--accent);">View details &rarr;</span>
                </div>
            </div>
        {% endfor %}
    </div>

    <!-- Modal View Details -->
    <div class="modal-overlay" id="modalOverlay" onclick="closeModal(event)">
        <div class="modal" id="modalContent" onclick="event.stopPropagation()">
            <button class="close-btn" onclick="closeModalDirect()">&times;</button>
            <div id="modalBody"></div>
        </div>
    </div>

    <script>
        const scriptData = {{ scripts | tojson }};
        
        function openModal(id) {
            const s = scriptData.find(item => item.id === id);
            const modalBody = document.getElementById('modalBody');
            modalBody.innerHTML = `
                <h2 style="margin-top:0; color: var(--accent);">${s.title}</h2>
                <p style="color: var(--text-muted);">${s.description}</p>
                <div style="background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; margin-top: 15px;">
                    <h4 style="margin:0 0 10px 0; color: var(--text-muted); text-transform:uppercase; font-size:0.8rem;">Install Command</h4>
                    <div style="background:#04060a; padding:10px; border-radius:6px; font-family:monospace; color:var(--accent); overflow-x:auto;">${s.installCmd}</div>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-top:15px;">
                    <div style="background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px;">
                        <h4 style="margin:0 0 5px 0; color: var(--text-muted); text-transform:uppercase; font-size:0.8rem;">Credentials</h4>
                        <p style="margin:5px 0;"><strong>User:</strong> ${s.user}</p>
                        <p style="margin:5px 0; font-size:0.85rem; color:var(--text-muted);">${s.credentialsNote}</p>
                    </div>
                    <div style="background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px;">
                        <h4 style="margin:0 0 5px 0; color: var(--text-muted); text-transform:uppercase; font-size:0.8rem;">Specs (CPU / RAM / HDD)</h4>
                        <p style="margin:5px 0;">${s.cpu} | ${s.ram} | ${s.hdd}</p>
                        <p style="margin:10px 0 0 0;"><a href="${s.website}" target="_blank" style="color:var(--accent); text-decoration:none;">GitHub Repo &rarr;</a></p>
                    </div>
                </div>
            `;
            document.getElementById('modalOverlay').style.display = 'flex';
        }

        function closeModal(e) { if (e.target.id === 'modalOverlay') document.getElementById('modalOverlay').style.display = 'none'; }
        function closeModalDirect() { document.getElementById('modalOverlay').style.display = 'none'; }
    </script>
""")

LOGIN_PAGE = TEMPLATE.replace('{% block content %}{% endblock %}', """
    <div style="max-width: 400px; margin: 80px auto; background: var(--bg-card); padding: 30px; border-radius: 12px; border: 1px solid var(--border-color);">
        <h2 style="margin-top:0; color: var(--accent);">Admin Login</h2>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <p style="color: var(--danger); font-size: 0.9rem;">{{ messages[0] }}</p>
          {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
            <button type="submit" class="btn" style="width:100%; margin-top:10px;">Login</button>
        </form>
    </div>
""")

ADMIN_DASHBOARD = TEMPLATE.replace('{% block content %}{% endblock %}', """
    <div class="admin-container">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>Script Management Dashboard</h2>
            <a href="/admin/new" class="btn">+ Add New Script</a>
        </div>
        <table class="admin-table">
            <thead>
                <tr>
                    <th>Title</th>
                    <th>Category</th>
                    <th>Runs In</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for s in scripts %}
                <tr>
                    <td><strong>{{ s.title }}</strong></td>
                    <td>{{ s.category }}</td>
                    <td>{{ s.runsIn }}</td>
                    <td>
                        <a href="/admin/edit/{{ s.id }}" class="btn" style="padding: 4px 10px; font-size: 0.8rem;">Edit</a>
                        <a href="/admin/delete/{{ s.id }}" class="btn btn-danger" style="padding: 4px 10px; font-size: 0.8rem;" onclick="return confirm('Are you sure?')">Delete</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
""")

ADMIN_FORM = TEMPLATE.replace('{% block content %}{% endblock %}', """
    <div class="admin-container" style="max-width: 700px;">
        <h2>{{ action }} Script</h2>
        <form method="POST" style="background: var(--bg-card); padding: 30px; border-radius: 12px; border: 1px solid var(--border-color); margin-top: 20px;">
            <div class="form-row">
                <div class="form-group"><label>Script ID (unique slug e.g. jellyfin)</label><input type="text" name="id" value="{{ script.id if script else '' }}" required></div>
                <div class="form-group"><label>Title</label><input type="text" name="title" value="{{ script.title if script else '' }}" required></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Category</label><input type="text" name="category" value="{{ script.category if script else '' }}" required></div>
                <div class="form-group"><label>Tags (comma separated)</label><input type="text" name="tags" value="{{ script.tags if script else '' }}" required></div>
            </div>
            <div class="form-group"><label>Description</label><textarea name="description" rows="3" required>{{ script.description if script else '' }}</textarea></div>
            <div class="form-group"><label>Install Command</label><input type="text" name="installCmd" value="{{ script.installCmd if script else '' }}" required></div>
            <div class="form-row">
                <div class="form-group"><label>Website / GitHub Link</label><input type="text" name="website" value="{{ script.website if script else '' }}"></div>
                <div class="form-group"><label>Runs In</label><input type="text" name="runsIn" value="{{ script.runsIn if script else 'LXC' }}"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>CPU Cores</label><input type="text" name="cpu" value="{{ script.cpu if script else '1 Core' }}"></div>
                <div class="form-group"><label>RAM Size</label><input type="text" name="ram" value="{{ script.ram if script else '1024 MB' }}"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>HDD Size</label><input type="text" name="hdd" value="{{ script.hdd if script else '4 GB' }}"></div>
                <div class="form-group"><label>Default User</label><input type="text" name="user" value="{{ script.user if script else 'admin' }}"></div>
            </div>
            <div class="form-group"><label>Credentials / Security Note</label><input type="text" name="credentialsNote" value="{{ script.credentialsNote if script else '' }}"></div>
            <button type="submit" class="btn" style="margin-top: 15px;">Save Script</button>
            <a href="/admin" class="btn" style="background: transparent; color: var(--text-muted); border: 1px solid var(--border-color);">Cancel</a>
        </form>
    </div>
""")

@app.route('/')
def index():
    config = load_config()
    return render_template_string(INDEX_PAGE, scripts=config.get('scripts', []))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        config = load_config()
        client_ip = request.remote_addr or "Unknown IP"
        if request.form['username'] == config.get('ADMIN_USERNAME') and check_password_hash(config.get('ADMIN_PASSWORD_HASH'), request.form['password']):
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        
        # Track failed attempt and trigger Discord security alert update
        failed_login_tracker['count'] += 1
        send_discord_security_alert(failed_login_tracker['count'], client_ip)
        flash('Invalid username or password')
    return render_template_string(LOGIN_PAGE)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    config = load_config()
    return render_template_string(ADMIN_DASHBOARD, scripts=config.get('scripts', []))

@app.route('/admin/new', methods=['GET', 'POST'])
def admin_new():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        config = load_config()
        new_script = {
            "id": request.form['id'],
            "title": request.form['title'],
            "category": request.form['category'],
            "description": request.form['description'],
            "tags": request.form['tags'],
            "website": request.form['website'],
            "installCmd": request.form['installCmd'],
            "runsIn": request.form['runsIn'],
            "cpu": request.form['cpu'],
            "ram": request.form['ram'],
            "hdd": request.form['hdd'],
            "user": request.form['user'],
            "credentialsNote": request.form['credentialsNote']
        }
        config['scripts'].append(new_script)
        save_config(config)
        return redirect(url_for('admin_dashboard'))
    return render_template_string(ADMIN_FORM, action="Add", script=None)

@app.route('/admin/edit/<script_id>', methods=['GET', 'POST'])
def admin_edit(script_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    config = load_config()
    script = next((s for s in config['scripts'] if s['id'] == script_id), None)
    if not script:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        script.update({
            "id": request.form['id'],
            "title": request.form['title'],
            "category": request.form['category'],
            "description": request.form['description'],
            "tags": request.form['tags'],
            "website": request.form['website'],
            "installCmd": request.form['installCmd'],
            "runsIn": request.form['runsIn'],
            "cpu": request.form['cpu'],
            "ram": request.form['ram'],
            "hdd": request.form['hdd'],
            "user": request.form['user'],
            "credentialsNote": request.form['credentialsNote']
        })
        save_config(config)
        return redirect(url_for('admin_dashboard'))
    return render_template_string(ADMIN_FORM, action="Edit", script=script)

@app.route('/admin/delete/<script_id>')
def admin_delete(script_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    config = load_config()
    config['scripts'] = [s for s in config['scripts'] if s['id'] != script_id]
    save_config(config)
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)