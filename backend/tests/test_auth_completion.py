import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.auth import router as auth_routes
from app.api.v1.auth.router import GOOGLE_STATE_COOKIE, REFRESH_COOKIE
from app.core.config import settings
from app.db.models.auth import EmailToken, OAuthAccount, RefreshToken, User
from app.services.email import build_auth_email
from app.services.rate_limit import reset_rate_limiter

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.usefixtures("clean_auth_tables"),
]

PASSWORD = "Strong-Email-Password-58!"


async def register(
    client: AsyncClient, email: str = "flow@example.com", locale: str = "en"
) -> Any:
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "locale": locale},
    )


def email_token(message_text: str) -> str:
    match = re.search(r"https?://[^\s]+[?&]token=([A-Za-z0-9_-]+)", message_text)
    assert match
    return match.group(1)


async def login(client: AsyncClient, email: str = "flow@example.com") -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


async def test_register_hashes_once_for_new_and_duplicate_and_sends_notice(
    auth_client: AsyncClient,
    captured_email_sender: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0
    original_hash = auth_routes.hash_password

    def counting_hash(password: str) -> str:
        nonlocal calls
        calls += 1
        return original_hash(password)

    monkeypatch.setattr(auth_routes, "hash_password", counting_hash)
    new_user = await register(auth_client)
    duplicate = await register(auth_client)
    assert new_user.status_code == duplicate.status_code == 202
    assert new_user.json() == duplicate.json()
    assert calls == 2
    assert len(captured_email_sender.messages) == 2
    assert (
        "http://localhost:3000/en/verify-email?token="
        in captured_email_sender.messages[0].text
    )
    raw_token = email_token(captured_email_sender.messages[0].text)
    assert raw_token not in caplog.text
    assert PASSWORD not in caplog.text
    assert captured_email_sender.messages[1].subject == "ChainCompass account notice"


async def test_verify_email_success_expired_reused_tampered_and_verified_guard(
    auth_client: AsyncClient,
    captured_email_sender: Any,
    auth_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = datetime(2026, 11, 11, tzinfo=UTC)
    monkeypatch.setattr(auth_routes, "auth_clock", lambda: base)
    await register(auth_client, "verify@example.com")
    raw_token = email_token(captured_email_sender.messages[-1].text)
    protected = await auth_client.get(
        "/_verified-check",
        headers={
            "Authorization": "Bearer "
            + (await login(auth_client, "verify@example.com"))["access_token"]
        },
    )
    assert protected.status_code == 403
    assert protected.json()["error"]["code"] == "email_not_verified"

    verified = await auth_client.post(
        "/api/v1/auth/verify-email", json={"token": raw_token}
    )
    assert verified.status_code == 200
    again = await auth_client.post(
        "/api/v1/auth/verify-email", json={"token": raw_token}
    )
    tampered = await auth_client.post(
        "/api/v1/auth/verify-email", json={"token": raw_token + "bad"}
    )
    assert again.status_code == tampered.status_code == 400
    assert again.json()["error"]["code"] == "invalid_email_token"

    async with auth_session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "verify@example.com")
        )
        assert user and user.email_verified_at is not None
        expired = EmailToken(
            user_id=user.id,
            purpose="verify_email",
            token_hash=auth_routes.hash_refresh_token("expired-verification-token"),
            expires_at=base - timedelta(seconds=1),
        )
        session.add(expired)
        await session.commit()
    expired_response = await auth_client.post(
        "/api/v1/auth/verify-email",
        json={"token": "expired-verification-token"},
    )
    assert expired_response.status_code == 400


async def test_expired_password_reset_token_is_rejected(
    auth_client: AsyncClient,
    auth_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 11, 11, tzinfo=UTC)
    monkeypatch.setattr(auth_routes, "auth_clock", lambda: now)
    await register(auth_client, "expired-reset@example.com")
    async with auth_session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "expired-reset@example.com")
        )
        assert user
        token = EmailToken(
            user_id=user.id,
            purpose="reset_password",
            token_hash=auth_routes.hash_refresh_token(
                "expired-reset-token-value-with-enough-length"
            ),
            expires_at=now - timedelta(seconds=1),
        )
        session.add(token)
        await session.commit()
    response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "expired-reset-token-value-with-enough-length",
            "new_password": "New-Expired-Password-52!",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_reset_token"


