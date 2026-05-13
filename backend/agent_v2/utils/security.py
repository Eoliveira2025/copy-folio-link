"""V2 security utils.

Strict isolation: no import from V1.
"""
from __future__ import annotations
from cryptography.fernet import Fernet
from ..config import get_v2_settings

def decrypt_mt5_password(encrypted: str) -> str:
    s = get_v2_settings()
    f = Fernet(s.MT5_CREDENTIAL_KEY.encode())
    return f.decrypt(encrypted.encode()).decode()
