from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
import pytest
from argon2 import PasswordHasher
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.auth.router import CSRF_COOKIE, REFRESH_COOKIE
from app.core.config import settings
from app.core.security import hash_password, hash_refresh_token
from app.db.models.auth import RefreshToken, User

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.usefixtures("clean_auth_tables"),
]

TEST_EMAIL = "auth-test@example.com"
TEST_PASSWORD = "Strong-Test-Password-42!"


async def register_user(client: AsyncClient, email: str = TEST_EMAIL) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "locale": "fa"},
    )
    assert response.status_code == 202


async def login_user(client: AsyncClient, email: str = TEST_EMAIL) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def csrf_headers(client: AsyncClient) -> dict[str, str]:
    csrf_token = client.cookies.get(CSRF_COOKIE)
    assert csrf_token
    return {"X-CSRF-Token": csrf_token}


async def test_register_duplicate_weak_password_and_argon2id(
    auth_client: AsyncClient,
    auth_session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    weak = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": "password", "locale": "en"},
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "weak_password"
    email_as_password = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_EMAIL, "locale": "en"},
    )
    assert email_as_password.status_code == 422
    assert email_as_password.json()["error"]["code"] == "weak_password"

    first = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "Auth-Test@EXAMPLE.com",
            "password": TEST_PASSWORD,
            "locale": "fa",
        },
    )
    duplicate = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "locale": "fa"},
    )
    assert first.status_code == duplicate.status_code == 202
    assert first.json() == duplicate.json()
    assert not first.headers.get_list("set-cookie")
    assert "password_hash" not in first.text
    assert TEST_PASSWORD not in first.text

    async with auth_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == TEST_EMAIL))
    assert user is not None
    assert user.email == TEST_EMAIL
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash not in caplog.text
    assert TEST_PASSWORD not in caplog.text
    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200
    assert user.password_hash not in login_response.text
    assert user.password_hash not in caplog.text


async def test_login_rehashes_outdated_argon2id_hash(
    auth_client: AsyncClient,
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    old_hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    old_hash = old_hasher.hash(TEST_PASSWORD)
    async with auth_session_factory() as session:
        session.add(
            User(
                email=TEST_EMAIL,
                password_hash=old_hash,
                locale="en",
            )
        )
        await session.commit()

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    async with auth_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == TEST_EMAIL))
    assert user is not None
    assert user.password_hash is not None
    assert user.password_hash != old_hash
    assert not PasswordHasher().check_needs_rehash(user.password_hash)


