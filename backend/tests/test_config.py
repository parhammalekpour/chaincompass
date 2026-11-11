import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    "secret",
    ["", "PLACEHOLDER_SECRET_FOR_PRODUCTION", "change-me-with-a-long-but-unsafe-value"],
)
def test_non_development_requires_non_placeholder_jwt_secret(secret: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            app_env="production",
            jwt_secret=secret,
        )


def test_development_auth_settings_have_safe_defaults() -> None:
    config = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        app_env="development",
        jwt_secret="",
    )
    assert config.access_token_minutes == 15
    assert config.refresh_token_days == 30
    assert config.cookie_secure is False
    assert config.cookie_domain is None


def test_non_development_requires_smtp_configuration() -> None:
    with pytest.raises(ValidationError, match="SMTP_HOST"):
        Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            app_env="production",
            jwt_secret="SecureProductionJwtSecretValue0123456789",
            smtp_host="PLACEHOLDER_SMTP_HOST",
            smtp_user="PLACEHOLDER_SMTP_USER",
            smtp_password="PLACEHOLDER_SMTP_PASSWORD",
            smtp_from="PLACEHOLDER_SMTP_FROM",
        )
