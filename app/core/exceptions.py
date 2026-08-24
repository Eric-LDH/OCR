"""统一异常定义与响应结构。"""
from __future__ import annotations

from pydantic import BaseModel

from app.core.config import settings


class ApiError(Exception):
    """业务异常，携带 HTTP 状态码与错误码。"""

    def __init__(
        self, status_code: int, code: str, message: str, request_id: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id


# 通用错误码
ERR_INVALID_REQUEST = "InvalidRequest"
ERR_FILE_TOO_LARGE = "FileTooLarge"
ERR_UNSUPPORTED_FILE_TYPE = "UnsupportedFileType"
ERR_IMAGE_DECODE_FAILED = "ImageDecodeFailed"
ERR_OCR_FAILED = "OcrFailed"
ERR_RATE_LIMITED = "RateLimited"
ERR_INTERNAL = "InternalError"


class ApiResponse(BaseModel):
    """统一响应结构（对齐大厂：code/requestId 在外层）。"""

    code: int
    message: str
    request_id: str
    data: dict | None = None


def error_response(code: int, message: str, request_id: str) -> dict:
    return ApiResponse(code=code, message=message, request_id=request_id, data=None).model_dump()


def app_name() -> str:
    return settings.app_name
