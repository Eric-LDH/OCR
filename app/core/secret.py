"""密钥管理模块。

当前实现为“静态配置”（从 config.yaml 或环境变量 OCR_APP_SECRETS 读取）。
为便于未来扩展为数据库/管理接口模式，这里提供统一封装：
    - 校验 appid 是否存在
    - 根据 appid 获取 secret
    - 预留密钥轮换接口

如需升级为数据库模式，只需替换内部存储实现，而不必改动调用方。
"""
from __future__ import annotations

import secrets as _secrets
from typing import Protocol

from app.core.config import settings


class SecretStore(Protocol):
    """密钥存储抽象接口。"""

    def get_secret(self, appid: str) -> str | None: ...

    def rotate(self, appid: str) -> str: ...


class StaticSecretStore:
    """静态配置密钥存储（当前默认实现）。"""

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        # secrets: appid -> secret
        self._secrets: dict[str, str] = secrets if secrets is not None else settings.app_secrets

    def get_secret(self, appid: str) -> str | None:
        return self._secrets.get(appid)

    def rotate(self, appid: str) -> str:
        """预留的密钥轮换接口（静态模式下不支持，抛出异常提示）。"""
        raise NotImplementedError(
            "静态配置模式下不支持动态轮换密钥。请通过修改 config.yaml 或 "
            "环境变量 OCR_APP_SECRETS 后重启服务来轮换密钥。"
        )

    def all_appids(self) -> list[str]:
        return list(self._secrets.keys())


class SecretManager:
    """密钥管理器门面，业务代码统一通过它访问密钥。"""

    def __init__(self, store: SecretStore | None = None) -> None:
        self._store: SecretStore = store or StaticSecretStore()

    def resolve_secret(self, appid: str) -> str | None:
        return self._store.get_secret(appid)

    def appid_exists(self, appid: str) -> bool:
        return self._store.get_secret(appid) is not None


# 全局单例
secret_manager = SecretManager()


def generate_secret(length: int = 32) -> str:
    """生成一个安全的随机 secret，用于配置/发放新密钥时使用。"""
    return _secrets.token_urlsafe(length)
