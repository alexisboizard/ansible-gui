import logging
from flask import session
from app.models import Setting, LocalUser

log = logging.getLogger(__name__)


def authenticate(username, password):
    """
    Authenticate a user.
    Tries LDAP first (if configured), then falls back to local DB.
    """
    ldap_server = Setting.get("ldap_server", "")

    # Try LDAP first if configured
    if ldap_server and ldap_server.strip():
        ok, user = _ldap_auth(username, password)
        if ok:
            log.info(f"User '{username}' authenticated via LDAP")
            return True, user
        log.debug(f"LDAP auth failed for '{username}', trying local")

    # Fallback to local auth
    ok, user = _local_auth(username, password)
    if ok:
        log.info(f"User '{username}' authenticated via local DB")
    return ok, user


def _local_auth(username, password):
    user = LocalUser.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return True, username
    return False, None


def _ldap_auth(username, password):
    try:
        from ldap3 import Server, Connection, ALL, SIMPLE, SUBTREE
        from ldap3.core.exceptions import LDAPException, LDAPBindError

        server_addr = Setting.get("ldap_server", "")
        port = int(Setting.get("ldap_port", "389") or 389)
        base_dn = Setting.get("ldap_base_dn", "")
        bind_dn = Setting.get("ldap_bind_dn", "")
        bind_pass = Setting.get("ldap_bind_password", "")
        user_filter = Setting.get("ldap_user_filter", "(sAMAccountName={username})")
        use_ssl = Setting.get("ldap_use_ssl", "false").lower() == "true"

        if not server_addr:
            log.debug("LDAP server not configured")
            return False, None

        if not base_dn:
            log.warning("LDAP base DN not configured")
            return False, None

        log.debug(f"LDAP: connecting to {server_addr}:{port} (SSL={use_ssl})")
        server = Server(server_addr, port=port, use_ssl=use_ssl, get_info=ALL)

        # Step 1: Bind with service account to search for user
        if bind_dn and bind_pass:
            log.debug(f"LDAP: binding as service account {bind_dn}")
            try:
                conn = Connection(server, user=bind_dn, password=bind_pass,
                                  authentication=SIMPLE, auto_bind=True)
            except LDAPBindError as e:
                log.error(f"LDAP service account bind failed: {e}")
                return False, None
        else:
            # Anonymous bind for search
            log.debug("LDAP: using anonymous bind for search")
            try:
                conn = Connection(server, auto_bind=True)
            except LDAPException as e:
                log.error(f"LDAP anonymous bind failed: {e}")
                return False, None

        # Step 2: Search for the user
        filt = user_filter.replace("{username}", username)
        log.debug(f"LDAP: searching base='{base_dn}' filter='{filt}'")

        conn.search(base_dn, filt, search_scope=SUBTREE,
                    attributes=["distinguishedName", "cn", "sAMAccountName"])

        if not conn.entries:
            log.debug(f"LDAP: user '{username}' not found")
            conn.unbind()
            return False, None

        user_dn = conn.entries[0].entry_dn
        log.debug(f"LDAP: found user DN: {user_dn}")
        conn.unbind()

        # Step 3: Try to bind as the user with their password
        log.debug(f"LDAP: attempting user bind for {user_dn}")
        try:
            user_conn = Connection(server, user=user_dn, password=password,
                                   authentication=SIMPLE, auto_bind=True)
            if user_conn.bound:
                user_conn.unbind()
                return True, username
        except LDAPBindError:
            log.debug(f"LDAP: password verification failed for '{username}'")
            return False, None

        return False, None

    except ImportError:
        log.error("ldap3 module not installed")
        return False, None
    except Exception as e:
        log.error(f"LDAP authentication error: {e}")
        return False, None


def get_role_for_user(username):
    """Return the role for a username (local DB or LDAP default)."""
    local = LocalUser.query.filter_by(username=username).first()
    if local:
        return local.role or "admin"
    # LDAP user — use configured default role
    from app.models import Setting
    return Setting.get("ldap_default_role", "admin") or "admin"


def login_required(f):
    from functools import wraps
    from flask import redirect, url_for

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("main.login_page"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    from functools import wraps
    from flask import jsonify

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            from flask import redirect, url_for
            return redirect(url_for("main.login_page"))
        if session.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)

    return decorated
