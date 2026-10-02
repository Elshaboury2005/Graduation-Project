"""
app/core/security.py
--------------------
Reusable security utilities: JWT token handling and password hashing.

Auth *routes* are intentionally absent here — they belong to a later phase.
Only the pure helper functions are provided so other modules can import them
without pulling in routing concerns.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# ── Password hashing ───────────────────────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Return a bcrypt hash of *plain_password*.

    The resulting string is safe to store in the database.
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify *plain_password* against a stored *hashed_password*.

    Returns True when the passwords match, False otherwise.
    """
    return _pwd_context.verify(plain_password, hashed_password)


# ── JWT ────────────────────────────────────────────────────────────────────────

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.

    Parameters
    ----------
    data:
        Arbitrary claims to embed in the token payload.  A ``sub`` key
        containing the subject (e.g. user UUID) is conventional.
    expires_delta:
        How long until the token expires.  Defaults to the value of
        ``JWT_EXPIRE_MINUTES`` from settings.

    Returns
    -------
    str
        Encoded, signed JWT string.
    """
    settings = get_settings()
    payload = data.copy()
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Parameters
    ----------
    token:
        The raw JWT string (without the ``Bearer `` prefix).

    Returns
    -------
    dict
        The decoded token payload.

    Raises
    ------
    jose.JWTError
        When the token is invalid, expired, or tampered with.
    """
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
