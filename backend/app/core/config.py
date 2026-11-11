from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    database_url: str
    app_env: str = "development"
    jwt_secret: str = ""
    access_token_minutes: int = Field(default=15, gt=0)
    refresh_token_days: int = Field(default=30, gt=0)
    cookie_secure: bool = False
    cookie_domain: str | None = None
    frontend_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_auth_secret_outside_development(self) -> "Settings":
        if self.app_env.strip().lower() not in {"development", "dev", "test", "local"}:
            normalized_secret = self.jwt_secret.strip().lower().replace("_", "-")
            if (
                len(self.jwt_secret) < 32
                or "placeholder" in normalized_secret
                or "change-me" in normalized_secret
                or "replace-this" in normalized_secret
                or "your-" in normalized_secret
            ):
                raise ValueError(
                    "JWT_SECRET must be a non-placeholder value of at least "
                    "32 characters outside development"
                )
        return self


settings = Settings()  # type: ignore[call-arg]  # Loaded from root .env or environment.
