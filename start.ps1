# Windows 一键启动脚本
# 用法: .\start.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境..." -ForegroundColor Cyan
    python -m venv .venv
    Write-Host "安装依赖..." -ForegroundColor Cyan
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

Write-Host "启动 OCR 服务: http://127.0.0.1:8000  (docs 在 /docs)" -ForegroundColor Green
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
