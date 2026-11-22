from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.agent import router as agent_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.public import router as public_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(public_router)
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(agent_router)
api_router.include_router(alerts_router)
api_router.include_router(admin_router, tags=["admin"])
