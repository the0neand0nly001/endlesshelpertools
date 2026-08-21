#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -Eeuo pipefail

# --- STYLING & COLORS (Matching Proxmox Helper Scripts) ---
YW=$(echo "\033[33m")
BL=$(echo "\033[36m")
RD=$(echo "\033[01;31m")
GN=$(echo "\033[1;92m")
CL=$(echo "\033[m")
CM="${GN}✓${CL}"
HOLD=" "

msg_info() {
    local msg="$1"
    echo -ne " ${HOLD} ${YW}${msg} "
}

msg_ok() {
    local msg="$1"
    echo -e "\r\033[K ${CM} ${GN}${msg}${CL}"
}
# ---------------------------------------------------------

APP_DIR="/opt/pve-scripts"
REPO_URL="https://github.com/the0neand0nly001/endlesshelpertools.git"

msg_info("Updating system packages...")
apt update &>/dev/null && apt upgrade -y &>/dev/null
msg_ok("System packages updated")

msg_info("Installing required dependencies (Python, Git)...")
apt install -y python3 python3-pip python3-venv git &>/dev/null
msg_ok("Dependencies installed")

msg_info("Setting up application directory...")
if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR" &>/dev/null
else
    cd "$APP_DIR"
    git pull &>/dev/null
fi
msg_ok("Application directory configured")

msg_info("Installing Python packages (Flask, PyYAML)...")
pip3 install --break-system-packages Flask PyYAML &>/dev/null
msg_ok("Python packages installed")

msg_info("Configuring Systemd service...")
SERVICE_FILE="/etc/systemd/system/pve-scripts.service"
cat > "$SERVICE_FILE" <<EOF
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
systemctl daemon-reload &>/dev/null
systemctl enable pve-scripts.service &>/dev/null
systemctl restart pve-scripts.service &>/dev/null
msg_ok("Systemd service started")

# Get the host's primary IP address cleanly
IP_ADDR=$(hostname -I | awk '{print $1}')

echo -e "\n${GN}Setup completed successfully!${CL}"
echo -e "Access your Script Manager web UI at: ${BL}http://${IP_ADDR}:8080${CL}\n"