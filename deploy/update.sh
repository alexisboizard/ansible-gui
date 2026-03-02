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

echo "[1/4] Copie des fichiers..."
rsync -a --exclude='.git' --exclude='venv' --exclude='__pycache__' \
         --exclude='*.pyc' --exclude='.env' \
         "$REPO_DIR/" "$APP_DIR/"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "[2/4] Mise à jour des dépendances Python..."
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "[3/4] Rechargement du service..."
systemctl restart ansible-gui

echo "[4/4] Vérification..."
sleep 2
if systemctl is-active --quiet ansible-gui; then
    echo " ✓ Service actif"
else
    echo " ✗ Erreur - vérifiez : journalctl -u ansible-gui -n 50"
    exit 1
fi

echo ""
echo " ✓ Mise à jour terminée !"
