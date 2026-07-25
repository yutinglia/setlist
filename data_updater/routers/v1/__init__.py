from fastapi import APIRouter

from routers.v1 import health, search, updater

router = APIRouter(prefix="/v1")

router.include_router(health.router)
router.include_router(search.router)
router.include_router(updater.router)
