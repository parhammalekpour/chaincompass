import logging
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]
    version: str


@router.get("/health", response_model=HealthResponse)
async def get_health(
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        logger.warning("Database health check failed", exc_info=True)
        return HealthResponse(status="degraded", db="down", version=__version__)

    return HealthResponse(status="ok", db="ok", version=__version__)