async def test_resend_forgot_generic_responses_and_newest_reset_token(
    auth_client: AsyncClient,
    captured_email_sender: Any,
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register(auth_client, "known@example.com")
    unknown_resend = await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "missing@example.com"},
    )
    known_resend = await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "known@example.com"},
    )
    assert unknown_resend.status_code == known_resend.status_code == 202
    assert unknown_resend.json() == known_resend.json()
    await register(auth_client, "localized@example.com", locale="fa")
    await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "localized@example.com"},
    )
    localized_message = captured_email_sender.messages[-1]
    assert "http://localhost:3000/fa/verify-email?token=" in localized_message.text

    unknown_forgot = await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "missing@example.com"},
    )
    known_forgot = await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "known@example.com"},
    )
    assert unknown_forgot.status_code == known_forgot.status_code == 202
    assert unknown_forgot.json() == known_forgot.json()
    reset_messages = [
        message
        for message in captured_email_sender.messages
        if "reset-password?token=" in message.text
    ]
    assert len(reset_messages) == 1
    assert "http://localhost:3000/en/reset-password?token=" in reset_messages[0].text

    old_reset_token = email_token(reset_messages[0].text)
    await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "known@example.com"},
    )
    reset_messages = [
        message
        for message in captured_email_sender.messages
        if "reset-password?token=" in message.text
    ]
    assert len(reset_messages) == 2
    new_reset_token = email_token(reset_messages[-1].text)
    old_response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": old_reset_token, "new_password": "New-Strong-Password-42!"},
    )
    new_response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": new_reset_token, "new_password": "New-Strong-Password-42!"},
    )
    reuse_response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": new_reset_token, "new_password": "Another-Strong-Password-42!"},
    )
    assert old_response.status_code == 400
    assert new_response.status_code == 200
    assert reuse_response.status_code == 400
    async with auth_session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "known@example.com")
        )
        assert user and user.password_hash


async def test_password_reset_revokes_all_refresh_tokens_and_supports_oauth_user(
    auth_client: AsyncClient,
    captured_email_sender: Any,
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with auth_session_factory() as session:
        oauth_user = User(email="google-only@example.com", password_hash=None)
        session.add(oauth_user)
        await session.flush()
        for _ in range(2):
            session.add(
                RefreshToken(
                    user_id=oauth_user.id,
                    token_hash=auth_routes.hash_refresh_token(str(uuid4())),
                    family_id=uuid4(),
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )
        await session.commit()
    await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "google-only@example.com"},
    )
    token = email_token(captured_email_sender.messages[-1].text)
    response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "New-Google-Password-52!"},
    )
    assert response.status_code == 200
    async with auth_session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "google-only@example.com")
        )
        tokens = list((await session.scalars(select(RefreshToken))).all())
        assert user and user.password_hash
        assert len(tokens) == 2
        assert all(item.revoked_at is not None for item in tokens)


async def test_change_password_revokes_other_families_and_sends_notice(
    auth_client: AsyncClient,
    captured_email_sender: Any,
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register(auth_client, "change@example.com")
    auth = await login(auth_client, "change@example.com")
    current_refresh = auth_client.cookies.get(REFRESH_COOKIE)
    assert current_refresh
    async with auth_session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "change@example.com")
        )
        assert user
        session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=auth_routes.hash_refresh_token("other-session-token"),
                family_id=uuid4(),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await session.commit()
    response = await auth_client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": PASSWORD,
            "new_password": "Changed-Password-52!",
        },
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 204
    async with auth_session_factory() as session:
        tokens = list((await session.scalars(select(RefreshToken))).all())
        user = await session.scalar(
            select(User).where(User.email == "change@example.com")
        )
    assert user and user.password_hash
    current_hash = auth_routes.hash_refresh_token(current_refresh)
    kept = [item for item in tokens if item.token_hash == current_hash]
    revoked = [item for item in tokens if item.token_hash != current_hash]
    assert len(kept) == 1 and kept[0].revoked_at is None
    assert revoked and all(item.revoked_at is not None for item in revoked)
    assert captured_email_sender.messages[-1].subject.endswith("password was changed")


async def test_lockout_generic_response_and_clock_controlled_unlock(
    auth_client: AsyncClient,
    captured_email_sender: Any,
    auth_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 11, 11, tzinfo=UTC)
    monkeypatch.setattr(auth_routes, "auth_clock", lambda: now)
    await register(auth_client, "locked@example.com")
    captured_email_sender.messages.clear()
    responses = []
    for _ in range(5):
        responses.append(
            await auth_client.post(
                "/api/v1/auth/login",
                json={
                    "email": "locked@example.com",
                    "password": "Incorrect-Password-56!",
                },
            )
        )
    assert all(
        response.status_code == 401
        and response.json()["error"]["code"] == "invalid_credentials"
        for response in responses
    )
    assert len(captured_email_sender.messages) == 1
    locked_response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "locked@example.com", "password": PASSWORD},
    )
    assert locked_response.status_code == responses[0].status_code
    assert locked_response.json() == responses[0].json()

    async with auth_session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "locked@example.com")
        )
        assert user and user.locked_until == now + timedelta(minutes=15)
    monkeypatch.setattr(auth_routes, "auth_clock", lambda: now + timedelta(minutes=16))
    reset_rate_limiter()
    unlocked = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "locked@example.com", "password": PASSWORD},
    )
    assert unlocked.status_code == 200
    async with auth_session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "locked@example.com")
        )
        assert user and user.failed_login_count == 0 and user.locked_until is None


