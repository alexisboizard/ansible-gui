#!/bin/bash
set -e

echo "=== Ansible GUI Installer ==="

# System dependencies
apt-get update
apt-get install -y python3 python3-pip python3-venv python3-lxml \
  libxml2-dev libxslt-dev sshpass ansible

# Create dedicated user
if ! id -u ansible-gui &>/dev/null; then
  useradd -r -m -s /bin/bash ansible-gui
fi

# Install application
APP_DIR=/opt/ansible-gui
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/"
chown -R ansible-gui:ansible-gui "$APP_DIR"

# Python venv
sudo -u ansible-gui python3 -m venv "$APP_DIR/venv"
sudo -u ansible-gui "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u ansible-gui "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# Systemd service
cat > /etc/systemd/system/ansible-gui.service <<EOF
[Unit]
Description=Ansible GUI Web Interface
After=network.target

[Service]
Type=simple
User=ansible-gui
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/gunicorn -w 2 -k gthread --threads 4 -b 0.0.0.0:5000 run:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ansible-gui
systemctl restart ansible-gui

echo ""
echo "=== Ansible GUI installed and started on port 5000 ==="
echo "    Default login: admin / admin"
