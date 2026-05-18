# DeepSeek（OpenAI Compatible）配置说明

本项目的“宏观推演 / 主题报告”功能通过 OpenAI 兼容的 Chat Completions API 调用大模型。

默认情况下，本项目会以 DeepSeek 作为默认模型端点（如果你不显式配置 OpenAI）。

## 1. 推荐环境变量（与你给的一致）

在后端进程环境中设置：

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=<your_deepseek_key>
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=60
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=2000
```

### 1.1 最推荐的填写位置（本项目已支持）

在项目根目录创建 `d:\FactorPlatform\.env.local`，把上面的变量粘进去并把 `LLM_API_KEY` 换成你的真实 key。

启动脚本 `scripts/start_all.ps1` 会自动加载 `\.env.local` 并把 `LLM_*` 传递给后端进程。

注意：如果后端已经在跑，修改 `.env.local` 不会自动生效，需要重启后端（可用 `FACTOR_PLATFORM_FORCE_RESTART_API=1` 强制重启）。

说明：

- `LLM_BASE_URL` 可以是 `https://api.deepseek.com` 或 `https://api.deepseek.com/v1`，系统会自动归一化为 `.../v1/chat/completions`。
- `LLM_API_KEY` 必须是真实 key。若 key 无效，接口会返回 4xx（常见为认证失败）。

## 2. 与旧变量的兼容

如果你已经使用 OpenAI 风格变量，也仍然可用：

```bash
OPENAI_API_KEY=<your_key>
OPENAI_BASE_URL=https://api.deepseek.com/v1/chat/completions
FACTOR_PLATFORM_LLM_MODEL=deepseek-chat
```

其中：

- `LLM_API_KEY` 优先级高于 `OPENAI_API_KEY`
- `LLM_BASE_URL` 优先级高于 `OPENAI_BASE_URL`

## 3. 快速自检

- 打开后端接口文档：`http://127.0.0.1:8003/docs`
- 调用宏观推演：`POST /api/v1/macro/chain-of-impact`，body 示例：

```json
{ "topic": "石油" }
```

若配置成功，返回体中的 `llm_ready` 应为 `true`。