async def test_login_errors_me_expired_and_tampered_tokens(
    auth_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await register_user(auth_client)
    unknown = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": TEST_PASSWORD},
    )
    wrong = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": "Wrong-Password-123!"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert unknown.json()["error"]["code"] == "invalid_credentials"

    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200
    auth_data = login_response.json()
    assert auth_data["token_type"] == "bearer"
    assert auth_data["expires_in"] == settings.access_token_minutes * 60
    assert auth_data["user"]["email"] == TEST_EMAIL
    assert "password_hash" not in str(auth_data)
    refresh_cookie = auth_client.cookies.get(REFRESH_COOKIE)
    assert refresh_cookie
    assert len(refresh_cookie) > 40
    assert refresh_cookie not in caplog.text
    assert auth_data["access_token"] not in caplog.text
    set_cookies = login_response.headers.get_list("set-cookie")
    refresh_set_cookie = next(
        cookie for cookie in set_cookies if cookie.startswith(f"{REFRESH_COOKIE}=")
    )
    csrf_set_cookie = next(
        cookie for cookie in set_cookies if cookie.startswith(f"{CSRF_COOKIE}=")
    )
    assert "httponly" in refresh_set_cookie.lower()
    assert "samesite=lax" in refresh_set_cookie.lower()
    assert "path=/api/v1/auth" in refresh_set_cookie.lower()
    assert "httponly" not in csrf_set_cookie.lower()

    valid = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {auth_data['access_token']}"},
    )
    assert valid.status_code == 200
    assert valid.json()["locale"] == "fa"
    assert valid.json()["email_verified"] is False

    claims = jwt.decode(
        auth_data["access_token"],
        settings.jwt_secret,
        algorithms=["HS256"],
        options={"verify_exp": False},
    )
    claims["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    expired_token = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
    for token in (expired_token, f"{auth_data['access_token']}tampered"):
        response = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_access_token"


async def test_refresh_rotates_and_reuse_revokes_family(
    auth_client: AsyncClient,
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_user(auth_client)
    await login_user(auth_client)
    first_refresh = auth_client.cookies.get(REFRESH_COOKIE)
    assert first_refresh
    first_csrf = csrf_headers(auth_client)
    response = await auth_client.post("/api/v1/auth/refresh", headers=first_csrf)
    assert response.status_code == 200
    second_refresh = auth_client.cookies.get(REFRESH_COOKIE)
    assert second_refresh and second_refresh != first_refresh
    assert response.json()["access_token"]

    reused = await auth_client.post(
        "/api/v1/auth/refresh",
        headers={
            **csrf_headers(auth_client),
            "Cookie": (
                f"{REFRESH_COOKIE}={first_refresh}; "
                f"{CSRF_COOKIE}={auth_client.cookies.get(CSRF_COOKIE)}"
            ),
        },
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_token_reuse"

    second_reuse = await auth_client.post(
        "/api/v1/auth/refresh",
        headers={
            **csrf_headers(auth_client),
            "Cookie": (
                f"{REFRESH_COOKIE}={second_refresh}; "
                f"{CSRF_COOKIE}={auth_client.cookies.get(CSRF_COOKIE)}"
            ),
        },
    )
    assert second_reuse.status_code == 401
    assert second_reuse.json()["error"]["code"] == "refresh_token_reuse"
    async with auth_session_factory() as session:
        tokens = list((await session.scalars(select(RefreshToken))).all())
    assert len(tokens) == 2
    assert all(token.revoked_at is not None for token in tokens)


async def test_logout_and_csrf_protection(
    auth_client: AsyncClient,
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_user(auth_client)
    await login_user(auth_client)
    refresh_cookie = auth_client.cookies.get(REFRESH_COOKIE)
    assert refresh_cookie
    missing_refresh_csrf = await auth_client.post("/api/v1/auth/refresh")
    assert missing_refresh_csrf.status_code == 403
    assert missing_refresh_csrf.json()["error"]["code"] == "csrf_failed"

    missing_csrf = await auth_client.post("/api/v1/auth/logout")
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "csrf_failed"

    invalid_origin = await auth_client.post(
        "/api/v1/auth/logout",
        headers={**csrf_headers(auth_client), "Origin": "https://attacker.example"},
    )
    assert invalid_origin.status_code == 403
    assert invalid_origin.json()["error"]["code"] == "origin_not_allowed"

    response = await auth_client.post(
        "/api/v1/auth/logout",
        headers={**csrf_headers(auth_client), "Origin": settings.frontend_origin},
    )
    assert response.status_code == 204
    assert REFRESH_COOKIE in response.headers["set-cookie"]
    async with auth_session_factory() as session:
        stored_token = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh_cookie)
            )
        )
    assert stored_token is not None
    assert stored_token.revoked_at is not None
    token_after_logout = await auth_client.post(
        "/api/v1/auth/refresh",
        headers={
            "X-CSRF-Token": "csrf-after-logout",
            "Cookie": f"{CSRF_COOKIE}=csrf-after-logout",
        },
    )
    assert token_after_logout.status_code == 401


async def test_role_dependency(auth_client: AsyncClient) -> None:
    await register_user(auth_client)
    user_auth = await login_user(auth_client)
    forbidden = await auth_client.get(
        "/_admin-check",
        headers={"Authorization": f"Bearer {user_auth['access_token']}"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


async def test_admin_role_dependency_accepts_admin(
    auth_client: AsyncClient,
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with auth_session_factory() as session:
        admin = User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email="admin-test@example.com",
            password_hash=hash_password(TEST_PASSWORD),
            role="admin",
        )
        session.add(admin)
        await session.commit()

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "admin-test@example.com", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    result = await auth_client.get(
        "/_admin-check",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert result.status_code == 200
    assert result.json()["role"] == "admin"
