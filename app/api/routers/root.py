from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>FactorPlatform</title>
</head>
<body>
  <h1>FactorPlatform</h1>
  <p>后端 MVP：因子注册/列表/运行（含 qlib_bin 数据接入）。</p>
  <ul>
    <li><a href="/docs">API Docs (Swagger)</a></li>
    <li><a href="/redoc">API Docs (ReDoc)</a></li>
    <li><a href="/api/factors">Factor List</a></li>
  </ul>
</body>
</html>"""

