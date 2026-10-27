"""
Password hashing and verification using Argon2id.
Never store plain passwords. Never use simple SHA-256 for passwords.
"""
from typing import Optional
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password securely with Argon2id."""
    if not password or not isinstance(password, str):
        raise ValueError("Password is required")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    if not plain_password or not password_hash:
        return False
    try:
        return pwd_context.verify(plain_password, password_hash)
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Check if hash needs rehashing."""
    try:
        return pwd_context.needs_update(password_hash)
    except Exception:
        return False
