# Playbook Masterisation Debian 13

Playbook Ansible pour la masterisation de VMs Debian 13 (Trixie).

## Rôles inclus

| Rôle | Description |
|------|-------------|
| `common` | Outils système de base (vim, btop, jq, tcpdump...) |
| `ssh` | Configuration SSH sécurisée (port 1822) |
| `firewall` | UFW avec règles de base |
| `fail2ban` | Protection brute force SSH |
| `centreon` | Agent SNMP pour supervision |
| `updates` | Mises à jour automatiques |

## Prérequis

- Ansible >= 2.14
- Collection `community.general`

```bash
ansible-galaxy collection install community.general
```

## Variables principales

| Variable | Défaut | Description |
|----------|--------|-------------|
| `ssh_port` | 1822 | Port SSH |
| `centreon_poller_ip` | 10.0.0.100 | IP du poller Centreon |
| `snmp_community` | public | Communauté SNMP |
| `fail2ban_bantime` | 3600 | Durée de bannissement (sec) |
| `fail2ban_maxretry` | 3 | Tentatives avant ban |

## Utilisation

### 1. Configurer l'inventaire

```ini
[debian_vms]
vm1.example.com
vm2.example.com

[debian_vms:vars]
ansible_user=root
centreon_poller=10.0.0.100
```

### 2. Exécuter le playbook

```bash
ansible-playbook -i inventory.ini site.yml
```

### 3. Mode check (dry-run)

```bash
ansible-playbook -i inventory.ini site.yml --check --diff
```

### 4. Exécuter un rôle spécifique

```bash
ansible-playbook -i inventory.ini site.yml --tags ssh
```

## Après masterisation

Mettre à jour l'inventaire pour utiliser le nouveau port SSH :

```ini
[debian_vms:vars]
ansible_port=1822
```

## Structure

```
.
├── site.yml              # Playbook principal
├── inventory.ini         # Inventaire exemple
└── roles/
    ├── common/           # Outils de base
    ├── ssh/              # Configuration SSH
    ├── firewall/         # UFW
    ├── fail2ban/         # Protection brute force
    ├── centreon/         # Supervision SNMP
    └── updates/          # Mises à jour auto
```

## Personnalisation

Créer un fichier `group_vars/all.yml` :

```yaml
ssh_port: 1822
centreon_poller_ip: "192.168.1.50"
snmp_community: "mysecretcommunity"
fail2ban_bantime: 7200
unattended_automatic_reboot: true
unattended_mail: "admin@example.com"
```
