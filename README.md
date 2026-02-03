# Ansible GUI

Interface web pour gérer et exécuter des playbooks Ansible.

## Fonctionnalités

- **Inventaire** : gestion CRUD des hôtes (hostname, IP, port, utilisateur, groupe, variables)
- **Playbooks** : éditeur YAML avec coloration syntaxique (CodeMirror), création et modification
- **Exécution** : lancement de playbooks avec choix du pattern d'hôtes, suivi du statut et consultation de la sortie
- **Planification** : exécution automatique via expressions cron (APScheduler)
- **Notifications** : rapport d'exécution envoyé par email (SMTP)

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Python / Flask |
| Base de données | SQLite (SQLAlchemy) |
| Frontend | Bootstrap 5, CodeMirror, JavaScript vanilla |
| Planification | APScheduler |
| Email | Flask-Mail |
| Conteneurisation | Docker |

## Démarrage rapide

### Avec Docker

```bash
cp .env.example .env
# Éditer .env avec vos paramètres SMTP
docker compose up -d
```

L'application est accessible sur `http://localhost:5000`.

### Sans Docker

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Éditer .env

python run.py
```

## Configuration

Toute la configuration se fait via des variables d'environnement (fichier `.env`) :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `SECRET_KEY` | Clé secrète Flask | `change-me-in-production` |
| `DATABASE_URL` | URI SQLAlchemy | `sqlite:///ansible_gui.db` |
| `MAIL_SERVER` | Serveur SMTP | `localhost` |
| `MAIL_PORT` | Port SMTP | `587` |
| `MAIL_USE_TLS` | Activer TLS | `true` |
| `MAIL_USERNAME` | Login SMTP | |
| `MAIL_PASSWORD` | Mot de passe SMTP | |
| `MAIL_DEFAULT_SENDER` | Expéditeur | `ansible-gui@localhost` |
| `NOTIFICATION_EMAIL` | Destinataire par défaut | |

## API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/hosts` | Lister les hôtes |
| POST | `/api/hosts` | Créer un hôte |
| GET | `/api/hosts/:id` | Détail d'un hôte |
| PUT | `/api/hosts/:id` | Modifier un hôte |
| DELETE | `/api/hosts/:id` | Supprimer un hôte |
| GET | `/api/playbooks` | Lister les playbooks |
| POST | `/api/playbooks` | Créer un playbook |
| GET | `/api/playbooks/:id` | Détail d'un playbook |
| PUT | `/api/playbooks/:id` | Modifier un playbook |
| DELETE | `/api/playbooks/:id` | Supprimer un playbook |
| GET | `/api/executions` | Historique des exécutions |
| POST | `/api/executions` | Lancer une exécution |
| GET | `/api/executions/:id` | Détail d'une exécution |
| GET | `/api/schedules` | Lister les planifications |
| POST | `/api/schedules` | Créer une planification |
| PUT | `/api/schedules/:id` | Modifier une planification |
| DELETE | `/api/schedules/:id` | Supprimer une planification |
