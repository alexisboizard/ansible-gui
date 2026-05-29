#!/bin/bash
set -e

echo "=== Ansible GUI Update ==="

APP_DIR=/opt/ansible-gui

# Step 1: Pull latest code
echo "[1/5] Pulling latest code..."
cd "$APP_DIR"
git pull

# Step 2: System dependencies
echo "[2/5] Updating system dependencies..."
apt-get install -y python3-lxml libxml2-dev libxslt-dev sshpass

# Step 3: Python dependencies
echo "[3/5] Updating Python packages..."
sudo -u ansible-gui "$APP_DIR/venv/bin/pip" install --upgrade -r requirements.txt

# Step 4: Restart service
echo "[4/5] Restarting service..."
systemctl restart ansible-gui

# Step 5: Status check
echo "[5/5] Checking status..."
systemctl status ansible-gui --no-pager

echo ""
echo "=== Update complete ==="
