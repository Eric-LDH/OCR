"""签名鉴权模块。

实现对齐腾讯云 / 阿里云等大厂风格的对称密钥签名校验：

请求头（约定）：
    X-TC-AppId     调用方 AppId
    X-TC-Timestamp 调用时间戳（Unix 秒）
    X-TC-Nonce     随机字符串（防重放）
    X-TC-Signature HMAC-SHA256 签名

签名串格式（HMAC-SHA256，密钥为 AppSecret）：
    {HttpMethod}\n{Path}\n{Timestamp}\n{Nonce}

服务端校验流程：
    1. 参数完整性校验
    2. AppId 是否存在
    3. 时间戳偏差校验（防重放，超时拒绝）
    4. Nonce 唯一性校验（同一 AppId+Nonce 在 TTL 内只能使用一次）
    5. 使用 AppSecret 计算签名并比对（恒定时间比较，防时序攻击）
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

from starlette.requests import Request

from app.core.config import settings
from app.core.secret import secret_manager

# 签名字段在请求头中的名称
HEADER_APPID = "x-tc-appid"
HEADER_TIMESTAMP = "x-tc-timestamp"
HEADER_NONCE = "x-tc-nonce"
HEADER_SIGNATURE = "x-tc-signature"

# 错误码（供业务层统一返回）
ERR_MISSING_HEADERS = "SignatureMissingHeaders"
ERR_INVALID_APPID = "SignatureInvalidAppId"
ERR_EXPIRED_TIMESTAMP = "SignatureExpired"
ERR_REPLAYED_NONCE = "SignatureNonceReused"
ERR_SIGNATURE_MISMATCH = "SignatureMismatch"


def compute_signature(
    secret: str, http_method: str, path: str, timestamp: str, nonce: str
) -> str:
    """根据规范计算 HMAC-SHA256 签名（返回十六进制小写字符串）。"""
    message = f"{http_method}\n{path}\n{timestamp}\n{nonce}"
    digest = hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return digest


def _constant_time_compare(a: str, b: str) -> bool:
    """恒定时间字符串比较，避免时序侧信道。"""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class NonceCache:
    """Nonce 去重缓存。

    单机部署使用进程内存字典即可；若需多副本/多实例，可替换为 Redis（key: nonce, value: appid）。
    为控制内存，TTL 过期条目在每次写入时惰性清理。
    """

    def __init__(self) -> None:
        # nonce -> expire_at(绝对时间戳)
        self._store: dict[str, float] = {}

    def _purge(self, now: float) -> None:
        expired = [k for k, v in self._store.items() if v <= now]
        for k in expired:
            self._store.pop(k, None)

    def has(self, nonce: str) -> bool:
        return nonce in self._store

    def set(self, nonce: str, expire_after: float, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        self._purge(now)
        self._store[nonce] = now + expire_after


nonce_cache = NonceCache()


class SignatureAuthError(Exception):
    """签名校验失败异常。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def verify_signature(request: Request, *, body_payload: Optional[str] = None) -> str:
    """校验请求签名，成功返回 AppId，失败抛出 SignatureAuthError。

    说明：由于当前使用 multipart/form-data 上传图片，请求体为二进制文件流，
    且大厂实践通常不将整个文件内容纳入签名串（文件体积大、解析成本高），
    故签名基于“请求方法 + 路径 + 时间戳 + Nonce”。如需将请求参数纳入签名，
    可扩展 body_payload 参与签名。
    """
    appid = request.headers.get(HEADER_APPID, "")
    timestamp_str = request.headers.get(HEADER_TIMESTAMP, "")
    nonce = request.headers.get(HEADER_NONCE, "")
    signature = request.headers.get(HEADER_SIGNATURE, "")

    # 1. 参数完整性
    if not appid or not timestamp_str or not nonce or not signature:
        raise SignatureAuthError(ERR_MISSING_HEADERS, "缺少签名所需的请求头参数")

    # 2. AppId 合法性
    if not secret_manager.appid_exists(appid):
        raise SignatureAuthError(ERR_INVALID_APPID, f"无效的 AppId: {appid}")

    # 3. 时间戳偏差（防重放）
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise SignatureAuthError(ERR_EXPIRED_TIMESTAMP, "时间戳格式非法")
    now = time.time()
    if abs(now - timestamp) > settings.signature_clock_skew:
        raise SignatureAuthError(ERR_EXPIRED_TIMESTAMP, "请求时间戳已过期")

    # 4. Nonce 唯一性（同一 Nonce 在 TTL 内不能复用）
    cache_key = f"{appid}:{nonce}"
    if nonce_cache.has(cache_key):
        raise SignatureAuthError(ERR_REPLAYED_NONCE, "Nonce 已被使用，疑似重放攻击")
    nonce_cache.set(cache_key, settings.nonce_ttl)

    # 5. 签名比对
    secret = secret_manager.resolve_secret(appid)
    expected = compute_signature(secret, request.method, request.url.path, timestamp_str, nonce)
    if not _constant_time_compare(expected, signature):
        raise SignatureAuthError(ERR_SIGNATURE_MISMATCH, "签名校验失败")

    return appid
