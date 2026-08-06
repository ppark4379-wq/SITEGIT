from fastapi import APIRouter

from .routes import auth, health, policies, state

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(state.router)
api_router.include_router(policies.router)
