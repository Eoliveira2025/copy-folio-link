"""
Credential Vault — encrypts/decrypts MT5 passwords using Fernet (AES-128-CBC).

Passwords are stored encrypted in the database and only decrypted in-memory
within the Terminal Manager process when spawning a new MT5 connection.
"""

from __future__ import annotations
import logging
from cryptography.fernet import Fernet, InvalidToken
from mt5_manager.config import get_manager_settings

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.vault")

_fernet = Fernet(settings.MT5_CREDENTIAL_KEY.encode())


def encrypt_password(password: str) -> str:
    """Encrypt an MT5 password for database storage."""
    return _fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Decrypt an MT5 password from database storage."""
    try:
        return _fernet.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt MT5 password — invalid key or corrupted data")
        raise ValueError("Cannot decrypt MT5 credentials")
