# 宏观推演（CoT）与新闻聚合：前端接入审计报告

本文审计范围仅覆盖“宏观推演（Chain-of-Impact）+ 主题报告（Holistic Report）+ 新闻聚合”这部分从后端 API 到前端页面的接入链路，包括鉴权、代理、超时与可用性验证。

## 1. 审计结论（摘要）

- 功能已在前端以独立页面形式上线：`/macro-intel`，并在侧边栏新增入口。
- 鉴权链路清晰：前端通过 `X-API-Key` 访问 `/backend/*`，由 Next 代理转发至后端；后端基于 `FACTOR_PLATFORM_API_KEYS` 校验并做角色授权。
- 关键稳定性修复已落实：宏观接口原先可能因读取大体积 parquet 导致前端代理 30s 超时；现已通过“元数据读取 + 超时放宽”避免 504。
- 已进行联通性验证：通过前端代理访问 `/api/v1/news/search` 与 `/api/v1/macro/chain-of-impact` 均返回 200。

## 2. 变更范围与文件清单

### 2.1 前端（Next.js）

- 新页面：`web/src/app/macro-intel/page.tsx`
- 侧边栏入口：`web/src/components/layout/AppSidebar.tsx`
- API 封装：
  - `web/src/lib/api/macro.ts`
  - `web/src/lib/api/news.ts`
- 类型定义：
  - `web/src/types/macro.ts`
  - `web/src/types/news.ts`
- 代理与超时策略：`web/src/app/backend/[...path]/route.ts`

### 2.2 后端（FastAPI）

- 宏观 API：`app/api/routers/macro.py`
- 新闻 API：`app/api/routers/news.py`
- 宏观服务：`app/services/macro_intelligence_service.py`

### 2.3 启动与环境

- 开发启动脚本：`scripts/start_all.ps1`
- 前端本地环境变量：`web/.env.local`

## 3. 功能入口与用户路径

- 页面入口：侧边栏 `Macro Intelligence` → 路由 `/macro-intel`
- 页面能力：
  - 输入：topic（必填）、event/region/horizon（可选）
  - 操作：一键生成 / 单独生成推演 / 单独生成报告 / 拉取新闻
  - 输出：宏观推演结构化结果、报告摘要、新闻聚合（highlights/sources/items）

## 4. API 接入与鉴权链路审计

### 4.1 请求路径

- 浏览器 → 前端 API：统一走 `/backend` 代理
  - 宏观推演：`POST /backend/api/v1/macro/chain-of-impact`
  - 主题报告：`POST /backend/api/v1/macro/topic-report`
  - 新闻搜索：`GET /backend/api/v1/news/search?...`
  - 新闻摘要：`GET /backend/api/v1/news/summary?...`

### 4.2 鉴权方式

- 前端请求头：`X-API-Key: <key>`
  - 来源：`NEXT_PUBLIC_API_KEY` 或浏览器 `localStorage` 的 `FP_API_KEY`
  - 相关实现：`web/src/lib/api/client.ts`

- Next 代理补齐请求头：若入站未带 `X-API-Key`，会自动用 `NEXT_PUBLIC_API_KEY` 注入
  - 相关实现：`web/src/app/backend/[...path]/route.ts` 的 `apiKey()` 与代理逻辑

- 后端校验：`FACTOR_PLATFORM_API_KEYS` 解析格式 `key:role,key2:role2`
  - 相关实现：`app/api/dependencies/auth.py`（`get_actor()` / `require_role()`）
  - 宏观与新闻路由均要求角色：`viewer|operator|admin`

### 4.3 开发环境配置（本次使用）

- 后端：`FACTOR_PLATFORM_API_KEYS=dev-key-123:admin` 且 `FACTOR_PLATFORM_REQUIRE_AUTH=1`
- 前端：
  - `NEXT_PUBLIC_API_BASE_PATH=/backend`
  - `NEXT_PUBLIC_API_KEY=dev-key-123`

说明：该 key 为开发用途演示 key，不建议用于生产。

## 5. 稳定性与性能审计

### 5.1 已观察到的风险

- 风险：宏观接口在构造上下文时读取 `stock_daily_ohlcv.parquet`（可能体积大），若全量读取会造成请求耗时过长。
- 表现：前端代理对非 GET 默认 30s 超时，可能返回 504 `BACKEND_TIMEOUT_OR_UNREACHABLE`。

### 5.2 已采取的修复

- 后端：`_read_stock_ohlcv_status()` 改为优先使用 parquet 元数据/统计信息获取起止日期与行数，避免全量扫描；失败时再降级读取少量列。
  - 文件：`app/services/macro_intelligence_service.py`

- 前端：对 `/api/v1/macro/*` 放宽代理超时至 120s，避免因推演/报告耗时导致误判超时。
  - 文件：`web/src/app/backend/[...path]/route.ts`

### 5.3 仍建议的后续优化（非阻塞）

- 对宏观与报告接口增加缓存（按 topic/region/horizon + 数据版本）或异步任务化，避免重复计算。
- 对新闻 RSS 增加请求重试与限流策略；同时为不同数据源预留扩展点。

## 6. 启动与运维链路审计

- `scripts/start_all.ps1`：
  - 自动拉起 postgres/redis（docker）
  - 自动选择可用 API 端口（优先 8003/8004/8002）并启动后端
  - 启动 WSL Next dev，并确保 `NEXT_PUBLIC_API_KEY` 与 `BACKEND_ORIGIN` 注入

注意：脚本中 WSL 前端会复制 `D:/FactorPlatform/web` 至 `~/factorplatform_web` 并在该目录启动 dev server。

## 7. 验证记录

本次完成以下最小验证（通过前端代理路径）：

- `GET /backend/api/v1/news/search?topic=石油&limit=1` → 200
- `POST /backend/api/v1/macro/chain-of-impact`（`{"topic":"石油"}`）→ 200
- `GET /macro-intel` → 200

## 8. 安全审计备注

- `dev-key-123` 仅作为开发演示，不应进入生产环境。
- `web/.env.local` 属于本地文件，已被 `web/.gitignore` 忽略（不会被提交）。

