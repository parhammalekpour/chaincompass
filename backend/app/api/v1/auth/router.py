import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.api.v1.auth.dependencies import CurrentUserDependency
from app.api.v1.auth.schemas import (
    AuthTokenResponse,
    ChangePasswordRequest,
    EmailRequest,
    EmailTokenRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
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
from app.db.models.auth import EmailToken, OAuthAccount, RefreshToken, User
from app.db.session import get_session
from app.services.clock import Clock, utc_now
from app.services.email import (
    EmailSender,
    email_for,
    get_email_sender,
    send_email_safely,
)
from app.services.google_oauth import (
    create_google_authorization_url,
    exchange_google_code,
    google_is_configured,
)
from app.services.rate_limit import check_rate_limit, client_ip

router = APIRouter()
logger = logging.getLogger(__name__)
REFRESH_COOKIE = "chaincompass_refresh"
CSRF_COOKIE = "chaincompass_csrf"
REFRESH_PATH = "/api/v1/auth"
GOOGLE_STATE_COOKIE = "chaincompass_google_state"
auth_clock: Clock = utc_now
email_sender: EmailSender = get_email_sender()
DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password-000")


def _invalid_refresh() -> APIError:
    return APIError(401, "invalid_refresh_token", "Refresh token is invalid")


def _invalid_login_response(background_tasks: BackgroundTasks) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "invalid_credentials",
                "message": "Invalid email or password",
            }
        },
        background=background_tasks,
    )


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


def _email_link(locale: str, page: str, token: str) -> str:
    return f"{settings.frontend_origin.rstrip('/')}/{locale}/{page}?token={token}"


def _queue_email(
    background_tasks: BackgroundTasks,
    recipient: str,
    locale: str,
    kind: str,
    link: str | None = None,
) -> None:
    background_tasks.add_task(
        send_email_safely,
        email_sender,
        email_for(recipient, locale, kind, link),
    )


async def _create_email_token(
    session: AsyncSession,
    user: User,
    purpose: Literal["verify_email", "reset_password"],
    expires_in: timedelta,
    invalidate_previous: bool = False,
) -> str:
    if invalidate_previous:
        await session.execute(
            update(EmailToken)
            .where(
                EmailToken.user_id == user.id,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
            )
            .values(used_at=auth_clock())
        )
    raw_token = create_refresh_token()
    session.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_refresh_token(raw_token),
            expires_at=auth_clock() + expires_in,
        )
    )
    return raw_token


async def _limited_email_and_ip(
    request: Request,
    email: str,
    bucket: str,
) -> None:
    window = timedelta(hours=1)
    await check_rate_limit(f"{bucket}:email", email, 5, window)
    await check_rate_limit(f"{bucket}:ip", client_ip(request), 10, window)


