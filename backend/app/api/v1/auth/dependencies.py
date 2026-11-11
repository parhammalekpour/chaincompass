from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.db.models.auth import User
from app.db.session import get_session

bearer_scheme = HTTPBearer(auto_error=False)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CredentialDependency = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]


async def get_current_user(
    credentials: CredentialDependency,
    session: SessionDependency,
) -> User:
    if credentials is None:
        raise APIError(401, "invalid_access_token", "Authentication is required")
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = UUID(claims["sub"])
    except (InvalidAccessTokenError, TypeError, ValueError):
        raise APIError(401, "invalid_access_token", "Access token is invalid") from None

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise APIError(401, "invalid_access_token", "Access token is invalid")
    return user


CurrentUserDependency = Annotated[User, Depends(get_current_user)]
UserDependency = Callable[..., Awaitable[User]]


async def require_verified_user(user: CurrentUserDependency) -> User:
    if user.email_verified_at is None:
        raise APIError(
            403,
            "email_not_verified",
            "Email verification is required",
        )
    return user


def require_role(required_role: str) -> UserDependency:
    async def dependency(user: CurrentUserDependency) -> User:
        if user.role != required_role:
            raise APIError(403, "forbidden", "You do not have permission")
        return user

    return dependency
