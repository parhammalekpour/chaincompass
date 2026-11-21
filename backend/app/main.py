from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.providers.factory import create_configured_provider
from app.agent.providers.openai_compatible import OpenAICompatibleProvider
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, request_id_middleware
from app.db.session import engine


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        provider = getattr(application.state, "agent_provider", None)
        if isinstance(provider, OpenAICompatibleProvider):
            await provider.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(title="ChainCompass API", version="0.1.0", lifespan=lifespan)
    application.state.agent_provider = create_configured_provider()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    application.middleware("http")(request_id_middleware)
    register_exception_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
