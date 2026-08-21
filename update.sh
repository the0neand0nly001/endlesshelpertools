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

if [ ! -d "$APP_DIR" ]; then
    echo -e "${RD}Error: Application directory $APP_DIR does not exist! Run setup.sh first.${CL}"
    exit 1
fi

msg_info "Navigating to application directory..."
cd "$APP_DIR"
msg_ok "In application directory"

msg_info "Pulling latest updates from GitHub..."
# Ensure local config.yml is ignored/preserved during git operations
git fetch origin main &>/dev/null
git reset --hard origin/main &>/dev/null
msg_ok "Repository updated to latest version"

# Ensure config.yml exists (falls back to example if somehow missing, but keeps existing one safe)
if [ ! -f "config.yml" ] && [ -f "config.example.yml" ]; then
    cp config.example.yml config.yml
fi

msg_info "Restarting Systemd service..."
systemctl restart pve-scripts.service &>/dev/null
msg_ok "Systemd service restarted"

echo -e "\n${GN}Update completed successfully! Your config.yml was preserved.${CL}\n"