"""FastAPI 应用入口。

挂载 REST 路由、静态前端、统一异常处理与生命周期容器。
启动：``python -m uvicorn app.main:app --reload``
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_approval,
    routes_auth,
    routes_chat,
    routes_evaluation,
    routes_evaluation_ext,
    routes_handoff,
    routes_health,
    routes_knowledge,
    routes_learning,
    routes_notifications,
    routes_session,
    routes_students,
    routes_workflow,
)
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.exceptions import CampusAgentError
from app.deps import AppContainer, reset_container
from app.core.logging import get_logger


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    settings = get_settings()
    logger = get_logger("app")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """启动时构建容器，关闭时清理全局引用。"""
        reset_container()
        container = AppContainer(settings)
        app.state.container = container
        logger.info(f"服务启动: {settings.app_name} v{settings.app_version}")
        try:
            yield
        finally:
            close = getattr(container.campus_service, "aclose", None)
            if close is not None:
                await close()
            logger.info("服务关闭")
            reset_container()

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api/v1"
    app.include_router(routes_health.router, prefix=api_prefix)
    app.include_router(routes_auth.router, prefix=api_prefix)
    for router in (
        routes_session.router,
        routes_chat.router,
        routes_workflow.router,
        routes_handoff.router,
        routes_approval.router,
        routes_knowledge.router,
        routes_evaluation.router,
        routes_evaluation_ext.router,
        routes_learning.router,
        routes_notifications.router,
        routes_students.router,
    ):
        app.include_router(
            router,
            prefix=api_prefix,
            dependencies=[Depends(get_current_user)],
        )

    static_dir: Path = settings.static_dir
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        """返回单页工作台。"""
        index_file = static_dir / "index.html"
        return FileResponse(index_file)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        """避免浏览器请求图标产生 404。"""
        return Response(status_code=204)

    @app.exception_handler(CampusAgentError)
    async def handle_campus_error(request: Request, exc: CampusAgentError) -> JSONResponse:
        """把领域异常转换为统一错误结构。"""
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """请求参数校验失败。"""
        del request
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "请求参数校验失败",
                "detail": jsonable_encoder(exc.errors()),
            },
        )

    return app


app = create_app()
