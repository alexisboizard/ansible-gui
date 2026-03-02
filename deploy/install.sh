#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Ansible GUI — Script d'installation production
#  Usage : sudo bash deploy/install.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="/opt/ansible-gui"
DATA_DIR="/var/lib/ansible-gui"
LOG_DIR="/var/log/ansible-gui"
APP_USER="ansible-gui"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Installation d'Ansible GUI"
echo "    Source : $REPO_DIR"
echo "    Cible  : $APP_DIR"

# ── 1. Dépendances système ────────────────────────────────────
echo ""
echo "[1/7] Installation des dépendances système..."
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv openssh-client sshpass ansible

# ── 2. Utilisateur dédié ─────────────────────────────────────
echo ""
echo "[2/7] Création de l'utilisateur $APP_USER..."
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
    echo "      Utilisateur créé."
else
    echo "      Utilisateur déjà existant, ignoré."
fi

# ── 3. Copie des fichiers ─────────────────────────────────────
echo ""
echo "[3/7] Déploiement des fichiers..."
mkdir -p "$APP_DIR"
rsync -a --exclude='.git' --exclude='venv' --exclude='__pycache__' \
         --exclude='*.pyc' --exclude='.env' \
         "$REPO_DIR/" "$APP_DIR/"

# ── 4. Environnement Python ───────────────────────────────────
echo ""
echo "[4/7] Création du virtualenv..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ── 5. Répertoires de données et logs ────────────────────────
echo ""
echo "[5/7] Création des répertoires..."
mkdir -p "$DATA_DIR" "$LOG_DIR"
chown -R "$APP_USER:$APP_USER" "$DATA_DIR" "$LOG_DIR" "$APP_DIR"

# ── 6. Fichier .env ───────────────────────────────────────────
echo ""
echo "[6/7] Configuration de l'environnement..."
if [ ! -f "$APP_DIR/.env" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > "$APP_DIR/.env" <<EOF
SECRET_KEY=$SECRET_KEY
DATABASE_URL=sqlite:///$DATA_DIR/ansible_gui.db
ANSIBLE_WORK_DIR=$DATA_DIR
EOF
    chmod 640 "$APP_DIR/.env"
    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    echo "      Fichier .env créé avec une SECRET_KEY générée automatiquement."
else
    echo "      Fichier .env déjà existant, conservé."
fi

# ── 7. Service systemd ────────────────────────────────────────
echo ""
echo "[7/7] Installation du service systemd..."
cp "$APP_DIR/deploy/ansible-gui.service" /etc/systemd/system/ansible-gui.service
systemctl daemon-reload
systemctl enable ansible-gui
systemctl restart ansible-gui

# ── Résumé ────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────"
echo " ✓ Ansible GUI déployé avec succès !"
echo "────────────────────────────────────────────"
echo ""
echo "  Service  : systemctl status ansible-gui"
echo "  Logs     : journalctl -u ansible-gui -f"
echo "  App      : http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "  Connexion par défaut : admin / admin"
echo "  → Changez le mot de passe dès la première connexion !"
echo ""
