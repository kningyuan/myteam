"""Hub API 域路由聚合。"""

from fastapi import APIRouter

from hub.api.routes.agents import router as agents_router
from hub.api.routes.chat import router as chat_router
from hub.api.routes.config import router as config_router
from hub.api.routes.groups import router as groups_router
from hub.api.routes.projects import router as projects_router
from hub.api.routes.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(agents_router)
api_router.include_router(projects_router)
api_router.include_router(config_router)
api_router.include_router(chat_router)
api_router.include_router(groups_router)
api_router.include_router(workflows_router)
