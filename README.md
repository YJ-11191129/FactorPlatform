# FactorPlatform

因子库与因子分析平台开发目录。

- 主设计文档：docs/FACTOR_PLATFORM_MASTER_PLAN.md
- 建议按主设计文档拆分并补齐 docs 下的子文档

## 开发启动（后端）

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.api.app:app --reload --host 0.0.0.0 --port 8000
```

## docker-compose（上线/联调）

```bash
docker compose up -d --build
```

- 前端：http://localhost:3000
- 后端：http://localhost:8002

## 鉴权（API Key）

- docker-compose 默认开启鉴权：请求头 `X-API-Key`
- key/角色在 `docker-compose.yml` 里通过 `FACTOR_PLATFORM_API_KEYS` 配置（格式：`key:role,key2:role2`）
