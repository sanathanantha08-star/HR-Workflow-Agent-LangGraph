from fastapi import APIRouter
from api.endpoints.workflow import router as workflow_router
from api.endpoints.hitl import router as hitl_router
from api.endpoints.webhooks import router as webhooks_router
from api.endpoints.debug import router as debug_router

api_router = APIRouter(prefix="/api")
api_router.include_router(workflow_router)
api_router.include_router(hitl_router)
api_router.include_router(webhooks_router)
api_router.include_router(debug_router)
