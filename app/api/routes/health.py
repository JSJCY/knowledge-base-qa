"""系统级路由：健康检查与服务信息。"""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["系统"])


@router.get("/health", summary="健康检查")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/", summary="服务信息")
def service_info() -> dict[str, object]:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "llm_enabled": settings.llm_enabled,
    }
