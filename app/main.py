"""FastAPI 应用入口。"""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, documents, health, search
from app.core.config import get_settings
from app.core.db import init_db

logger = logging.getLogger("kb_qa.api")


def _error_payload(code: str, message: str, request_id: str, **extra: object) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "request_id": request_id, **extra}}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.include_router(health.router)
    application.include_router(documents.router)
    application.include_router(search.router)
    application.include_router(chat.router)
    request_times: dict[str, list[float]] = {}

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(str(exc.status_code), str(exc.detail), request_id),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "validation_error", "请求参数不合法", request_id, details=exc.errors()
            ),
        )

    @application.middleware("http")
    async def api_guard(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started_at = time.perf_counter()
        settings = get_settings()
        if request.url.path.startswith("/api/v1"):
            client_ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            recent = [value for value in request_times.get(client_ip, []) if now - value < 60]
            if len(recent) >= settings.rate_limit_per_minute:
                return JSONResponse(
                    status_code=429,
                    content=_error_payload("rate_limited", "请求过于频繁", request_id),
                )
            recent.append(now)
            request_times[client_ip] = recent
        if request.url.path.startswith("/api/v1") and settings.api_key:
            if request.headers.get("X-API-Key") != settings.api_key:
                return JSONResponse(
                    status_code=401,
                    content=_error_payload("unauthorized", "API Key 无效", request_id),
                )
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    # Web 前端（静态单页应用）：挂载在根路径，须在所有 API 路由注册之后
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        application.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return application


app = create_app()
