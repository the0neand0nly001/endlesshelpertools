#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -Eeuo pipefail

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo bash setup.sh)"
  exit 1
fi

echo "=================================================="
echo "🚀 Endless Helper Tools Installer"
echo "=================================================="

# Check and install whiptail if missing
if ! dpkg -s whiptail >/dev/null 2>&1; then
    apt-get update >/dev/null 2>&1 && apt-get install -y whiptail >/dev/null 2>&1
fi

# Direct input prompts with pre-filled default values (No "defaults" yes/no box)
ADMIN_USER=$(whiptail --title "Admin Username" --inputbox "Enter admin username:" 10 60 "admin" 3>&1 1>&2 2>&3)
[ -z "$ADMIN_USER" ] && ADMIN_USER="admin"

ADMIN_PASS=$(whiptail --title "Admin Password" --passwordbox "Enter admin password:" 10 60 3>&1 1>&2 2>&3)
[ -z "$ADMIN_PASS" ] && ADMIN_PASS="admin"

DISCORD_WEBHOOK_URL=""
if (whiptail --title "Discord Webhook Alert" --yesno "Would you like to link a Discord webhook for failed login alerts?" 10 60); then
    DISCORD_WEBHOOK_URL=$(whiptail --title "Discord Webhook" --inputbox "Enter your Discord Webhook URL:" 10 60 3>&1 1>&2 2>&3)
fi

if !(whiptail --title "Ready to Install" --yesno "Proceed with installing Endless Helper Tools?" 10 60); then
    echo "Installation aborted."
    exit 0
fi

clear

APP_DIR="/opt/pve-scripts"
REPO_URL="https://github.com/the0neand0nly001/endlesshelpertools.git"

echo "[EndlessTools] 📦 Updating system packages..."
apt-get update &>/dev/null && apt-get upgrade -y &>/dev/null

echo "[EndlessTools] 🐍 Installing required dependencies (Python, Git)..."
apt-get install -y python3 python3-pip python3-venv git python3-requests &>/dev/null

echo "[EndlessTools] 📁 Setting up application directory..."
if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR" &>/dev/null
else
    cd "$APP_DIR"
    git pull &>/dev/null
fi

echo "[EndlessTools] 📦 Installing Python packages (Flask, PyYAML, Requests)..."
pip3 install --break-system-packages Flask PyYAML requests &>/dev/null

echo "[EndlessTools] ⚙️ Configuring admin credentials and security webhook..."
cd "$APP_DIR"
cat << 'PY_EOF' > make_config.py
import sys
import yaml
from werkzeug.security import generate_password_hash

user = sys.argv[1]
password = sys.argv[2]
webhook = sys.argv[3] if len(sys.argv) > 3 else ""

config = {
    'ADMIN_USERNAME': user,
    'ADMIN_PASSWORD_HASH': generate_password_hash(password),
    'DISCORD_WEBHOOK_URL': webhook,
    'scripts': [
        {
            'id': 'caddy-manager',
            'title': 'Caddy Manager',
            'category': 'Reverse Proxy',
            'description': 'A lightweight web interface for Caddy.',
            'tags': 'LXC,Proxy',
            'website': 'https://github.com/theoneandonly001/caddymanager',
            'installCmd': 'bash -c "$(wget -qLO - https://raw.githubusercontent.com/theoneandonly001/caddymanager/stable/ct/caddy-manager.sh)"',
            'runsIn': 'LXC',
            'cpu': '1 Core',
            'ram': '1024 MB',
            'hdd': '4 GB',
            'user': 'admin',
            'credentialsNote': 'Default setup, Port 5000'
        }
    ]
}

with open('config.yml', 'w') as f:
    yaml.dump(config, f)
PY_EOF

python3 make_config.py "$ADMIN_USER" "$ADMIN_PASS" "$DISCORD_WEBHOOK_URL"
rm -f make_config.py

echo "[EndlessTools] 🔌 Configuring systemd service..."
SERVICE_FILE="/etc/systemd/system/pve-scripts.service"
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Proxmox Custom Script Manager
After=network.target

[Service]
User=root
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload >/dev/null 2>&1
systemctl enable pve-scripts.service >/dev/null 2>&1
systemctl restart pve-scripts.service >/dev/null 2>&1

IP_ADDR=$(hostname -I | awk '{print $1}')

echo "=================================================="
echo "✔ Installation Complete! Script Manager is running."
echo "✔ Access it at: http://${IP_ADDR}:8080"
echo "=================================================="