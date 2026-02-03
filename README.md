# Ansible GUI

Interface web pour gérer et exécuter des playbooks Ansible.

## Fonctionnalités

- **Authentification AD/LDAP** : connexion via Active Directory, filtrage par groupe, sessions sécurisées
- **Inventaire** : gestion CRUD des hôtes (hostname, IP, port, utilisateur, groupe, variables)
- **Playbooks** : éditeur YAML avec coloration syntaxique (CodeMirror), création et modification
- **Exécution** : lancement de playbooks avec choix du pattern d'hôtes, suivi du statut et consultation de la sortie
- **Planification** : exécution automatique via expressions cron (APScheduler)
- **Notifications** : rapport d'exécution envoyé par email (SMTP)
- **Paramètres** : page de configuration intégrée pour LDAP/AD, SMTP et options générales, avec test de connexion

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Python / Flask |
| Base de données | SQLite (SQLAlchemy) |
| Authentification | LDAP / Active Directory (ldap3) |
| Frontend | Bootstrap 5, CodeMirror, JavaScript vanilla |
| Planification | APScheduler |
| Email | smtplib (config via UI) |
| Conteneurisation | Docker |

## Démarrage rapide

### Avec Docker

```bash
cp .env.example .env
# Éditer .env (SECRET_KEY uniquement)
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

### Variables d'environnement (.env)

| Variable | Description | Défaut |
|----------|-------------|--------|
| `SECRET_KEY` | Clé secrète Flask | `change-me-in-production` |
| `DATABASE_URL` | URI SQLAlchemy | `sqlite:///ansible_gui.db` |

### Paramètres via l'interface web

Tous les paramètres LDAP et SMTP se configurent depuis l'onglet **Paramètres** de l'interface :

**Active Directory / LDAP :**
- Serveur, port, SSL
- Bind DN et mot de passe (compte de service)
- Base de recherche, filtre utilisateur
- Groupe requis (optionnel)

**SMTP :**
- Serveur, port, TLS
- Identifiants
- Expéditeur, destinataire par défaut

Des boutons **Tester la connexion** permettent de valider la configuration avant de l'utiliser.

## API REST

Toutes les routes API nécessitent une authentification (session). Un appel non authentifié retourne `401`.

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/login` | Page de connexion |
| GET | `/logout` | Déconnexion |
| GET | `/api/auth/me` | Utilisateur connecté |
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
| GET | `/api/settings/schema` | Schéma des paramètres |
| GET | `/api/settings` | Lire les paramètres |
| PUT | `/api/settings` | Modifier les paramètres |
| POST | `/api/settings/test-ldap` | Tester la connexion LDAP |
| POST | `/api/settings/test-smtp` | Tester la connexion SMTP |
