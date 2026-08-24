#!/usr/bin/env bash
# 调用方对接示例（Shell / curl 版）
# 生成签名并调用 OCR 接口。需要 openssl。
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
APP_ID="${APP_ID:-demo}"
APP_SECRET="${APP_SECRET:-CHANGE_ME_demo_secret_key_please_replace}"
IMAGE="${1:?用法: $0 <图片路径>}"

PATH_="/api/v1/ocr"
TIMESTAMP=$(date +%s)
NONCE=$(cat /proc/sys/kernel/random/uuid)   # 或使用 $RANDOM 组合随机字符串

# 拼接待签名串并计算 HMAC-SHA256（十六进制小写）
MESSAGE="${TIMESTAMP}${NONCE}${PATH_}"
# 注意：message 实际格式为 "POST\n/api/v1/ocr\n{ts}\n{nonce}"
MESSAGE="POST
${PATH_}
${TIMESTAMP}
${NONCE}"
SIGNATURE=$(printf '%s' "${MESSAGE}" | openssl dgst -sha256 -hmac "${APP_SECRET}" -hex | awk '{print $NF}')

curl -sS -X POST "${BASE_URL}${PATH_}" \
  -H "X-TC-AppId: ${APP_ID}" \
  -H "X-TC-Timestamp: ${TIMESTAMP}" \
  -H "X-TC-Nonce: ${NONCE}" \
  -H "X-TC-Signature: ${SIGNATURE}" \
  -F "file=@${IMAGE}" \
  | python -m json.tool
