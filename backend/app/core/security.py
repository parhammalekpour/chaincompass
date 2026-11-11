import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt import InvalidTokenError

from app.core.config import settings

password_hasher = PasswordHasher()
COMMON_PASSWORDS = {
    "password",
    "password123",
    "qwerty12345",
    "1234567890",
    "letmein123",
    "welcome1234",
    "iloveyou123",
}


class InvalidAccessTokenError(Exception):
    pass


def validate_password(password: str, email: str) -> bool:
    normalized = password.casefold()
    return (
        10 <= len(password) <= 128
        and normalized != email.casefold()
        and normalized not in COMMON_PASSWORDS
    )


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return password_hasher.check_needs_rehash(password_hash)


def create_access_token(subject: str, role: str) -> str:
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {
            "sub": subject,
            "role": role,
            "exp": expires_at,
            "iat": issued_at,
            "jti": str(uuid4()),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if not all(key in payload for key in ("sub", "role", "exp", "iat", "jti")):
            raise InvalidAccessTokenError
        return {str(key): value for key, value in payload.items()}
    except (InvalidTokenError, InvalidAccessTokenError) as exc:
        raise InvalidAccessTokenError from exc


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)
