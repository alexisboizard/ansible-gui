#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Ansible GUI — Script de mise à jour
#  Usage : sudo bash deploy/update.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="/opt/ansible-gui"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="ansible-gui"

echo "==> Mise à jour d'Ansible GUI"

echo "[1/5] Installation des dépendances système..."
apt-get update -q
apt-get install -y -q libxml2-dev libxslt-dev 2>/dev/null || true

echo "[2/5] Copie des fichiers..."
rsync -a --exclude='.git' --exclude='venv' --exclude='__pycache__' \
         --exclude='*.pyc' --exclude='.env' \
         "$REPO_DIR/" "$APP_DIR/"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "[3/5] Mise à jour des dépendances Python..."
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "[4/5] Rechargement du service..."
systemctl restart ansible-gui

echo "[5/5] Vérification..."
sleep 2
if systemctl is-active --quiet ansible-gui; then
    echo " ✓ Service actif"
else
    echo " ✗ Erreur - vérifiez : journalctl -u ansible-gui -n 50"
    exit 1
fi

echo ""
echo " ✓ Mise à jour terminée !"
