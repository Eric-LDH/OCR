# OCR 安全识别接口

基于 FastAPI + RapidOCR 构建的通用图文识别接口，采用对齐大厂（腾讯云 / 阿里云）风格的
**HMAC-SHA256 对称签名鉴权**，内置**时间戳防重放、Nonce 防重放、全局限流**，适用于
公网对外开放场景，可在 2C4G 服务器上运行。

## 目录结构

```
.
├── app/
│   ├── main.py               # 应用入口 & 统一异常处理
│   ├── static/
│   │   └── index.html        # 可视化测试界面
│   ├── api/
│   │   ├── router.py         # 路由注册
│   │   ├── ocr.py            # OCR 接口（签名+限流+校验+识别）
│   │   └── test_ui.py        # 测试界面专用端点（无签名，仅本地）
│   ├── core/
│   │   ├── config.py         # 配置加载（yaml + 环境变量）
│   │   ├── secret.py         # 密钥管理（静态配置，预留扩展）
│   │   ├── signature.py      # 签名校验（HMAC-SHA256 + 防重放）
│   │   ├── ratelimit.py      # 令牌桶全局限流
│   │   └── exceptions.py     # 统一异常与响应结构
│   └── services/
│       └── ocr_service.py    # RapidOCR 封装
├── examples/
│   ├── client_sdk.py         # Python 调用示例
│   └── curl_demo.sh          # curl 调用示例
├── config.yaml               # 默认配置
├── .env.example              # 环境变量示例
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 接口定义

### 识别接口

- **URL**：`POST /api/v1/ocr`
- **Content-Type**：`multipart/form-data`
- **表单字段**：`file`（单张图片，字段名固定为 `file`）
- **图片限制**：jpg/png/webp/bmp，默认上限 5MB（可配置）

#### 请求头（鉴权）

| 头 | 说明 |
|---|---|
| `X-TC-AppId` | 调用方 AppId |
| `X-TC-Timestamp` | Unix 秒级时间戳 |
| `X-TC-Nonce` | 随机字符串（防重放，每次请求唯一） |
| `X-TC-Signature` | HMAC-SHA256 签名 |

#### 签名算法

```
message = "{HTTP方法}\n{请求路径}\n{时间戳}\n{Nonce}"
签名示例：POST\n/api/v1/ocr\n1700000000\nxxxx-xxxx
signature = HMAC_SHA256(message, key=AppSecret).hexdigest()   # 十六进制小写
```

`HTTP方法` 为 `POST`，`请求路径` 为 `/api/v1/ocr`（不含域名与查询串）。

#### 成功响应（HTTP 200）

```json
{
  "code": 200,
  "message": "success",
  "request_id": "uuid",
  "data": {
    "text": "第一行文字\n第二行文字",
    "lines": [
      {
        "text": "第一行文字",
        "confidence": 0.99,
        "box": [[10, 10], [200, 10], [200, 40], [10, 40]]
      }
    ]
  }
}
```

- `text`：全部识别文字（按行以换行拼接）
- `lines[].box`：文字块四角点 `[x1,y1],[x2,y2],[x3,y3],[x4,y4]`（像素坐标）

#### 错误码表

| HTTP | 错误说明 |
|---|---|
| 200 | 成功 |
| 400 | 请求参数错误（文件过大 / 类型不支持 / 图片解码失败 / 缺少字段） |
| 401 | 签名校验失败（缺头 / 无效 AppId / 时间戳过期 / Nonce 复用 / 签名不匹配） |
| 429 | 超过全局限流 |
| 500 | 服务端内部错误（OCR 识别失败等） |

### 健康检查

- **URL**：`GET /health`（不校验签名）

### 交互式文档

启动后访问 `http://<host>:8000/docs`（Swagger）。

### 测试界面（本地测试）

提供了一个可视化测试页面，无需手工计算签名即可拖拽图片测试识别效果。

- **访问地址**：`http://<host>:8000/test`
- **功能**：拖拽/选择图片 → 点击"开始识别" → 显示识别文本、置信度、坐标，并在图片上绘制文字框
- **接口**：使用专用测试端点 `POST /api/v1/test/ocr`（**无签名**，仅供本地测试）
- **开关**：由 `ENABLE_TEST_UI` 控制（`config.yaml` 或环境变量 `OCR_ENABLE_TEST_UI`），**生产务必设为 `false`**

## 密钥配置说明

### 生成密钥

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 配置方式（任选其一）

1. **环境变量（推荐，生产）**：
   ```bash
   export OCR_APP_SECRETS="appid1:secret1,appid2:secret2"
   ```
2. **配置文件**：编辑 `config.yaml` 中的 `APP_SECRETS`。

### 密钥轮换

静态配置模式下不支持热更新。轮换流程：
1. 在配置中**新增**新密钥（新 AppId）或修改 Secret；
2. 重启服务生效；
3. 如为修改同一 AppId 的 Secret，需同步更新所有调用方后重启。

> 设计上预留了 `SecretManager` 接口，如需升级为数据库管理（发放/吊销/轮换），
> 只需替换 `StaticSecretStore` 实现，无需改动业务代码。

## 部署（Docker）

### 1. 配置密钥

编辑 `docker-compose.yml` 中的 `OCR_APP_SECRETS` 环境变量，替换示例密钥。

### 2. 构建并启动

```bash
docker compose up -d --build
```

### 3. 验证

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 调用示例
bash examples/curl_demo.sh /path/to/image.jpg
```

## 本地开发（非 Docker）

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload
```

> 首次识别会加载 RapidOCR 模型（约 100-200MB），需要几秒，属正常现象。

## HTTPS 说明

当前默认 HTTP。公网开放**务必启用 HTTPS**，否则密钥与图片在传输中可被窃取。建议：

- **方式一（推荐）**：前置 Nginx / Caddy / 云负载均衡做 TLS 终结，把 `/api/` 反向代理到
  本服务 8000 端口，本服务保持 HTTP 即可（架构最简）。
- **方式二**：Caddy 自动申请 Let's Encrypt 证书并反向代理（配置示例见下）。

```caddyfile
api.example.com {
    reverse_proxy ocr-api:8000
}
```

## 限流说明

默认全局限流：每秒 2 次、突发 5 次（令牌桶）。通过环境变量
`OCR_RATE_LIMIT_PER_SECOND` / `OCR_RATE_LIMIT_BURST` 调整。

- 单实例进程内实现，无需外部组件。
- 如需多实例横向扩展，请将 `NonceCache` 与令牌桶替换为 Redis 实现（代码已标注位置）。

## 性能参考

| 项 | 参考值 |
|---|---|
| 模型内存占用 | 约 400-800MB（CPU 推理） |
| 单张识别耗时（普通图片） | 约 0.5-2 秒（视内容复杂度） |
| 建议并发 | 2C4G 下建议串行处理（worker=1），QPS 受限于图片复杂度 |

> 高并发场景建议前置消息队列/异步化，或将 OCR 抽离为独立算力服务。
