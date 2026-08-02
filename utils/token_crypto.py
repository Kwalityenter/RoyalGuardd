"""utils/token_crypto.py — Encrypts/decrypts tenant bot tokens at rest."""

import os
from cryptography.fernet import Fernet, InvalidToken

_key = os.getenv("TENANT_ENCRYPTION_KEY")
if not _key:
    raise RuntimeError(
        "TENANT_ENCRYPTION_KEY is not set. Generate one with: "
        "python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

_fernet = Fernet(_key.encode() if isinstance(_key, str) else _key)


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    try:
        return _fernet.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise ValueError("Could not decrypt token — key mismatch or corrupted record.")
