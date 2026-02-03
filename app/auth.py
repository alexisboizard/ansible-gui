import functools
from flask import session, redirect, url_for, request, jsonify
from ldap3 import Server, Connection, ALL, SUBTREE
from app.models import Setting


def get_ldap_settings():
    """Read LDAP/AD settings from the database."""
    return {
        "server": Setting.get("ldap_server", ""),
        "port": int(Setting.get("ldap_port", "389")),
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
        return False, "", "Serveur LDAP non configuré. Allez dans Paramètres."

    if not username or not password:
        return False, "", "Identifiants requis."

    try:
        server = Server(cfg["server"], port=cfg["port"], use_ssl=cfg["use_ssl"], get_info=ALL)

        # Bind with service account to search for the user
        bind_dn = cfg["bind_dn"]
        bind_password = cfg["bind_password"]

        if bind_dn:
            conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
        else:
            # Try direct bind with UPN (user@domain) or DN
            conn = Connection(server, user=username, password=password, auto_bind=True)

        # Search for the user entry
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

        # If we used a service account, re-bind as the user to validate password
        if bind_dn:
            user_conn = Connection(server, user=user_dn, password=password)
            if not user_conn.bind():
                conn.unbind()
                return False, "", "Mot de passe incorrect."
            user_conn.unbind()

        # Check group membership if required
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
