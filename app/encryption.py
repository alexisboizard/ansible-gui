"""
Encryption utilities for sensitive settings using Fernet symmetric encryption.
The encryption key is generated on first run and stored in .encryption_key file
or can be provided via ENCRYPTION_KEY environment variable.
"""

import base64
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_fernet = None
_KEY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "instance", ".encryption_key"
)

# Prefix to identify encrypted values
ENCRYPTED_PREFIX = "enc::"


def _get_or_create_key():
    """Get encryption key from env var or file, creating if needed."""
    # Check environment variable first
    env_key = os.environ.get("ENCRYPTION_KEY")
    if env_key:
        try:
            # Validate it's a valid Fernet key
            Fernet(env_key.encode())
            return env_key.encode()
        except Exception:
            logger.warning("Invalid ENCRYPTION_KEY env var, will use file-based key")

    # Ensure instance directory exists
    instance_dir = os.path.dirname(_KEY_FILE)
    os.makedirs(instance_dir, exist_ok=True)

    # Check if key file exists
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            key = f.read().strip()
            try:
                Fernet(key)
                return key
            except Exception:
                logger.warning("Invalid key in file, generating new key")

    # Generate new key
    key = Fernet.generate_key()
    with open(_KEY_FILE, "wb") as f:
        f.write(key)
    os.chmod(_KEY_FILE, 0o600)
    logger.info(f"Generated new encryption key at {_KEY_FILE}")
    return key


def _get_fernet():
    """Get or create Fernet instance."""
    global _fernet
    if _fernet is None:
        key = _get_or_create_key()
        _fernet = Fernet(key)
    return _fernet


def encrypt_value(plaintext):
    """
    Encrypt a plaintext string.
    Returns encrypted string with prefix for identification.
    If already encrypted, returns as-is.
    """
    if not plaintext:
        return plaintext

    # Already encrypted
    if isinstance(plaintext, str) and plaintext.startswith(ENCRYPTED_PREFIX):
        return plaintext

    try:
        f = _get_fernet()
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")
        encrypted = f.encrypt(plaintext)
        return ENCRYPTED_PREFIX + encrypted.decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        # Return original value if encryption fails
        return plaintext


def decrypt_value(ciphertext):
    """
    Decrypt an encrypted string.
    If not encrypted (no prefix), returns as-is.
    """
    if not ciphertext:
        return ciphertext

    # Not encrypted
    if not isinstance(ciphertext, str) or not ciphertext.startswith(ENCRYPTED_PREFIX):
        return ciphertext

    try:
        f = _get_fernet()
        encrypted_data = ciphertext[len(ENCRYPTED_PREFIX) :].encode("utf-8")
        decrypted = f.decrypt(encrypted_data)
        return decrypted.decode("utf-8")
    except InvalidToken:
        logger.error("Decryption failed: invalid token (key may have changed)")
        return ""
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return ""


def is_encrypted(value):
    """Check if a value is already encrypted."""
    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)
