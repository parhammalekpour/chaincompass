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


def test_development_auth_settings_have_safe_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_name in (
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_DAILY_TOKEN_BUDGET",
    ):
        monkeypatch.delenv(env_name, raising=False)

    config = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
        app_env="development",
        jwt_secret="",
    )
    assert config.access_token_minutes == 15
    assert config.refresh_token_days == 30
    assert config.cookie_secure is False
    assert config.cookie_domain is None
    assert config.llm_provider == "none"
    assert config.llm_daily_token_budget == 200_000


def test_llm_settings_reject_unknown_provider_and_nonpositive_budget() -> None:
    base = {
        "database_url": "postgresql+asyncpg://test:test@localhost/test",
        "app_env": "development",
    }

    with pytest.raises(ValidationError):
        Settings(**base, llm_provider="unknown")
    with pytest.raises(ValidationError):
        Settings(**base, llm_daily_token_budget=0)


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
