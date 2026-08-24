"""OCR 识别接口路由。"""
from __future__ import annotations

import io
import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile
from PIL import Image

from app.core.config import settings
from app.core.exceptions import (
    ApiError,
    ERR_FILE_TOO_LARGE,
    ERR_IMAGE_DECODE_FAILED,
    ERR_OCR_FAILED,
    ERR_RATE_LIMITED,
    ERR_UNSUPPORTED_FILE_TYPE,
)
from app.core.ratelimit import TokenBucket
from app.core.signature import verify_signature
from app.services.ocr_service import ocr_service

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局限流令牌桶
_rate_bucket = TokenBucket(settings.rate_limit_per_second, settings.rate_limit_burst)


async def signature_dependency(request: Request) -> str:
    """签名校验依赖，成功返回 appid。未启用签名时可跳过。"""
    if not settings.enable_signature:
        return "anonymous"
    return verify_signature(request)


def _validate_file_size(size: int) -> None:
    if size <= 0:
        raise ApiError(400, ERR_FILE_TOO_LARGE, "文件为空")
    if size > settings.max_upload_size:
        raise ApiError(
            400,
            ERR_FILE_TOO_LARGE,
            f"文件过大，允许的最大大小为 {settings.max_upload_size // 1024}KB",
        )


def _validate_file_type(filename: str, content_type: str | None) -> None:
    ext = (filename or "").lower()
    if not any(ext.endswith(e) for e in settings.allowed_image_exts):
        raise ApiError(400, ERR_UNSUPPORTED_FILE_TYPE, "不支持的图片类型，仅允许 jpg/png/webp/bmp")
    # content-type 检查（FastAPI 可能解析不出 content_type，此时跳过）
    if content_type and content_type.split(";")[0].strip() not in settings.allowed_image_types:
        raise ApiError(400, ERR_UNSUPPORTED_FILE_TYPE, f"不支持的 MIME 类型: {content_type}")


def _decode_image(raw: bytes) -> Image.Image:
    """解码图片，校验格式合法。"""
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        logger.warning("图片解码失败: %s", e)
        raise ApiError(400, ERR_IMAGE_DECODE_FAILED, "图片解码失败，请上传有效图片")


@router.post("/ocr")
async def ocr_recognize(
    request: Request,
    file: UploadFile = File(...),
    appid: str = Depends(signature_dependency),
) -> dict:
    """通用 OCR 识别。

    - 请求方式: POST，Content-Type: multipart/form-data
    - 表单字段: file（图片文件，单张）
    - 鉴权头: X-TC-AppId / X-TC-Timestamp / X-TC-Nonce / X-TC-Signature
    """
    request_id = getattr(request.state, "request_id", "")

    # 全局限流
    if not _rate_bucket.try_acquire():
        raise ApiError(429, ERR_RATE_LIMITED, "请求过于频繁，请稍后再试", request_id)

    # 读取文件（限制大小，避免内存耗尽）
    raw = await file.read(settings.max_upload_size + 1)
    _validate_file_size(len(raw))
    _validate_file_type(file.filename or "", file.content_type)

    # 预解码校验（占用低，先确认是合法图片）
    _decode_image(raw)

    # 执行 OCR
    try:
        result = ocr_service.recognize(raw)
    except Exception as e:
        logger.exception("OCR 识别失败，request_id=%s", request_id)
        raise ApiError(500, ERR_OCR_FAILED, "OCR 识别失败", request_id)

    return {
        "code": 200,
        "message": "success",
        "request_id": request_id,
        "data": result,
    }
