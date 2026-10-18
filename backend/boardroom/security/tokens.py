"""Short-lived access tokens, opaque refresh and invitation tokens, password hashing."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from boardroom.config import get_settings

_hasher = PasswordHasher()
# Verified against when the email is unknown, so a login takes the same time either way.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def issue_access_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_minutes)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "iss": settings.jwt_issuer,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "jti": uuid.uuid4().hex,
            "typ": "access",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token, expires


def verify_access_token(token: str) -> uuid.UUID:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss", "typ"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("invalid token") from exc
    if claims.get("typ") != "access":
        raise TokenError("wrong token type")
    try:
        return uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise TokenError("invalid subject") from exc


def new_opaque_token() -> tuple[str, str]:
    """Return a random token and the hash stored in its place. The token itself is never stored."""
    token = secrets.token_urlsafe(32)
    return token, hash_opaque_token(token)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
