from fastapi import APIRouter

from app.api.v1 import templates, documents, knowledge, qcc

api_router = APIRouter()

api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(qcc.router, prefix="/qcc", tags=["qcc"])
