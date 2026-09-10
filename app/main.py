"""FastAPI 应用入口。"""

from fastapi import FastAPI

from app.api.routes import health
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
    )
    application.include_router(health.router)
    return application


app = create_app()
