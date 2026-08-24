"""调用方对接示例（Python 版）。

展示如何生成签名并调用 OCR 接口。
运行前请安装依赖：pip install requests
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from pathlib import Path

import requests

# 配置（替换为你自己的值）
BASE_URL = "http://127.0.0.1:8000"
APP_ID = "demo"
APP_SECRET = "CHANGE_ME_demo_secret_key_please_replace"


def build_signature(http_method: str, path: str, timestamp: str, nonce: str) -> str:
    """生成签名，算法须与服务端一致：
    message = "{HTTP方法}\\n{路径}\\n{时间戳}\\n{Nonce}"
    signature = HMAC-SHA256(message, key=AppSecret) 十六进制小写
    """
    message = f"{http_method}\n{path}\n{timestamp}\n{nonce}"
    return hmac.new(
        APP_SECRET.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def ocr_recognize(image_path: str | Path) -> dict:
    image_path = Path(image_path)
    path = "/api/v1/ocr"
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())

    signature = build_signature("POST", path, timestamp, nonce)

    headers = {
        "X-TC-AppId": APP_ID,
        "X-TC-Timestamp": timestamp,
        "X-TC-Nonce": nonce,
        "X-TC-Signature": signature,
    }

    with open(image_path, "rb") as f:
        files = {"file": (image_path.name, f, "image/jpeg")}
        resp = requests.post(
            f"{BASE_URL}{path}", headers=headers, files=files, timeout=60
        )

    return resp.json()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python client_sdk.py <图片路径>")
        sys.exit(1)

    result = ocr_recognize(sys.argv[1])
    print("HTTP 状态:", 200 if result.get("code") == 200 else result.get("code"))
    if result.get("code") == 200:
        data = result["data"]
        print("识别文本:\n", data["text"])
        print("\n文字块坐标:")
        for line in data["lines"]:
            print(f"  {line['text']} (conf={line.get('confidence')}, box={line['box']})")
    else:
        print("调用失败:", result)
