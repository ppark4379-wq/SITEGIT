from fastapi import APIRouter

from .routes import auth, health, isaac, policies, site_plans, state, work_packages

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(state.router)
api_router.include_router(policies.router)
api_router.include_router(isaac.router)
api_router.include_router(work_packages.router)
api_router.include_router(site_plans.router)
