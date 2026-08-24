"""FastAPI 应用入口。"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.api.test_ui import router as test_ui_router
from app.core.config import settings
from app.core.exceptions import ApiError, ERR_INTERNAL, ERR_INVALID_REQUEST
from app.core.signature import SignatureAuthError

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="安全 OCR 识别接口（HMAC-SHA256 签名鉴权 + 全局限流）",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """为每个请求注入 request_id，便于排查与统一返回。"""
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("未捕获的异常，request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "内部服务错误",
                "request_id": request_id,
                "data": None,
            },
        )
    response.headers["X-Request-Id"] = request_id
    return response


# ---------- 全局异常处理 ----------

@app.exception_handler(SignatureAuthError)
async def signature_auth_error_handler(request: Request, exc: SignatureAuthError):
    return JSONResponse(
        status_code=401,
        content={
            "code": 401,
            "message": exc.message,
            "request_id": getattr(request.state, "request_id", ""),
            "data": None,
        },
    )


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.message,
            "request_id": exc.request_id or getattr(request.state, "request_id", ""),
            "data": None,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": str(exc.detail),
            "request_id": getattr(request.state, "request_id", ""),
            "data": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": ERR_INVALID_REQUEST,
            "request_id": getattr(request.state, "request_id", ""),
            "data": {"detail": exc.errors()},
        },
    )


@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok", "app": settings.app_name}


app.include_router(api_router, prefix="/api/v1")

# 测试界面（仅本地测试；生产请通过 ENABLE_TEST_UI=false 关闭）
if settings.enable_test_ui:
    app.include_router(test_ui_router, prefix="/api/v1")
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/test", StaticFiles(directory=static_dir, html=True), name="test-ui")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
