from fastapi import APIRouter

from config import IS_DEV
from routers.v1 import health, search

router = APIRouter(prefix="/v1")

router.include_router(health.router)
router.include_router(search.router)

# Placeholder example routes only in APP_ENV=dev
if IS_DEV:
    from routers.v1 import example

    router.include_router(example.router)
