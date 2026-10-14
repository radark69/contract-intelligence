from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.economics import router as economics_router
from app.api.extraction import router as extraction_router
from app.api.facts import router as facts_router
from app.api.obligations import router as obligations_router
from app.api.playbook import router as playbook_router
from app.api.reports import router as reports_router
from app.auth import router as auth_router
from app.api.risk import router as risk_router

router = APIRouter()
router.include_router(documents_router)
router.include_router(economics_router)
router.include_router(extraction_router)
router.include_router(facts_router)
router.include_router(obligations_router)
router.include_router(playbook_router)
router.include_router(reports_router)
router.include_router(auth_router)
router.include_router(risk_router)
