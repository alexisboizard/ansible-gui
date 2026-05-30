# Installation Docker

Ce guide détaille le déploiement d'Ansible GUI avec Docker et Docker Compose.

## Prérequis

- Docker 20.10+ 
- Docker Compose v2.0+ (ou docker-compose v1.29+)
- 1 GB RAM minimum
- 10 GB espace disque

### Vérification

```bash
docker --version      # Docker version 20.10+
docker compose version  # Docker Compose version v2.0+
```

---

## Démarrage rapide

### 1. Cloner le dépôt

```bash
git clone https://github.com/alexisboizard/ansible-gui.git
cd ansible-gui
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
nano .env
```

**Configuration minimale :**
```bash
SECRET_KEY=votre-cle-secrete-aleatoire-de-32-caracteres-minimum
```

### 3. Lancer l'application

```bash
docker compose up -d
```

### 4. Accéder à l'interface

Ouvrir `http://localhost:5000` dans votre navigateur.

**Identifiants par défaut :** `admin` / `admin`

---

## Configuration avancée

### docker-compose.yml (SQLite)

Configuration par défaut avec SQLite :

```yaml
version: '3.8'

services:
  ansible-gui:
    build: .
    container_name: ansible-gui
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
    volumes:
      # Persistence des données
      - ./instance:/app/instance
      # Clés SSH (optionnel)
      - ./ssh-keys:/app/ssh-keys:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### docker-compose.yml (PostgreSQL)

Configuration production avec PostgreSQL :

```yaml
version: '3.8'

services:
  ansible-gui:
    build: .
    container_name: ansible-gui
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql://ansible:${DB_PASSWORD}@db:5432/ansible_gui
    volumes:
      - ./instance:/app/instance
      - ./ssh-keys:/app/ssh-keys:ro
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15-alpine
    container_name: ansible-gui-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=ansible
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=ansible_gui
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ansible -d ansible_gui"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

**.env pour PostgreSQL :**
```bash
SECRET_KEY=votre-cle-secrete-longue
DB_PASSWORD=mot-de-passe-postgres-securise
```

---

## Volumes et persistance

| Volume | Description |
|--------|-------------|
| `./instance` | Base SQLite, clé de chiffrement, rôles installés |
| `./ssh-keys` | Clés SSH privées (montées en lecture seule) |
| `pgdata` | Données PostgreSQL (si utilisé) |

### Structure du dossier instance

```
instance/
├── ansible_gui.db      # Base SQLite
├── .encryption_key     # Clé Fernet (générée auto)
└── roles/              # Rôles Ansible Galaxy installés
```

---

## Reverse Proxy

### Traefik

```yaml
version: '3.8'

services:
  ansible-gui:
    build: .
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ansible.rule=Host(`ansible.example.com`)"
      - "traefik.http.routers.ansible.entrypoints=websecure"
      - "traefik.http.routers.ansible.tls.certresolver=letsencrypt"
      - "traefik.http.services.ansible.loadbalancer.server.port=5000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
    volumes:
      - ./instance:/app/instance
    networks:
      - traefik

networks:
  traefik:
    external: true
```

### Nginx Proxy Manager

Utiliser les paramètres suivants :
- **Scheme:** http
- **Forward Hostname:** ansible-gui
- **Forward Port:** 5000
- **Block Common Exploits:** Activé
- **Websockets Support:** Activé

---

## Commandes utiles

### Gestion du conteneur

```bash
# Démarrer
docker compose up -d

# Arrêter
docker compose down

# Redémarrer
docker compose restart

# Voir les logs
docker compose logs -f

# Logs d'un service spécifique
docker compose logs -f ansible-gui
```

### Maintenance

```bash
# Accéder au shell du conteneur
docker compose exec ansible-gui /bin/bash

# Backup de la base SQLite
docker compose exec ansible-gui cp /app/instance/ansible_gui.db /app/instance/backup.db
docker cp ansible-gui:/app/instance/backup.db ./backup.db

# Mise à jour
git pull
docker compose build
docker compose up -d
```

### Réinitialisation

```bash
# Supprimer tout et repartir de zéro
docker compose down -v
rm -rf instance/*
docker compose up -d
```

---

## Monitoring

### Health check

```bash
# Vérifier la santé du conteneur
docker inspect ansible-gui --format='{{.State.Health.Status}}'

# Endpoint de santé
curl http://localhost:5000/health
```

**Réponse attendue :**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "scheduler": "running"
}
```

### Intégration Prometheus (optionnel)

Créer un job Prometheus pour le health check :

```yaml
scrape_configs:
  - job_name: 'ansible-gui'
    static_configs:
      - targets: ['ansible-gui:5000']
    metrics_path: /health
    scrape_interval: 30s
```

---

## Mise à jour

### Mise à jour standard

```bash
cd ansible-gui
git pull
docker compose build --no-cache
docker compose up -d
```

### Mise à jour avec migration

Si une migration de base est nécessaire :

```bash
# Backup avant mise à jour
docker compose exec ansible-gui cp /app/instance/ansible_gui.db /app/instance/pre-update-backup.db

# Mise à jour
git pull
docker compose build --no-cache
docker compose up -d

# Vérifier que tout fonctionne
curl http://localhost:5000/health
```

---

## Dépannage

### Le conteneur ne démarre pas

```bash
# Vérifier les logs
docker compose logs ansible-gui

# Causes fréquentes :
# - SECRET_KEY manquant dans .env
# - Port 5000 déjà utilisé
# - Permissions sur les volumes
```

### Problèmes de connexion aux hôtes

```bash
# Vérifier que les clés SSH sont montées
docker compose exec ansible-gui ls -la /app/ssh-keys/

# Tester Ansible directement
docker compose exec ansible-gui ansible all -i "192.168.1.10," -m ping
```

### Base de données corrompue

```bash
# Restaurer depuis le backup
docker compose exec ansible-gui cp /app/instance/backup.db /app/instance/ansible_gui.db
docker compose restart
```

### Réinitialiser le mot de passe admin

```bash
docker compose exec ansible-gui python3 << EOF
from app import create_app, db
from app.models import LocalUser

app = create_app()
with app.app_context():
    admin = LocalUser.query.filter_by(username='admin').first()
    if admin:
        admin.set_password('nouveau-mot-de-passe')
        db.session.commit()
        print("Mot de passe réinitialisé")
EOF
```

---

## Sécurité

### Recommandations

1. **Changer les identifiants par défaut** immédiatement après installation
2. **Utiliser HTTPS** via reverse proxy (Traefik, Nginx)
3. **Restreindre l'accès réseau** avec des règles firewall
4. **Sauvegarder régulièrement** le dossier `instance/`
5. **Mettre à jour** régulièrement l'image Docker

### Variables sensibles

Ne jamais commiter le fichier `.env` contenant :
- `SECRET_KEY`
- `DB_PASSWORD`
- `ENCRYPTION_KEY`

Utiliser des secrets Docker en production :

```yaml
services:
  ansible-gui:
    secrets:
      - secret_key
      - db_password

secrets:
  secret_key:
    file: ./secrets/secret_key.txt
  db_password:
    file: ./secrets/db_password.txt
```
