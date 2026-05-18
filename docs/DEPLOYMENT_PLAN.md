# DEPLOYMENT_PLAN

本文件从主设计文档拆分，定义：docker-compose（MVP）、环境变量、数据卷、迁移与启动顺序。

## 1. 本地开发

- 后端：uvicorn 直接启动，数据库可选（默认不会强制要求 DB）。
- 前端：Next.js dev，通过 `/backend/*` rewrite 代理到后端。

## 2. docker-compose（MVP）

- 目标：一条命令拉起 postgres + redis + 后端 + worker + 前端，并完成数据库迁移与因子元数据同步；异步任务由 Celery worker 执行。
- 入口文件：仓库根目录 `docker-compose.yml`

启动：

```bash
docker compose up -d --build
```

访问：

- 前端：http://localhost:3000
- 后端：http://localhost:8002（Swagger: http://localhost:8002/docs）

## 3. 配置与密钥管理

- DATABASE_URL：后端数据库连接串（生产必须配置）
- REDIS_URL：预留给异步任务/缓存（当前后端会读但不强依赖）
- FACTOR_PLATFORM_REQUIRE_DB：设为 1 时后端启动会强制要求 DB 可用
- FACTOR_PLATFORM_REQUIRE_AUTH：设为 1 时所有 API 需要 `X-API-Key`
- FACTOR_PLATFORM_API_KEYS：逗号分隔的 `key:role` 列表（role 支持 viewer/operator/admin）
- FACTOR_PLATFORM_REAL_OHLCV_PATH：真实日频 OHLCV parquet 路径（用于 `/api/factor-library/compute-store`）
- FACTOR_PLATFORM_TRADABLE_FLAGS_PATH / FACTOR_PLATFORM_UNIVERSE_PATH / FACTOR_PLATFORM_FINANCIAL_STATEMENT_PATH：股票筛选数据路径（用于 `/api/factor-library/screen/*`）
- FACTOR_PLATFORM_ENABLE_PDF：设为 1 时尝试生成 PDF（若运行环境缺少 weasyprint 依赖则会回退仅生成 HTML）

docker-compose 已为后端与 worker 设置 DATABASE_URL/REDIS_URL/FACTOR_PLATFORM_REQUIRE_DB/鉴权开关，并示例性挂载：

- `D:/Kaggle/data` -> `/data/kaggle`（只读）
- `D:/mcQlib/data` -> `/data/mcqlib`（只读）

如果你的数据目录不同，请调整 `docker-compose.yml` 的 volumes 与 `FACTOR_PLATFORM_REAL_OHLCV_PATH` 等环境变量。

## 4. 初始化与迁移

- 迁移工具：Alembic
- 启动时自动执行：容器后端进程会先运行 `python scripts/init_db.py`，对 DB 执行 `upgrade head`，并同步“代码因子”到 `factor_metadata` 表
- 手动执行：

```bash
python scripts/init_db.py
```

## 5. 观测与日志

- 后端健康检查：`GET /health`
- 前端请求链路：Next.js `/backend/*` 代理到 `BACKEND_ORIGIN`（docker-compose 中为 `http://backend:8000`）
