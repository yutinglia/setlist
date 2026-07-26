from fastapi import APIRouter

from routers.v1 import auth, health, report, search, updater

router = APIRouter(prefix="/v1")

router.include_router(auth.router)
router.include_router(health.router)
router.include_router(report.router)
router.include_router(search.router)
router.include_router(updater.router)
