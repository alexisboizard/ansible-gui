# Installation Bare Metal

Ce guide détaille l'installation d'Ansible GUI sur un serveur Linux sans Docker.

## Prérequis

### Système
- Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+, ou équivalent)
- Python 3.9 ou supérieur
- pip (gestionnaire de paquets Python)
- Ansible 2.9+ installé sur le système

### Vérification des prérequis

```bash
# Vérifier Python
python3 --version  # Doit être >= 3.9

# Vérifier pip
pip3 --version

# Vérifier Ansible
ansible --version  # Doit être >= 2.9
```

### Installation des dépendances système

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git ansible
```

**RHEL/CentOS/Rocky:**
```bash
sudo dnf install -y python3 python3-pip git ansible-core
```

**Arch Linux:**
```bash
sudo pacman -S python python-pip git ansible
```

---

## Installation

### 1. Cloner le dépôt

```bash
cd /opt
sudo git clone https://github.com/alexisboizard/ansible-gui.git
sudo chown -R $USER:$USER ansible-gui
cd ansible-gui
```

### 2. Créer l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installer les dépendances Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurer l'environnement

```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer la configuration
nano .env
```

**Contenu minimal de `.env` :**
```bash
# Clé secrète Flask (générer une clé aléatoire)
SECRET_KEY=votre-cle-secrete-tres-longue-et-aleatoire

# Base de données (SQLite par défaut)
DATABASE_URL=sqlite:///instance/ansible_gui.db

# Optionnel: clé de chiffrement pour les credentials
# ENCRYPTION_KEY=  # Généré automatiquement si non défini
```

**Générer une clé secrète :**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Initialiser la base de données

```bash
source venv/bin/activate
python3 -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### 6. Lancer l'application (développement)

```bash
source venv/bin/activate
python run.py
```

L'application est accessible sur `http://localhost:5000`.

---

## Déploiement Production

### Avec Gunicorn

**Installation :**
```bash
pip install gunicorn
```

**Lancement :**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

### Service systemd

Créer le fichier `/etc/systemd/system/ansible-gui.service` :

```ini
[Unit]
Description=Ansible GUI Web Application
After=network.target

[Service]
Type=simple
User=ansible-gui
Group=ansible-gui
WorkingDirectory=/opt/ansible-gui
Environment="PATH=/opt/ansible-gui/venv/bin"
EnvironmentFile=/opt/ansible-gui/.env
ExecStart=/opt/ansible-gui/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Activation du service :**
```bash
# Créer l'utilisateur système
sudo useradd -r -s /bin/false ansible-gui

# Définir les permissions
sudo chown -R ansible-gui:ansible-gui /opt/ansible-gui

# Activer et démarrer le service
sudo systemctl daemon-reload
sudo systemctl enable ansible-gui
sudo systemctl start ansible-gui

# Vérifier le statut
sudo systemctl status ansible-gui
```

### Reverse Proxy Nginx

Créer `/etc/nginx/sites-available/ansible-gui` :

```nginx
server {
    listen 80;
    server_name ansible.example.com;

    # Redirection HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ansible.example.com;

    ssl_certificate /etc/ssl/certs/ansible-gui.crt;
    ssl_certificate_key /etc/ssl/private/ansible-gui.key;

    # Configuration SSL recommandée
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (pour les futures fonctionnalités)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Fichiers statiques (optionnel, améliore les performances)
    location /static {
        alias /opt/ansible-gui/app/static;
        expires 1d;
    }
}
```

**Activation :**
```bash
sudo ln -s /etc/nginx/sites-available/ansible-gui /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## PostgreSQL (Optionnel)

Pour les déploiements à grande échelle, PostgreSQL est recommandé.

### Installation PostgreSQL

```bash
# Ubuntu/Debian
sudo apt install -y postgresql postgresql-contrib

# RHEL/CentOS
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### Création de la base

```bash
sudo -u postgres psql << EOF
CREATE USER ansible_gui WITH PASSWORD 'votre-mot-de-passe';
CREATE DATABASE ansible_gui OWNER ansible_gui;
GRANT ALL PRIVILEGES ON DATABASE ansible_gui TO ansible_gui;
EOF
```

### Configuration

Modifier `.env` :
```bash
DATABASE_URL=postgresql://ansible_gui:votre-mot-de-passe@localhost:5432/ansible_gui
```

---

## Mise à jour

```bash
cd /opt/ansible-gui

# Arrêter le service
sudo systemctl stop ansible-gui

# Mettre à jour le code
git pull origin main

# Activer l'environnement et mettre à jour les dépendances
source venv/bin/activate
pip install -r requirements.txt

# Redémarrer le service
sudo systemctl start ansible-gui
```

---

## Dépannage

### Logs

```bash
# Logs systemd
sudo journalctl -u ansible-gui -f

# Logs applicatifs
tail -f /opt/ansible-gui/logs/app.log
```

### Vérification santé

```bash
curl http://localhost:5000/health
```

### Réinitialiser le mot de passe admin

```bash
cd /opt/ansible-gui
source venv/bin/activate
python3 << EOF
from app import create_app, db
from app.models import LocalUser

app = create_app()
with app.app_context():
    admin = LocalUser.query.filter_by(username='admin').first()
    if admin:
        admin.set_password('nouveau-mot-de-passe')
        db.session.commit()
        print("Mot de passe réinitialisé")
    else:
        print("Utilisateur admin non trouvé")
EOF
```

### Permissions SSH

Si Ansible ne peut pas se connecter aux hôtes :

```bash
# Vérifier que la clé SSH est accessible
ls -la /opt/ansible-gui/instance/.ssh/

# Tester la connexion manuellement
ansible all -i "192.168.1.10," -m ping --private-key=/chemin/vers/cle
```