async def test_rate_limit_has_retry_after(
    auth_client: AsyncClient,
) -> None:
    responses = []
    for _ in range(6):
        responses.append(
            await auth_client.post(
                "/api/v1/auth/login",
                json={"email": "rate-limit@example.com", "password": PASSWORD},
            )
        )
    limited = responses[-1]
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1
    reset_rate_limiter()
    resend_responses = [
        await auth_client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "resend-limit@example.com"},
        )
        for _ in range(6)
    ]
    assert resend_responses[-1].status_code == 429
    assert int(resend_responses[-1].headers["Retry-After"]) >= 1


async def test_register_rate_limit_is_per_ip(
    auth_client: AsyncClient,
) -> None:
    responses = [
        await register(auth_client, f"register-{index}@example.com")
        for index in range(6)
    ]
    assert all(response.status_code == 202 for response in responses[:5])
    assert responses[5].status_code == 429
    assert responses[5].json()["error"]["code"] == "rate_limited"
    assert int(responses[5].headers["Retry-After"]) >= 1


async def test_email_templates_bilingual_links_and_sender_failure_is_nonfatal(
    auth_client: AsyncClient,
    captured_email_sender: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    for locale, direction in (("en", "ltr"), ("fa", "rtl")):
        for kind in (
            "verify_email",
            "reset_password",
            "account_exists",
            "password_changed",
            "temporarily_locked",
        ):
            email = build_auth_email(
                locale,
                kind,
                "http://localhost:3000/fa/reset-password?token=sample-secret-token",
            )
            assert f'dir="{direction}"' in email.html
            assert not re.search(r"[۰-۹]", email.text)
            if locale == "fa" and kind == "temporarily_locked":
                assert "15" in email.text
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "email-fail@example.com",
            "password": PASSWORD,
            "locale": "fa",
        },
    )
    captured_email_sender.fail = True
    failure = await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "email-fail@example.com"},
    )
    assert failure.status_code == 202
    assert "Background email delivery failed" in caplog.text
    assert "email-fail@example.com" not in caplog.text
    assert "token=" not in caplog.text
    assert PASSWORD not in caplog.text


async def test_google_oauth_unconfigured_and_verified_link_create_refuse(
    auth_client: AsyncClient,
    auth_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_routes, "google_is_configured", lambda: False)
    for path in (
        "/api/v1/auth/google/login",
        "/api/v1/auth/google/callback",
    ):
        response = await auth_client.get(path)
        assert response.status_code == 501
        assert response.json()["error"]["code"] == "oauth_not_configured"

    monkeypatch.setattr(auth_routes, "google_is_configured", lambda: True)
    start = await auth_client.get(
        "/api/v1/auth/google/login",
        follow_redirects=False,
    )
    assert start.status_code == 302
    authorization_query = parse_qs(urlparse(start.headers["location"]).query)
    assert "code_challenge" in authorization_query
    assert authorization_query["code_challenge_method"] == ["S256"]
    assert len(start.headers.get_list("set-cookie")) == 1
    assert "httponly" in start.headers["set-cookie"].lower()

    existing_id = uuid4()
    async with auth_session_factory() as session:
        session.add(User(id=existing_id, email="link@example.com", password_hash=None))
        await session.commit()

    async def finish_google_callback(
        email: str, subject: str, verified: bool, locale: str = "fa"
    ):
        state = "test-state"
        nonce = "test-nonce"
        verifier = "test-verifier"
        cookie = jwt.encode(
            {
                "state": state,
                "nonce": nonce,
                "verifier": verifier,
                "locale": locale,
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            settings.jwt_secret,
            algorithm="HS256",
        )

        async def exchange(code: str, code_verifier: str, expected_nonce: str):
            assert code == "mock-code"
            assert code_verifier == verifier
            assert expected_nonce == nonce
            return {
                "sub": subject,
                "email": email,
                "email_verified": verified,
            }

        monkeypatch.setattr(auth_routes, "exchange_google_code", exchange)
        auth_client.cookies.set(
            GOOGLE_STATE_COOKIE,
            cookie,
            path="/api/v1/auth/google",
        )
        return await auth_client.get(
            "/api/v1/auth/google/callback",
            params={"state": state, "code": "mock-code"},
            follow_redirects=False,
        )

    linked = await finish_google_callback("link@example.com", "google-sub-1", True)
    assert linked.status_code == 303
    assert linked.headers["location"].endswith("/en/auth/callback")
    async with auth_session_factory() as session:
        linked_user = await session.get(User, existing_id)
        account = await session.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider_account_id == "google-sub-1"
            )
        )
    assert linked_user and linked_user.email_verified_at is not None
    assert account and account.user_id == existing_id

    created = await finish_google_callback(
        "new-google@example.com", "google-sub-2", True
    )
    assert created.status_code == 303
    async with auth_session_factory() as session:
        google_user = await session.scalar(
            select(User).where(User.email == "new-google@example.com")
        )
    assert google_user and google_user.password_hash is None

    refused = await finish_google_callback(
        "unverified@example.com", "google-sub-3", False
    )
    assert refused.status_code == 303
    assert "error=oauth_failed" in refused.headers["location"]
    async with auth_session_factory() as session:
        absent = await session.scalar(
            select(User).where(User.email == "unverified@example.com")
        )
    assert absent is None
