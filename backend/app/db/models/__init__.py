"""Import model classes here so Alembic can discover their metadata."""

from app.db.models.auth import RefreshToken, User

__all__ = ["RefreshToken", "User"]
