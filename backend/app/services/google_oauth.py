from typing import Any
from urllib.parse import urlparse

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError

from app.core.config import settings

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
GOOGLE_REDIRECT_URI = (
    f"{settings.frontend_origin.rstrip('/')}/api/v1/auth/google/callback"
)


def google_is_configured() -> bool:
    values = (settings.google_client_id, settings.google_client_secret)
    return all(
        value.strip()
        and not any(
            marker in value.lower()
            for marker in ("placeholder", "your_", "change-me", "replace-this")
        )
        for value in values
    )


async def create_google_authorization_url(
    state: str,
    nonce: str,
    code_verifier: str,
) -> str:
    async with AsyncOAuth2Client(
        settings.google_client_id,
        settings.google_client_secret,
        scope="openid email profile",
        code_challenge_method="S256",
    ) as client:
        url, _ = client.create_authorization_url(
            GOOGLE_AUTHORIZATION_ENDPOINT,
            state=state,
            code_verifier=code_verifier,
            code_challenge_method="S256",
            nonce=nonce,
            redirect_uri=GOOGLE_REDIRECT_URI,
            access_type="online",
        )
    return str(url)


async def exchange_google_code(
    code: str,
    code_verifier: str,
    nonce: str,
) -> dict[str, Any]:
    async with AsyncOAuth2Client(
        settings.google_client_id,
        settings.google_client_secret,
        scope="openid email profile",
    ) as client:
        token = await client.fetch_token(
            GOOGLE_TOKEN_ENDPOINT,
            code=code,
            code_verifier=code_verifier,
            redirect_uri=GOOGLE_REDIRECT_URI,
            include_client_id=True,
        )

    encoded_id_token = token.get("id_token")
    if not isinstance(encoded_id_token, str):
        raise ValueError("Google response did not contain an ID token")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(GOOGLE_JWKS_ENDPOINT)
        response.raise_for_status()
        key_set = JsonWebKey.import_key_set(response.json())

    try:
        claims = jwt.decode(
            encoded_id_token,
            key_set,
            claims_options={
                "iss": {"essential": True, "values": list(GOOGLE_ISSUERS)},
                "aud": {"essential": True, "value": settings.google_client_id},
                "nonce": {"essential": True, "value": nonce},
            },
        )
        claims.validate()
    except JoseError as exc:
        raise ValueError("Google ID token validation failed") from exc

    if urlparse(GOOGLE_REDIRECT_URI).scheme != "https" and settings.app_env not in {
        "development",
        "dev",
        "test",
        "local",
    }:
        raise ValueError("Google OAuth redirect URI must use HTTPS")
    return dict(claims)
