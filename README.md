<p align="center">
  <img src="docs/assets/logo.svg" alt="Ansible GUI Logo" width="120">
</p>

<h1 align="center">Ansible GUI</h1>

<p align="center">
  <strong>A modern, self-contained web interface for Ansible automation</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#screenshots">Screenshots</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/flask-3.0+-green.svg" alt="Flask 3.0+">
  <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/ansible-2.9+-red.svg" alt="Ansible 2.9+">
</p>

---

## Why Ansible GUI?

Ansible GUI provides a **complete web-based solution** for managing your Ansible infrastructure without requiring Git, AWX, or complex dependencies. Perfect for teams who want the power of Ansible with an intuitive interface.

- **Self-contained**: No Git server required, internal versioning system
- **Production-ready**: RBAC, audit logging, encrypted credentials, health checks
- **Easy deployment**: Single Docker container or bare metal installation
- **Community-friendly**: Open source, extensible, well-documented

---

## Features

### Core Automation
- **Playbook Management** — Create, edit, organize playbooks in folders with YAML syntax highlighting
- **Smart Editor** — CodeMirror with Ansible autocompletion (Ctrl+Space), module hints, snippets
- **Execution Engine** — Run playbooks with extra variables, tags, check mode (dry run)
- **Scheduling** — Cron-based automation with APScheduler
- **Version History** — Built-in versioning, compare and restore previous versions

### Inventory Management
- **Host Management** — Add hosts with variables, groups, Linux/Windows support
- **Group & Host Variables** — Dedicated variable management per group or host
- **Dynamic Inventory** — Python scripts or Ansible plugins (AWS, Azure, custom)
- **Ping Monitoring** — Auto-check host reachability with latency tracking
- **Import/Export** — CSV and ZIP support for bulk operations

### Ansible Ecosystem
- **Roles from Galaxy** — Search, install, manage roles from Ansible Galaxy
- **Git Roles** — Install roles directly from Git repositories
- **Vault Support** — Decrypt vault-encrypted variables in playbooks
- **Collections Ready** — Use any Ansible collection in your playbooks

### Enterprise Features
- **Authentication** — Local users + LDAP/Active Directory with auto-provisioning
- **RBAC** — Admin and Read-Only roles with per-user management
- **Audit Logging** — Complete traceability of all actions
- **Encrypted Credentials** — Fernet encryption for sensitive data (SSH keys, passwords)
- **Concurrency Control** — Limit simultaneous executions
- **Email Notifications** — SMTP alerts on success/failure

### Operations
- **Dashboard** — Real-time stats, execution trends (Chart.js), top playbooks
- **Health Endpoint** — `/health` for load balancers and monitoring
- **API Documentation** — Swagger UI at `/api/docs`
- **PostgreSQL Support** — Scale beyond SQLite when needed

---

## Quick Start

### Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/alexisboizard/ansible-gui.git
cd ansible-gui

# Start with Docker Compose
docker compose up -d

# Access the interface
open http://localhost:5000
```

Default credentials: `admin` / `admin`

### Bare Metal

```bash
# Clone and setup
git clone https://github.com/alexisboizard/ansible-gui.git
cd ansible-gui

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

See [full installation guide](docs/installation-baremetal.md) for detailed instructions.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Installation (Bare Metal)](docs/installation-baremetal.md) | Complete guide for native installation |
| [Installation (Docker)](docs/installation-docker.md) | Docker and Docker Compose setup |
| [User Guide](docs/user-guide.md) | How to use all features |
| [API Reference](/api/docs) | Swagger documentation (when running) |

---

## Screenshots

<details>
<summary>Dashboard</summary>

The dashboard provides an overview of your infrastructure with execution trends, success rates, and quick access to recent activity.

</details>

<details>
<summary>Playbook Editor</summary>

Edit playbooks with syntax highlighting, autocompletion, and instant execution.

</details>

<details>
<summary>Inventory Management</summary>

Manage hosts, groups, and variables with an intuitive interface.

</details>

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.9+ / Flask 3.0 |
| Database | SQLite (default) or PostgreSQL |
| Authentication | Local + LDAP/AD (ldap3) |
| Frontend | Vanilla JS, Chart.js, CodeMirror |
| Scheduling | APScheduler |
| Encryption | cryptography (Fernet) |
| Container | Docker / Docker Compose |

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `change-me-in-production` |
| `DATABASE_URL` | Database connection string | `sqlite:///instance/ansible_gui.db` |
| `ENCRYPTION_KEY` | Fernet key for credentials | Auto-generated |

### Settings via Web UI

All operational settings are configurable through the Settings page:

- **Authentication**: LDAP server, bind credentials, user filter
- **SSH**: Default user, password, private key
- **Vault**: Ansible Vault password
- **Notifications**: SMTP server, recipients, triggers
- **System**: Ping interval, concurrency limits

---

## API

Full REST API with Swagger documentation available at `/api/docs`.

```bash
# Example: List all hosts
curl -X GET http://localhost:5000/api/hosts \
  -H "Cookie: session=..."

# Example: Execute a playbook
curl -X POST http://localhost:5000/api/executions \
  -H "Content-Type: application/json" \
  -d '{"playbook_id": 1, "check_mode": false}'
```

Health check endpoint (no auth required):
```bash
curl http://localhost:5000/health
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [Ansible](https://www.ansible.com/) — The automation platform
- [Flask](https://flask.palletsprojects.com/) — The web framework
- [CodeMirror](https://codemirror.net/) — The code editor
- [Chart.js](https://www.chartjs.org/) — The charting library

---

<p align="center">
  Made with ❤️ for the Ansible community
</p>
