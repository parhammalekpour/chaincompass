"""Import model classes here so Alembic can discover their metadata."""

from app.db.models.auth import EmailToken, OAuthAccount, RefreshToken, User
from app.db.models.health import HealthScore, MarketRegime, RiskFlag
from app.db.models.ingestion import (
    Chain,
    ComputedFeature,
    DataSource,
    IngestionRun,
    MetricDefinition,
    Observation,
    RpcProbe,
    SeriesCoverage,
)

__all__ = [
    "Chain",
    "ComputedFeature",
    "DataSource",
    "EmailToken",
    "HealthScore",
    "IngestionRun",
    "MarketRegime",
    "MetricDefinition",
    "OAuthAccount",
    "Observation",
    "RpcProbe",
    "RiskFlag",
    "RefreshToken",
    "SeriesCoverage",
    "User",
]