async def _revoke_user_refresh_tokens(
    session: AsyncSession,
    user_id: UUID,
    except_family: UUID | None = None,
) -> None:
    statement = update(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )
    if except_family is not None:
        statement = statement.where(RefreshToken.family_id != except_family)
    await session.execute(statement.values(revoked_at=auth_clock()))


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
        expires_at=auth_clock() + timedelta(days=settings.refresh_token_days),
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
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    await check_rate_limit("register:ip", client_ip(request), 5, timedelta(hours=1))
    email = str(body.email).lower()
    if not validate_password(body.password, email):
        raise APIError(
            422,
            "weak_password",
            "Password does not meet the minimum requirements",
        )

    password_hash = hash_password(body.password)
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is None:
        user = User(email=email, password_hash=password_hash, locale=body.locale)
        session.add(user)
        await session.flush()
        token = await _create_email_token(
            session, user, "verify_email", timedelta(hours=24)
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(select(User).where(User.email == email))
            if existing is None:
                raise APIError(
                    500,
                    "registration_failed",
                    "Registration could not be completed",
                ) from None
            _queue_email(
                background_tasks,
                existing.email,
                existing.locale,
                "account_exists",
            )
        else:
            _queue_email(
                background_tasks,
                user.email,
                user.locale,
                "verify_email",
                _email_link(user.locale, "verify-email", token),
            )
    else:
        _queue_email(
            background_tasks,
            existing.email,
            existing.locale,
            "account_exists",
        )

    return RegisterResponse()


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> AuthTokenResponse | JSONResponse:
    email = str(body.email).lower()
    await check_rate_limit("login:ip", client_ip(request), 10, timedelta(minutes=1))
    user = await session.scalar(
        select(User).where(User.email == email).with_for_update()
    )
    now = auth_clock()
    locked = (
        user is not None and user.locked_until is not None and user.locked_until > now
    )
    if locked:
        return _invalid_login_response(background_tasks)
    await check_rate_limit("login:email", email, 5, timedelta(minutes=1))

    stored_hash = (
        user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
    )
    valid_password = verify_password(stored_hash, body.password)
    if (
        user is None
        or user.password_hash is None
        or not user.is_active
        or not valid_password
    ):
        if user is not None and user.is_active:
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                was_unlocked = user.locked_until is None or user.locked_until <= now
                user.locked_until = now + timedelta(minutes=15)
                if was_unlocked:
                    _queue_email(
                        background_tasks,
                        user.email,
                        user.locale,
                        "temporarily_locked",
                    )
            await session.commit()
        return _invalid_login_response(background_tasks)

    if user.locked_until is not None:
        user.locked_until = None
    user.failed_login_count = 0
    if password_needs_rehash(stored_hash):
        user.password_hash = hash_password(body.password)
    user.last_login_at = now
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


@router.post("/verify-email")
async def verify_email(
    body: EmailTokenRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    token = await session.scalar(
        select(EmailToken)
        .where(
            EmailToken.token_hash == hash_refresh_token(body.token),
            EmailToken.purpose == "verify_email",
        )
        .with_for_update()
    )
    now = auth_clock()
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise APIError(
            400, "invalid_email_token", "Email verification token is invalid"
        )

    user = await session.get(User, token.user_id)
    if user is None:
        raise APIError(
            400, "invalid_email_token", "Email verification token is invalid"
        )
    token.used_at = now
    user.email_verified_at = now
    await session.commit()
    return {"message": "Email verified"}


@router.post("/resend-verification", response_model=RegisterResponse, status_code=202)
async def resend_verification(
    body: EmailRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    email = str(body.email).lower()
    await _limited_email_and_ip(request, email, "resend_verification")
    user = await session.scalar(select(User).where(User.email == email))
    if user is not None and user.email_verified_at is None:
        token = await _create_email_token(
            session,
            user,
            "verify_email",
            timedelta(hours=24),
            invalidate_previous=True,
        )
        await session.commit()
        _queue_email(
            background_tasks,
            user.email,
            user.locale,
            "verify_email",
            _email_link(user.locale, "verify-email", token),
        )
    return RegisterResponse()


@router.post("/forgot-password", response_model=RegisterResponse, status_code=202)
async def forgot_password(
    body: EmailRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    email = str(body.email).lower()
    await _limited_email_and_ip(request, email, "forgot_password")
    hash_password(secrets.token_urlsafe(24))
    user = await session.scalar(select(User).where(User.email == email))
    if user is not None and user.is_active:
        token = await _create_email_token(
            session,
            user,
            "reset_password",
            timedelta(hours=1),
            invalidate_previous=True,
        )
        await session.commit()
        _queue_email(
            background_tasks,
            user.email,
            user.locale,
            "reset_password",
            _email_link(user.locale, "reset-password", token),
        )
    return RegisterResponse()


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    token = await session.scalar(
        select(EmailToken)
        .where(
            EmailToken.token_hash == hash_refresh_token(body.token),
            EmailToken.purpose == "reset_password",
        )
        .with_for_update()
    )
    now = auth_clock()
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise APIError(400, "invalid_reset_token", "Password reset token is invalid")

    user = await session.get(User, token.user_id)
    if user is None or not validate_password(body.new_password, user.email):
        raise APIError(
            422,
            "weak_password",
            "Password does not meet the minimum requirements",
        )

    token.used_at = now
    user.password_hash = hash_password(body.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    await _revoke_user_refresh_tokens(session, user.id)
    await session.commit()
    _queue_email(
        background_tasks,
        user.email,
        user.locale,
        "password_changed",
    )
    return {"message": "Password changed"}


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUserDependency,
    session: AsyncSession = Depends(get_session),
) -> Response:
    if user.password_hash is None or not verify_password(
        user.password_hash, body.current_password
    ):
        raise APIError(401, "invalid_credentials", "Current password is invalid")
    if not validate_password(body.new_password, user.email):
        raise APIError(
            422,
            "weak_password",
            "Password does not meet the minimum requirements",
        )

    user.password_hash = hash_password(body.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    current_refresh = request.cookies.get(REFRESH_COOKIE)
    current_family: UUID | None = None
    if current_refresh:
        current_token = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.token_hash == hash_refresh_token(current_refresh),
                RefreshToken.revoked_at.is_(None),
            )
        )
        if current_token is not None:
            current_family = current_token.family_id
    await _revoke_user_refresh_tokens(session, user.id, current_family)
    await session.commit()
    _queue_email(
        background_tasks,
        user.email,
        user.locale,
        "password_changed",
    )
    return Response(status_code=204)


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUserDependency) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        locale=user.locale,
        role=user.role,
        email_verified=user.email_verified_at is not None,
    )


def _oauth_redirect(locale: str, success: bool) -> RedirectResponse:
    if success:
        target = f"{settings.frontend_origin.rstrip('/')}/{locale}/auth/callback"
    else:
        target = (
            f"{settings.frontend_origin.rstrip('/')}/{locale}/login?error=oauth_failed"
        )
    return RedirectResponse(target, status_code=303)


@router.get("/google/login")
async def google_login(request: Request) -> Response:
    if not google_is_configured():
        raise APIError(501, "oauth_not_configured", "Google sign-in is not configured")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    requested_locale = request.cookies.get("NEXT_LOCALE", "en")
    locale = requested_locale if requested_locale in {"en", "fa"} else "en"
    authorization_url = await create_google_authorization_url(state, nonce, verifier)
    state_cookie = jwt.encode(
        {
            "state": state,
            "nonce": nonce,
            "verifier": verifier,
            "locale": locale,
            "exp": auth_clock() + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    redirect = RedirectResponse(authorization_url, status_code=302)
    redirect.set_cookie(
        GOOGLE_STATE_COOKIE,
        state_cookie,
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth/google",
        domain=settings.cookie_domain,
    )
    return redirect


@router.get("/google/callback")
async def google_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not google_is_configured():
        raise APIError(501, "oauth_not_configured", "Google sign-in is not configured")

    state_cookie = request.cookies.get(GOOGLE_STATE_COOKIE)
    state_data: dict[str, object] = {}
    locale = "en"
    try:
        if not state_cookie:
            raise ValueError("Missing OAuth state")
        state_data = jwt.decode(
            state_cookie,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["state", "nonce", "verifier", "exp"]},
        )
        state_value = state_data.get("state")
        nonce_value = state_data.get("nonce")
        verifier_value = state_data.get("verifier")
        locale_value = state_data.get("locale", "en")
        if not isinstance(state_value, str):
            raise ValueError("OAuth state cookie is invalid")
        if not isinstance(nonce_value, str):
            raise ValueError("OAuth nonce cookie is invalid")
        if not isinstance(verifier_value, str):
            raise ValueError("OAuth verifier cookie is invalid")
        if not isinstance(locale_value, str):
            raise ValueError("OAuth state cookie is invalid")
        locale = locale_value if locale_value in {"en", "fa"} else "en"
        if request.query_params.get("state") != state_value:
            raise ValueError("OAuth state mismatch")
        code = request.query_params.get("code")
        if not code:
            raise ValueError("Missing OAuth code")
        claims = await exchange_google_code(
            code,
            verifier_value,
            nonce_value,
        )
        if claims.get("email_verified") is not True:
            raise ValueError("Google email is not verified")
        subject = claims.get("sub")
        email_claim = claims.get("email")
        if (
            not isinstance(subject, str)
            or not subject
            or not isinstance(email_claim, str)
        ):
            raise ValueError("Google identity claims are incomplete")
        email = email_claim.lower()
        existing_account = await session.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider == "google",
                OAuthAccount.provider_account_id == subject,
            )
        )
        if existing_account is not None:
            user = await session.get(User, existing_account.user_id)
        else:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, password_hash=None, locale=locale)
                session.add(user)
                await session.flush()
            user.email_verified_at = auth_clock()
            session.add(
                OAuthAccount(
                    user_id=user.id,
                    provider="google",
                    provider_account_id=subject,
                    email=email,
                )
            )
        if user is None:
            raise ValueError("Google account is unavailable")
        if not user.is_active:
            raise ValueError("Google account is inactive")

        user.email_verified_at = user.email_verified_at or auth_clock()
        refresh_token = create_refresh_token()
        await _store_refresh_token(session, user, refresh_token, uuid4(), request)
        await session.commit()
        redirect = _oauth_redirect(user.locale, True)
        _set_auth_cookies(redirect, refresh_token)
        redirect.delete_cookie(
            GOOGLE_STATE_COOKIE,
            path="/api/v1/auth/google",
            secure=settings.cookie_secure,
            samesite="lax",
            domain=settings.cookie_domain,
        )
        return redirect
    except Exception as exc:
        await session.rollback()
        logger.warning("Google OAuth callback failed (%s)", type(exc).__name__)
        redirect = _oauth_redirect(locale, False)
        redirect.delete_cookie(
            GOOGLE_STATE_COOKIE,
            path="/api/v1/auth/google",
            secure=settings.cookie_secure,
            samesite="lax",
            domain=settings.cookie_domain,
        )
        return redirect
