"""Import model classes here so Alembic can discover their metadata."""

from app.db.models.auth import EmailToken, OAuthAccount, RefreshToken, User

__all__ = ["EmailToken", "OAuthAccount", "RefreshToken", "User"]
