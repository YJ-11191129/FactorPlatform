# AGENTS.md

## 项目目标

本项目是一个 AI 金融研究与交易辅助平台的官网落地页。请将现有页面改造成“专业金融科技 / 机构投研终端 / AI 市场分析平台”的风格，而不是夸张的交易信号站、币圈营销页或普通 SaaS 模板。

核心定位：
- AI market intelligence platform
- AI-assisted decision support
- risk-aware trading research terminal
- multi-agent market analysis
- not financial advice

## 视觉方向

整体风格应参考机构级金融终端、量化研究平台、AI 投研工作台：

- dark institutional fintech style
- deep navy / charcoal / black background
- low-saturation academic fintech palette
- clean grid layout
- subtle glassmorphism only where needed
- 1px soft borders
- restrained glow effects
- rounded-xl or rounded-2xl cards
- high information density but clear hierarchy
- no childish gradients
- no crypto casino visual style
- no over-decorated 3D illustrations
- no exaggerated neon effects

推荐配色：

- page background: #05070B
- section background: #08111F
- card background: #0B1220
- elevated panel: #111827
- border: rgba(255,255,255,0.08)
- primary text: #F8FAFC
- secondary text: #94A3B8
- muted text: #64748B
- cyan accent: #22D3EE
- emerald accent: #34D399
- violet accent: #A78BFA
- amber warning: #F59E0B
- red risk: #F87171

## 文案原则

必须弱化收益承诺，强化专业性、风险控制和辅助决策。

禁止使用：
- guaranteed profit
- win every trade
- predict the market with certainty
- beat the market easily
- unlock unlimited returns
- day trading edge you need
- 100% accurate signals
- risk-free
- 稳赚
- 躺赚
- 稳赢
- 精准预测涨跌
- 锁定收益
- 暴利信号

推荐使用：
- decision support
- risk-aware market analysis
- scenario-based forecasting
- signal screening
- market regime recognition
- volatility-aware research
- AI-assisted trading research
- probabilistic insight
- not financial advice
- 用于辅助研究与风险识别
- 辅助决策，而非替代判断
- 面向波动、趋势与结构变化的市场分析
- 提供概率化信号与情景推演

## 页面结构

尽量保留现有页面的信息架构，但重新组织视觉层级。目标页面应包括：

1. Header
   - Logo
   - Product
   - Features
   - Markets
   - Pricing
   - Login / Launch App

2. Hero Section
   - 大标题强调 AI 市场情报与风险感知
   - 副标题强调辅助决策、跨市场分析、情景推演
   - CTA 使用 “Explore Platform” / “View Research Terminal”
   - 不使用“Start Winning”之类表述

3. Terminal Mockup
   - 做成机构级 AI Research Terminal
   - 展示资产：XAU/USD、BTC/USD、S&P 500、USD/JPY
   - 展示模块：
     - AI confidence
     - volatility regime
     - risk/reward estimate
     - signal rationale
     - scenario analysis
     - stop-loss discipline
     - market microstructure notes

4. Multi-Agent Intelligence
   - Economist Agent
   - Quant Agent
   - Technical Agent
   - Risk Agent
   - News Agent
   - Contrarian Agent

5. Signal Analysis
   - 强调 signal screening，不强调“喊单”
   - 展示概率、置信区间、风险等级、触发条件

6. MarketGPT / AI Copilot
   - 定位为市场研究助手
   - 示例问题偏专业：
     - “What changed in the USD/JPY risk regime?”
     - “Summarize gold volatility drivers.”
     - “Compare trend strength across major indices.”
     - “Explain why this signal was rejected.”

7. Risk & Compliance Section
   - 加一块“Risk-aware by design”
   - 强调非投资建议、风险提示、模型不确定性

8. Pricing
   - Free / Pro / Institutional
   - 语气克制、专业

9. Footer
   - Risk disclaimer
   - Terms
   - Privacy

## 技术要求

请优先识别项目现有技术栈，不要盲目重构。

如果项目是 Next.js / React / Tailwind：
- 使用 TypeScript
- 使用 Tailwind CSS
- 优先复用现有组件
- 可以使用 lucide-react icons
- 可以使用 framer-motion / motion 做轻微动效
- 卡片、按钮、导航、徽章应组件化
- 避免引入过重依赖
- 不要破坏现有路由、SEO、i18n 和构建配置

如果项目不是 Next.js / React：
- 先说明识别到的技术栈
- 在现有栈内完成改造
- 不要强行迁移框架

## 工程约束

- 不要删除业务逻辑
- 不要修改认证、支付、后端 API
- 不要大规模重写项目结构，除非确有必要
- 优先小步修改
- 每次修改后运行 lint / build / typecheck
- 如果缺少脚本，请说明无法运行的原因
- 修改完成后给出变更摘要和验证结果

## 完成标准

完成后页面应满足：

- 看起来像专业 AI 金融研究平台
- 不像币圈喊单网站
- 不出现夸张收益承诺
- 移动端、平板端、桌面端布局正常
- 主视觉终端有真实金融信息密度
- CTA 清晰但克制
- 文案更专业、可信、风险意识更强
- 构建通过
