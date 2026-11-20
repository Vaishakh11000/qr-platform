from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


_password_hasher = PasswordHasher()

TOKEN_ALGORITHM = "HS256"
TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2."""
    if not password:
        raise ValueError("Password cannot be empty.")

    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its Argon2 hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError, TypeError):
        return False


def create_access_token(admin_id: UUID) -> str:
    """Create a short-lived signed access token for an administrator."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.admin_access_token_expire_minutes
    )

    payload = {
        "sub": str(admin_id),
        "iat": now,
        "exp": expires_at,
        "type": TOKEN_TYPE,
    }

    return jwt.encode(
        payload,
        settings.admin_token_secret.get_secret_value(),
        algorithm=TOKEN_ALGORITHM,
    )


def decode_access_token(token: str) -> UUID | None:
    """Validate an access token and return its administrator UUID."""
    try:
        payload = jwt.decode(
            token,
            settings.admin_token_secret.get_secret_value(),
            algorithms=[TOKEN_ALGORITHM],
            options={"require": ["sub", "iat", "exp", "type"]},
        )

        if payload.get("type") != TOKEN_TYPE:
            return None

        return UUID(payload["sub"])

    except (InvalidTokenError, ValueError, TypeError, KeyError):
        return None
