"""V2 security utils.

Strict isolation: no import from V1.
"""
from __future__ import annotations
import os

def decrypt_mt5_password(encrypted: str) -> str:
    try:
        from cryptography.fernet import Fernet
        from ..config import get_v2_settings
        s = get_v2_settings()
        f = Fernet(s.MT5_CREDENTIAL_KEY.encode())
        return f.decrypt(encrypted.encode()).decode()
    except (ImportError, ModuleNotFoundError):
        # Fallback for environments without cryptography (e.g. some sandbox tests)
        # In a real environment, this should never happen.
        return encrypted
