"""配置加载模块：从 config.yaml 加载，并支持环境变量覆盖关键项。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 项目根目录（本文件位于 app/core/ 下）
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"


class Settings:
    """服务配置对象。"""

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        raw: dict[str, Any] = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                if isinstance(loaded, dict):
                    raw = loaded

        self.app_name: str = self._get(raw, "APP_NAME", "ocr-api")
        self.host: str = self._get(raw, "HOST", "0.0.0.0")
        self.port: int = self._get(raw, "PORT", 8000)

        self.signature_clock_skew: int = int(
            os.getenv("OCR_SIGNATURE_CLOCK_SKEW", self._get(raw, "SIGNATURE_CLOCK_SKEW", 300))
        )
        self.nonce_ttl: int = int(os.getenv("OCR_NONCE_TTL", self._get(raw, "NONCE_TTL", 300)))
        self.enable_signature: bool = (
            os.getenv("OCR_ENABLE_SIGNATURE", str(self._get(raw, "ENABLE_SIGNATURE", True))).lower()
            == "true"
        )
        # 测试界面开关（仅本地/开发使用，生产务必关闭）
        self.enable_test_ui: bool = (
            os.getenv("OCR_ENABLE_TEST_UI", str(self._get(raw, "ENABLE_TEST_UI", True))).lower()
            == "true"
        )

        self.rate_limit_per_second: int = int(
            os.getenv("OCR_RATE_LIMIT_PER_SECOND", self._get(raw, "RATE_LIMIT_PER_SECOND", 2))
        )
        self.rate_limit_burst: int = int(
            os.getenv("OCR_RATE_LIMIT_BURST", self._get(raw, "RATE_LIMIT_BURST", 5))
        )

        self.max_upload_size: int = int(
            os.getenv("OCR_MAX_UPLOAD_SIZE", self._get(raw, "MAX_UPLOAD_SIZE", 5242880))
        )
        self.allowed_image_types: list[str] = list(
            self._get(raw, "ALLOWED_IMAGE_TYPES", ["image/jpeg", "image/png", "image/webp", "image/bmp"])
        )
        self.allowed_image_exts: list[str] = list(
            self._get(raw, "ALLOWED_IMAGE_EXTS", [".jpg", ".jpeg", ".png", ".webp", ".bmp"])
        )

        self.ocr_use_gpu: bool = self._get(raw, "OCR_USE_GPU", False)
        self.ocr_return_score: bool = self._get(raw, "OCR_RETURN_SCORE", True)
        self.ocr_return_details: bool = self._get(raw, "OCR_RETURN_DETAILS", True)

        self.log_level: str = os.getenv("OCR_LOG_LEVEL", self._get(raw, "LOG_LEVEL", "INFO"))

        # 密钥：优先从环境变量 OCR_APP_SECRETS 读取（逗号分隔 appid:secret）
        secrets = self._load_secrets(raw)
        self.app_secrets: dict[str, str] = secrets

    @staticmethod
    def _get(raw: dict[str, Any], key: str, default: Any) -> Any:
        return raw.get(key, default)

    @staticmethod
    def _parse_secrets_str(raw: str) -> dict[str, str]:
        """解析形如 'appid1:secret1,appid2:secret2' 的字符串。"""
        result: dict[str, str] = {}
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            if ":" not in item:
                raise ValueError(f"密钥项格式错误，应为 appid:secret，实际为: {item!r}")
            appid, secret = item.split(":", 1)
            appid = appid.strip()
            secret = secret.strip()
            if not appid or not secret:
                raise ValueError(f"密钥项 appid/secret 不能为空: {item!r}")
            result[appid] = secret
        return result

    def _load_secrets(self, raw: dict[str, Any]) -> dict[str, str]:
        env_secrets = os.getenv("OCR_APP_SECRETS")
        if env_secrets and env_secrets.strip():
            return self._parse_secrets_str(env_secrets)

        secrets: dict[str, str] = {}
        configured = self._get(raw, "APP_SECRETS", [])
        for item in configured or []:
            appid = str(item.get("appid", "")).strip()
            secret = str(item.get("secret", "")).strip()
            if appid and secret:
                secrets[appid] = secret
        return secrets

    def get_secret(self, appid: str) -> str | None:
        """根据 appid 获取对应的 secret，不存在返回 None。"""
        return self.app_secrets.get(appid)


settings = Settings()
