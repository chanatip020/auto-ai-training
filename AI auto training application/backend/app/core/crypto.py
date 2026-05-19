"""Symmetric encryption for stored secrets.

CVAT tokens / passwords are stored encrypted in the DB. We use Fernet
(AES-128-CBC + HMAC-SHA256, 32-byte key) which gives authenticated
symmetric encryption with rotating-key support if we ever need it.

Key comes from `settings.CVAT_ENC_KEY`. Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.core.errors import AppError


@lru_cache(maxsize=1)
def _fernet():
    from cryptography.fernet import Fernet
    key = (settings.CVAT_ENC_KEY or "").strip()
    if not key:
        raise AppError(
            "CVAT_ENC_KEY_NOT_SET",
            (
                "CVAT_ENC_KEY is not set in backend/.env, so storing CVAT credentials "
                "is disabled. Generate a key:\n"
                "  python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"\n"
                "Then add it to backend/.env and restart the api."
            ),
            status_code=500,
        )
    try:
        return Fernet(key.encode())
    except Exception as e:
        raise AppError(
            "CVAT_ENC_KEY_INVALID",
            f"CVAT_ENC_KEY is set but invalid Fernet key: {e}",
            status_code=500,
        )


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except Exception as e:
        raise AppError(
            "DECRYPT_FAILED",
            "Could not decrypt stored secret. Was CVAT_ENC_KEY rotated?",
            500,
            details={"error": str(e)},
        )
