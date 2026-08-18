from fastapi import APIRouter
from .routes_core import router as core_router
from .routes_extra import router as extra_router

router = APIRouter()
router.include_router(core_router)
router.include_router(extra_router)
