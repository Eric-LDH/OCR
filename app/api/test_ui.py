"""测试界面专用端点。

仅用于本地/开发测试（前端浏览器无法方便地计算签名），**不作为生产对外接口**。
受以下保护：
  - 由 ENABLE_TEST_UI 配置项控制开关（生产应关闭）
  - 同样经过全局限流
  - 同样经过文件大小 / 类型 / 解码校验

生产环境请使用带签名的正式接口 POST /api/v1/ocr。
"""
from __future__ import annotations

import io
import logging

from fastapi import APIRouter, File, Request, UploadFile

from PIL import Image

from app.core.config import settings
from app.core.exceptions import (
    ApiError,
    ERR_FILE_TOO_LARGE,
    ERR_IMAGE_DECODE_FAILED,
    ERR_RATE_LIMITED,
    ERR_UNSUPPORTED_FILE_TYPE,
)
from app.core.ratelimit import TokenBucket
from app.services.ocr_service import ocr_service

logger = logging.getLogger(__name__)

router = APIRouter()

_test_rate_bucket = TokenBucket(settings.rate_limit_per_second, settings.rate_limit_burst)


@router.post("/test/ocr")
async def test_ocr(request: Request, file: UploadFile = File(...)) -> dict:
    """测试界面识别端点（无签名，仅供本地测试）。"""
    request_id = getattr(request.state, "request_id", "")

    if not settings.enable_test_ui:
        raise ApiError(403, "Forbidden", "测试界面未开启（ENABLE_TEST_UI）", request_id)

    if not _test_rate_bucket.try_acquire():
        raise ApiError(429, ERR_RATE_LIMITED, "请求过于频繁，请稍后再试", request_id)

    raw = await file.read(settings.max_upload_size + 1)
    if len(raw) <= 0:
        raise ApiError(400, ERR_FILE_TOO_LARGE, "文件为空", request_id)
    if len(raw) > settings.max_upload_size:
        raise ApiError(400, ERR_FILE_TOO_LARGE, "文件过大", request_id)
    ext = (file.filename or "").lower()
    if not any(ext.endswith(e) for e in settings.allowed_image_exts):
        raise ApiError(400, ERR_UNSUPPORTED_FILE_TYPE, "不支持的图片类型", request_id)
    if file.content_type and file.content_type.split(";")[0].strip() not in settings.allowed_image_types:
        raise ApiError(400, ERR_UNSUPPORTED_FILE_TYPE, f"不支持的 MIME 类型: {file.content_type}", request_id)

    # 预解码校验
    try:
        Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        logger.warning("测试界面图片解码失败: %s", e)
        raise ApiError(400, ERR_IMAGE_DECODE_FAILED, "图片解码失败，请上传有效图片", request_id)

    try:
        result = ocr_service.recognize(raw)
    except Exception as e:
        logger.exception("测试界面 OCR 识别失败，request_id=%s", request_id)
        raise ApiError(500, "OcrFailed", "OCR 识别失败", request_id)

    return {
        "code": 200,
        "message": "success",
        "request_id": request_id,
        "data": result,
    }
