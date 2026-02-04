import functools
import hashlib
import secrets
from flask import session, redirect, url_for, request, jsonify
from ldap3 import Server, Connection, ALL, SUBTREE
from app.models import Setting


# ──────────────────────────────────────────────
# Local admin account
# ──────────────────────────────────────────────
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"


def _hash_password(password, salt=None):
    """Hash a password with SHA-256 + salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"


def _verify_password(password, stored):
    """Verify a password against a stored salt$hash."""
    if "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return _hash_password(password, salt) == stored


def authenticate_local(username, password):
    """Authenticate against the local admin account.

    Returns (success: bool, display_name: str, error: str).
    """
    admin_user = Setting.get("admin_username", DEFAULT_ADMIN_USER)
    admin_hash = Setting.get("admin_password_hash", "")

    if username != admin_user:
        return False, "", ""  # Empty error = not a local user, try LDAP

    if not admin_hash:
        # First run: accept default password
        if password == DEFAULT_ADMIN_PASSWORD:
            # Store the hash so the default is only valid once if changed
            Setting.set("admin_password_hash", _hash_password(DEFAULT_ADMIN_PASSWORD), "admin")
            Setting.set("admin_username", DEFAULT_ADMIN_USER, "admin")
            return True, "Administrateur", ""
        return False, "", "Mot de passe incorrect."

    if _verify_password(password, admin_hash):
        return True, "Administrateur", ""

    return False, "", "Mot de passe incorrect."


def change_admin_password(current_password, new_password):
    """Change the local admin password.

    Returns (success: bool, error: str).
    """
    admin_hash = Setting.get("admin_password_hash", "")

    if not admin_hash:
        # First setup — accept default
        if current_password != DEFAULT_ADMIN_PASSWORD:
            return False, "Mot de passe actuel incorrect."
    else:
        if not _verify_password(current_password, admin_hash):
            return False, "Mot de passe actuel incorrect."

    if len(new_password) < 6:
        return False, "Le nouveau mot de passe doit faire au moins 6 caractères."

    Setting.set("admin_password_hash", _hash_password(new_password), "admin")
    return True, ""


# ──────────────────────────────────────────────
# LDAP / Active Directory
# ──────────────────────────────────────────────
def get_ldap_settings():
    """Read LDAP/AD settings from the database."""
    return {
        "server": Setting.get("ldap_server", ""),
        "port": int(Setting.get("ldap_port", "389") or 389),
        "use_ssl": Setting.get("ldap_use_ssl", "false").lower() == "true",
        "bind_dn": Setting.get("ldap_bind_dn", ""),
        "bind_password": Setting.get("ldap_bind_password", ""),
        "search_base": Setting.get("ldap_search_base", ""),
        "user_filter": Setting.get("ldap_user_filter", "(sAMAccountName={username})"),
        "require_group": Setting.get("ldap_require_group", ""),
        "group_attribute": Setting.get("ldap_group_attribute", "memberOf"),
    }


def authenticate_ldap(username, password):
    """Authenticate a user against Active Directory / LDAP.

    Returns (success: bool, display_name: str, error: str).
    """
    cfg = get_ldap_settings()

    if not cfg["server"]:
        return False, "", "Serveur LDAP non configuré."

    if not username or not password:
        return False, "", "Identifiants requis."

    try:
        server = Server(cfg["server"], port=cfg["port"], use_ssl=cfg["use_ssl"], get_info=ALL)

        bind_dn = cfg["bind_dn"]
        bind_password = cfg["bind_password"]

        if bind_dn:
            conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
        else:
            conn = Connection(server, user=username, password=password, auto_bind=True)

        search_base = cfg["search_base"]
        user_filter = cfg["user_filter"].replace("{username}", username)

        conn.search(
            search_base=search_base,
            search_filter=user_filter,
            search_scope=SUBTREE,
            attributes=["cn", "displayName", "mail", cfg["group_attribute"]],
        )

        if not conn.entries:
            conn.unbind()
            return False, "", "Utilisateur introuvable dans l'annuaire."

        user_entry = conn.entries[0]
        user_dn = str(user_entry.entry_dn)

        if bind_dn:
            user_conn = Connection(server, user=user_dn, password=password)
            if not user_conn.bind():
                conn.unbind()
                return False, "", "Mot de passe incorrect."
            user_conn.unbind()

        require_group = cfg["require_group"]
        if require_group:
            group_attr = cfg["group_attribute"]
            groups = user_entry[group_attr].values if group_attr in user_entry else []
            group_dns = [str(g).lower() for g in groups]
            if not any(require_group.lower() in g for g in group_dns):
                conn.unbind()
                return False, "", "Vous n'êtes pas membre du groupe autorisé."

        display_name = ""
        if "displayName" in user_entry:
            display_name = str(user_entry["displayName"])
        elif "cn" in user_entry:
            display_name = str(user_entry["cn"])
        else:
            display_name = username

        conn.unbind()
        return True, display_name, ""

    except Exception as e:
        return False, "", f"Erreur LDAP : {str(e)}"


# ──────────────────────────────────────────────
# Combined authentication (local first, then LDAP)
# ──────────────────────────────────────────────
def authenticate(username, password):
    """Try local admin auth first, then LDAP.

    Returns (success: bool, display_name: str, error: str).
    """
    if not username or not password:
        return False, "", "Identifiants requis."

    # Try local admin
    success, display_name, error = authenticate_local(username, password)
    if success:
        return True, display_name, ""
    if error:
        # Username matched admin but password was wrong
        return False, "", error

    # Try LDAP (only if server is configured)
    ldap_cfg = get_ldap_settings()
    if ldap_cfg["server"]:
        return authenticate_ldap(username, password)

    return False, "", "LDAP non configuré. Connectez-vous avec le compte admin local."


# ──────────────────────────────────────────────
# Route protection
# ──────────────────────────────────────────────
def login_required(f):
    """Decorator to require authentication on routes."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("authenticated"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Authentification requise"}), 401
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated_function
