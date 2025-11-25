from fastapi import APIRouter
from routers.v1 import example, health

router = APIRouter(prefix="/v1")

router.include_router(example.router)
router.include_router(health.router)
