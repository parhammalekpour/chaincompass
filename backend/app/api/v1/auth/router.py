import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import CurrentUserDependency
from app.api.v1.auth.schemas import (
    AuthTokenResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from app.core.config import settings
from app.core.errors import APIError
from app.core.security import (
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    password_needs_rehash,
    validate_password,
    verify_password,
)
from app.db.models.auth import RefreshToken, User
from app.db.session import get_session

router = APIRouter()
REFRESH_COOKIE = "chaincompass_refresh"
CSRF_COOKIE = "chaincompass_csrf"
REFRESH_PATH = "/api/v1/auth"


def _invalid_refresh() -> APIError:
    return APIError(401, "invalid_refresh_token", "Refresh token is invalid")


def _set_auth_cookies(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_PATH,
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        CSRF_COOKIE,
        create_csrf_token(),
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_PATH,
        domain=settings.cookie_domain,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_PATH,
        domain=settings.cookie_domain,
    )
    response.delete_cookie(
        CSRF_COOKIE,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_PATH,
        domain=settings.cookie_domain,
    )


def _check_csrf(request: Request) -> None:
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get("X-CSRF-Token")
    if (
        not csrf_cookie
        or not csrf_header
        or not secrets.compare_digest(csrf_cookie, csrf_header)
    ):
        raise APIError(403, "csrf_failed", "CSRF token is invalid")

    origin = request.headers.get("Origin")
    if (
        origin
        and origin.rstrip("/").lower() != settings.frontend_origin.rstrip("/").lower()
    ):
        raise APIError(403, "origin_not_allowed", "Request origin is not allowed")


def _request_metadata(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("User-Agent")
    client_ip = request.client.host if request.client else None
    return (user_agent[:512] if user_agent else None, client_ip)


async def _store_refresh_token(
    session: AsyncSession,
    user: User,
    refresh_token: str,
    family_id: UUID,
    request: Request,
) -> RefreshToken:
    user_agent, client_ip = _request_metadata(request)
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        family_id=family_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        user_agent=user_agent,
        ip=client_ip,
    )
    session.add(token)
    return token


def _token_response(user: User, access_token: str) -> AuthTokenResponse:
    return AuthTokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_minutes * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            locale=user.locale,
            role=user.role,
        ),
    )


@router.post("/register", response_model=RegisterResponse, status_code=202)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    email = str(body.email).lower()
    if not validate_password(body.password, email):
        raise APIError(
            422,
            "weak_password",
            "Password does not meet the minimum requirements",
        )

    existing = await session.scalar(select(User.id).where(User.email == email))
    if existing is None:
        session.add(
            User(
                email=email,
                password_hash=hash_password(body.password),
                locale=body.locale,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(select(User.id).where(User.email == email))
            if existing is None:
                raise APIError(
                    500,
                    "registration_failed",
                    "Registration could not be completed",
                ) from None

    return RegisterResponse()


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthTokenResponse:
    email = str(body.email).lower()
    user = await session.scalar(select(User).where(User.email == email))
    if (
        user is None
        or user.password_hash is None
        or not user.is_active
        or not verify_password(user.password_hash, body.password)
    ):
        raise APIError(401, "invalid_credentials", "Invalid email or password")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    user.last_login_at = datetime.now(UTC)
    refresh_token = create_refresh_token()
    await _store_refresh_token(session, user, refresh_token, uuid4(), request)
    await session.commit()
    _set_auth_cookies(response, refresh_token)
    return _token_response(user, create_access_token(str(user.id), user.role))


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthTokenResponse:
    _check_csrf(request)
    token_value = request.cookies.get(REFRESH_COOKIE)
    if not token_value:
        raise _invalid_refresh()

    stored_token = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(token_value))
        .with_for_update()
    )
    if stored_token is None:
        raise _invalid_refresh()
    now = datetime.now(UTC)
    if stored_token.revoked_at is not None:
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == stored_token.family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await session.commit()
        raise APIError(401, "refresh_token_reuse", "Refresh token reuse was detected")
    if stored_token.expires_at <= now:
        raise _invalid_refresh()

    user = await session.get(User, stored_token.user_id)
    if user is None or not user.is_active:
        raise _invalid_refresh()

    replacement_value = create_refresh_token()
    replacement = await _store_refresh_token(
        session,
        user,
        replacement_value,
        stored_token.family_id,
        request,
    )
    await session.flush()
    stored_token.revoked_at = now
    stored_token.replaced_by_id = replacement.id
    await session.commit()
    _set_auth_cookies(response, replacement_value)
    return _token_response(user, create_access_token(str(user.id), user.role))


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> Response:
    _check_csrf(request)
    token_value = request.cookies.get(REFRESH_COOKIE)
    if token_value:
        stored_token = await session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(token_value))
            .with_for_update()
        )
        if stored_token is not None and stored_token.revoked_at is None:
            stored_token.revoked_at = datetime.now(UTC)
            await session.commit()
    _clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUserDependency) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        locale=user.locale,
        role=user.role,
        email_verified=user.email_verified_at is not None,
    )
