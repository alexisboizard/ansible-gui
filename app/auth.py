from flask import session
from app.models import Setting, LocalUser


def authenticate(username, password):
    """Authenticate a user via local DB or LDAP depending on settings."""
    mode = Setting.get("auth_mode", "local")

    if mode == "ldap":
        return _ldap_auth(username, password)
    else:
        return _local_auth(username, password)


def _local_auth(username, password):
    user = LocalUser.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return True, username
    return False, None


def _ldap_auth(username, password):
    try:
        from ldap3 import Server, Connection, ALL, NTLM
        server_addr = Setting.get("ldap_server", "")
        port = int(Setting.get("ldap_port", "389") or 389)
        base_dn = Setting.get("ldap_base_dn", "")
        bind_dn = Setting.get("ldap_bind_dn", "")
        bind_pass = Setting.get("ldap_bind_password", "")
        user_filter = Setting.get("ldap_user_filter", "(sAMAccountName={username})")
        use_ssl = Setting.get("ldap_use_ssl", "false").lower() == "true"

        if not server_addr:
            return False, None

        server = Server(server_addr, port=port, use_ssl=use_ssl, get_info=ALL)

        # Bind with service account to search
        conn = Connection(server, user=bind_dn, password=bind_pass, auto_bind=True)
        filt = user_filter.replace("{username}", username)
        conn.search(base_dn, filt, attributes=["distinguishedName", "cn"])

        if not conn.entries:
            return False, None

        user_dn = conn.entries[0].entry_dn

        # Try to bind as the user
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        if user_conn.bound:
            return True, username

        return False, None
    except Exception:
        return False, None


def login_required(f):
    from functools import wraps
    from flask import redirect, url_for, request

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("main.login_page"))
        return f(*args, **kwargs)

    return decorated
