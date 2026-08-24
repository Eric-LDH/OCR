"""全局限流模块（令牌桶算法，进程内实现）。

单机部署足够；如需多实例/分布式，可替换为基于 Redis 的令牌桶或 lua 脚本。
"""
from __future__ import annotations

import threading
import time


class TokenBucket:
    """令牌桶限流器，线程安全。"""

    def __init__(self, rate_per_second: float, capacity: int) -> None:
        self._rate = rate_per_second  # 每秒补充令牌数
        self._capacity = capacity  # 桶容量（最大突发）
        self._tokens = float(capacity)  # 当前令牌数
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def try_acquire(self, num: int = 1) -> bool:
        """尝试获取 num 个令牌，成功返回 True，失败（超限）返回 False。"""
        with self._lock:
            now = time.monotonic()
            # 补充令牌：rate * 流逝时间，且不超过容量
            self._tokens = min(self._capacity, self._tokens + self._rate * (now - self._last_refill))
            self._last_refill = now
            if self._tokens >= num:
                self._tokens -= num
                return True
            return False
