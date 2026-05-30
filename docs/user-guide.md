# Guide Utilisateur

Ce guide présente toutes les fonctionnalités d'Ansible GUI et comment les utiliser efficacement.

---

## Table des matières

1. [Connexion et authentification](#connexion-et-authentification)
2. [Dashboard](#dashboard)
3. [Inventaire](#inventaire)
4. [Variables](#variables)
5. [Playbooks](#playbooks)
6. [Rôles Ansible](#rôles-ansible)
7. [Dynamic Inventory](#dynamic-inventory)
8. [Exécutions](#exécutions)
9. [Planifications](#planifications)
10. [Paramètres](#paramètres)
11. [Utilisateurs](#utilisateurs)
12. [Audit](#audit)

---

## Connexion et authentification

### Première connexion

Lors de la première installation, un compte administrateur est créé automatiquement :
- **Utilisateur :** `admin`
- **Mot de passe :** `admin`

> ⚠️ **Important :** Changez ce mot de passe immédiatement après la première connexion.

### Modes d'authentification

Ansible GUI supporte deux modes d'authentification :

#### 1. Authentification locale
Les utilisateurs sont créés et gérés directement dans l'application. Les mots de passe sont hashés avec SHA-256 + salt.

#### 2. LDAP / Active Directory
Connexion via un annuaire LDAP ou Active Directory. Les utilisateurs sont automatiquement provisionnés lors de leur première connexion.

Configuration LDAP :
1. Aller dans **Paramètres** > **Authentication**
2. Renseigner le serveur LDAP, Base DN, Bind DN
3. Configurer le filtre utilisateur (ex: `(sAMAccountName={username})`)
4. Tester la connexion avec le bouton **Test LDAP**

### Rôles utilisateur

| Rôle | Permissions |
|------|------------|
| **Admin** | Accès complet : création, modification, suppression, exécution |
| **Read Only** | Consultation uniquement : voir les hôtes, playbooks, exécutions |

---

## Dashboard

Le dashboard offre une vue d'ensemble de votre infrastructure Ansible.

### Statistiques affichées

- **Total Hosts** : Nombre d'hôtes dans l'inventaire
- **Reachable Hosts** : Hôtes joignables (dernier ping réussi)
- **Playbooks** : Nombre de playbooks créés
- **Total Executions** : Historique des exécutions
- **Running / Max** : Exécutions en cours vs limite de concurrence

### Graphiques

- **Execution Trends** : Tendance des exécutions sur 30 jours (succès, échecs, total)
- **Success/Failure Ratio** : Répartition des résultats d'exécution
- **Top 5 Playbooks** : Playbooks les plus exécutés

### Exécutions récentes

Tableau des 5 dernières exécutions avec :
- Nom du playbook
- Statut (success, failed, running)
- Utilisateur ayant déclenché l'exécution
- Date de démarrage

---

## Inventaire

L'inventaire centralise tous vos hôtes cibles Ansible.

### Ajouter un hôte

1. Cliquer sur **Add Host**
2. Remplir les champs :
   - **Name** : Nom d'affichage (ex: `web-server-01`)
   - **Address** : IP ou hostname (ex: `192.168.1.10`)
   - **Groups** : Groupes séparés par virgules (ex: `web, production`)
   - **OS Type** : Linux ou Windows
   - **Username/Password** : Optionnel, override les paramètres globaux
3. Sauvegarder

### Variables d'hôte

Les variables peuvent être définies de deux manières :

1. **Champs dédiés** : Username, Password, Port (pour WinRM)
2. **Extra Variables (JSON)** : Variables Ansible personnalisées

Exemple de variables JSON :
```json
{
  "ansible_become": true,
  "ansible_become_method": "sudo",
  "http_port": 8080
}
```

### Support Windows

Pour les hôtes Windows :
1. Sélectionner **OS Type: Windows**
2. Un champ **WinRM Port** apparaît (défaut: 5985)
3. Les variables WinRM sont auto-injectées :
   - `ansible_connection: winrm`
   - `ansible_winrm_transport: ntlm`
   - `ansible_shell_type: powershell`

### Ping et monitoring

- Cliquer sur **Ping All** pour vérifier la joignabilité de tous les hôtes
- Le statut est affiché par un point coloré :
  - 🟢 Vert : Joignable
  - 🔴 Rouge : Non joignable
  - ⚪ Gris : Jamais testé
- La latence du ping est affichée en millisecondes

### Import/Export CSV

**Export :**
Cliquer sur **Export CSV** pour télécharger tous les hôtes.

**Import :**
1. Préparer un fichier CSV avec les colonnes : `name,address,groups,os_type,variables`
2. Cliquer sur **Import CSV**
3. Sélectionner le fichier

---

## Variables

Cette section permet de gérer les variables de groupe et d'hôte séparément de l'inventaire.

### Group Variables

Variables appliquées à tous les hôtes d'un groupe.

**Exemple :**
- Group: `webservers`
- Variable: `http_port`
- Value: `80`

Ces variables sont ajoutées dans la section `[group:vars]` de l'inventaire Ansible.

### Host Variables

Variables spécifiques à un hôte particulier.

**Exemple :**
- Host: `web-server-01`
- Variable: `max_connections`
- Value: `1000`

Ces variables sont écrites dans des fichiers `host_vars/<hostname>.yml`.

---

## Playbooks

### Organisation en dossiers

Les playbooks peuvent être organisés en dossiers :
1. Cliquer sur **+** dans la barre latérale des dossiers
2. Nommer le dossier
3. Créer des playbooks dans ce dossier ou déplacer des playbooks existants

### Éditeur YAML

L'éditeur intègre :
- **Coloration syntaxique** YAML (thème Dracula)
- **Numéros de ligne**
- **Indentation automatique** (2 espaces)
- **Autocompletion** (`Ctrl+Space`)

### Autocompletion

L'éditeur suggère automatiquement :
- Mots-clés Ansible : `hosts`, `tasks`, `vars`, `handlers`, `roles`, etc.
- Modules courants : `apt`, `copy`, `file`, `service`, `shell`, `debug`, etc.
- Variables Ansible : `ansible_host`, `inventory_hostname`, etc.

L'autocompletion se déclenche :
- Manuellement avec `Ctrl+Space`
- Automatiquement après `:` ou `-`

### Historique des versions

Chaque modification crée une nouvelle version :
1. Cliquer sur l'icône **Historique** d'un playbook
2. Parcourir les versions disponibles
3. Cliquer sur une version pour voir son contenu
4. Cliquer sur **Restore** pour restaurer cette version

### Import/Export

**Export individuel :** Icône de téléchargement → fichier `.yml`

**Export complet :** Bouton **Export ZIP** → archive avec tous les playbooks organisés par dossier

**Import :**
1. Cliquer sur **Import**
2. Sélectionner un fichier `.yml`, `.yaml` ou `.zip`
3. Les playbooks existants avec le même nom sont mis à jour

---

## Rôles Ansible

Gérez les rôles Ansible Galaxy directement depuis l'interface.

### Installer depuis Galaxy

1. Cliquer sur **Install Role**
2. Choisir la source : **Ansible Galaxy** ou **Git**
3. Entrer le nom du rôle (ex: `geerlingguy.docker`)
4. Optionnel : spécifier une version
5. Cliquer sur **Install**

### Rechercher sur Galaxy

1. Cliquer sur **Search Galaxy**
2. Entrer un terme de recherche
3. Parcourir les résultats avec descriptions et nombre de téléchargements
4. Cliquer sur **Install** pour installer directement

### Utiliser un rôle dans un playbook

```yaml
---
- name: Deploy Docker
  hosts: all
  roles:
    - geerlingguy.docker
```

Le chemin des rôles est automatiquement configuré (`ANSIBLE_ROLES_PATH`).

---

## Dynamic Inventory

Utilisez des inventaires dynamiques pour des environnements cloud ou complexes.

### Types d'inventaire

| Type | Description |
|------|-------------|
| **Script** | Script Python exécutable qui retourne du JSON |
| **Plugin** | Fichier YAML de configuration pour les plugins Ansible |

### Templates disponibles

- **AWS EC2** : Plugin pour Amazon EC2
- **Azure** : Plugin pour Azure Resource Manager
- **Python Script** : Exemple de script Python personnalisé

### Créer un inventaire dynamique

1. Cliquer sur **New Dynamic Inventory**
2. Choisir le type (Script ou Plugin)
3. Sélectionner un template ou écrire le code
4. Tester avec le bouton **Test**
5. Sauvegarder

### Exemple de script Python

```python
#!/usr/bin/env python3
import json
import sys

inventory = {
    "webservers": {
        "hosts": ["web1.example.com", "web2.example.com"],
        "vars": {"http_port": 80}
    },
    "_meta": {"hostvars": {}}
}

if "--list" in sys.argv:
    print(json.dumps(inventory))
```

---

## Exécutions

### Lancer un playbook

1. Depuis la page **Playbooks**, cliquer sur l'icône **Run**
2. Configurer l'exécution :
   - **Extra Variables** : Variables supplémentaires (JSON ou `key=value`)
   - **Tags** : Exécuter seulement certains tags
   - **Skip Tags** : Ignorer certains tags
   - **Dry Run** : Mode check (simulation)
3. Cliquer sur **Run Now**

### Suivre l'exécution

- Le statut passe à **running** pendant l'exécution
- La sortie est streamée en temps réel
- Cliquer sur l'icône **terminal** pour voir la sortie complète

### Statuts d'exécution

| Statut | Description |
|--------|-------------|
| `pending` | En attente de démarrage |
| `running` | En cours d'exécution |
| `success` | Terminé avec succès (code retour 0) |
| `failed` | Échec (code retour non-0) |

### Annuler une exécution

Cliquer sur l'icône **X** pour annuler une exécution en cours.

### Limites de concurrence

Un maximum d'exécutions simultanées peut être configuré dans **Paramètres** > **System** > **Max Concurrent Executions**.

---

## Planifications

Automatisez l'exécution de playbooks avec des expressions cron.

### Créer une planification

1. Cliquer sur **New Schedule**
2. Configurer :
   - **Name** : Nom de la planification
   - **Playbook** : Playbook à exécuter
   - **Cron Expression** : Expression cron (ex: `0 2 * * *`)
   - **Host Pattern** : Pattern d'hôtes (défaut: `all`)
   - **Enabled** : Activer/désactiver

### Presets cron

Des boutons de raccourci sont disponibles :
- **Hourly** : `0 * * * *`
- **Daily 2am** : `0 2 * * *`
- **Weekly Sun** : `0 2 * * 0`
- **Monthly** : `0 2 1 * *`
- **Every 15m** : `*/15 * * * *`

### Format cron

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday = 0)
│ │ │ │ │
* * * * *
```

---

## Paramètres

### Authentication (LDAP)

| Paramètre | Description |
|-----------|-------------|
| LDAP Server | Adresse du serveur LDAP |
| LDAP Port | Port (389 ou 636 pour SSL) |
| Base DN | Base de recherche (ex: `dc=example,dc=com`) |
| Bind DN | Compte de service pour la recherche |
| Bind Password | Mot de passe du compte de service |
| User Filter | Filtre LDAP (ex: `(sAMAccountName={username})`) |
| Use SSL | Activer LDAPS |
| Default Role | Rôle par défaut pour les nouveaux utilisateurs LDAP |

### SSH / Connection

| Paramètre | Description |
|-----------|-------------|
| Default SSH User | Utilisateur SSH par défaut |
| Default SSH Password | Mot de passe SSH par défaut |
| SSH Private Key | Clé privée PEM pour l'authentification par clé |

### Ansible Vault

| Paramètre | Description |
|-----------|-------------|
| Vault Password | Mot de passe pour décrypter les variables vault |

### Email Notifications

| Paramètre | Description |
|-----------|-------------|
| SMTP Host | Serveur SMTP |
| SMTP Port | Port (587 pour TLS) |
| SMTP User | Utilisateur SMTP |
| SMTP Password | Mot de passe SMTP |
| From Address | Adresse expéditeur |
| Use TLS | Activer le chiffrement TLS |
| Notify on Failure | Envoyer un email en cas d'échec |
| Notify on Success | Envoyer un email en cas de succès |
| Recipient Emails | Destinataires (séparés par virgules) |

### System

| Paramètre | Description |
|-----------|-------------|
| Ping Interval | Intervalle de ping automatique (secondes) |
| Ping Timeout | Timeout du ping (secondes) |
| Max Concurrent Executions | Limite d'exécutions simultanées |

---

## Utilisateurs

### Créer un utilisateur local

1. Aller dans **Users**
2. Cliquer sur **New User**
3. Renseigner :
   - Username
   - Password
   - Role (Admin ou Read Only)

### Gérer les utilisateurs LDAP

Les utilisateurs LDAP apparaissent après leur première connexion. Vous pouvez :
- Changer leur rôle (Admin ↔ Read Only)
- ⚠️ Impossible de modifier leur mot de passe (géré par LDAP)

### Sécurité

- Le dernier administrateur ne peut pas être supprimé
- Le dernier administrateur ne peut pas être rétrogradé en Read Only

---

## Audit

L'audit log enregistre toutes les actions effectuées dans l'application.

### Événements enregistrés

- Connexions (succès et échecs)
- Création/modification/suppression d'hôtes
- Création/modification/suppression de playbooks
- Exécutions lancées et annulées
- Modifications de planifications
- Changements de paramètres
- Gestion des utilisateurs

### Filtrage

- Par action (ex: `playbook_create`)
- Par utilisateur

### Informations enregistrées

- Date/heure
- Utilisateur
- Type d'action
- Cible (type, ID, nom)
- Détails (JSON)
- Adresse IP

---

## API REST

Toutes les fonctionnalités sont accessibles via API REST.

### Documentation Swagger

Accéder à `/api/docs` pour la documentation interactive Swagger UI.

### Authentification

L'API utilise les sessions. Authentifiez-vous via :
```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' \
  -c cookies.txt
```

Puis utilisez le cookie pour les requêtes suivantes :
```bash
curl http://localhost:5000/api/hosts -b cookies.txt
```

### Health Check

Endpoint sans authentification pour le monitoring :
```bash
curl http://localhost:5000/health
```

---

## Bonnes pratiques

### Sécurité

1. **Changez le mot de passe admin** immédiatement
2. **Utilisez HTTPS** via reverse proxy
3. **Activez LDAP** pour l'authentification centralisée
4. **Limitez les admins** au strict nécessaire
5. **Consultez l'audit log** régulièrement

### Organisation

1. **Utilisez des dossiers** pour organiser les playbooks par projet/environnement
2. **Nommez clairement** les hôtes et les playbooks
3. **Utilisez les groupes** pour cibler facilement des ensembles d'hôtes
4. **Documentez** avec les champs description

### Ansible

1. **Testez en dry run** avant l'exécution réelle
2. **Utilisez les tags** pour des exécutions partielles
3. **Versionnez vos playbooks** (l'historique est automatique)
4. **Utilisez les rôles Galaxy** plutôt que de réinventer la roue
