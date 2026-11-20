"""Import model classes here so Alembic can discover their metadata."""

from app.db.models.auth import EmailToken, OAuthAccount, RefreshToken, User
from app.db.models.ingestion import (
    Chain,
    DataSource,
    IngestionRun,
    MetricDefinition,
    Observation,
    RpcProbe,
    SeriesCoverage,
)

__all__ = [
    "Chain",
    "DataSource",
    "EmailToken",
    "IngestionRun",
    "MetricDefinition",
    "OAuthAccount",
    "Observation",
    "RpcProbe",
    "RefreshToken",
    "SeriesCoverage",
    "User",
]
