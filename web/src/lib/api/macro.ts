import { fetchJson } from "@/lib/api/client";
import type { MacroChainResponse, MacroInputs, MacroTopicReportResponse } from "@/types/macro";

function demoChain(payload: MacroInputs): MacroChainResponse {
  const topic = payload.topic || "市场事件";
  return {
    inputs: payload,
    context: {
      topic,
      event: payload.event,
      region: payload.region,
      horizon: payload.horizon,
      generated_at: new Date().toISOString(),
      notes: ["信息源暂不可用，当前展示只读结构化兜底。"],
    },
    llm_ready: false,
    result: {
      regime_hypothesis: `${topic} 可能影响产业预期与风险偏好，短期更适合作为观察线索而非直接交易依据。`,
      cause: [
        payload.event || `${topic} 相关新闻热度上升`,
        "产业链预期变化可能影响主题资产估值",
        "市场仍需成交量、波动率和资金流确认",
      ],
      transmission: [
        { step: "事件确认", channel: "新闻与公告", who: "产业链公司", timeframe: "当日" },
        { step: "预期重估", channel: "主题资金与估值", who: "相关行业", timeframe: "数日" },
        { step: "风险验证", channel: "波动与成交", who: "宽基与主题资产", timeframe: "1-2 周" },
      ],
      impact: {
        assets: [
          { name: "相关主题 ETF", direction: "mixed", confidence: 0.62 },
          { name: "宽基指数", direction: "mixed", confidence: 0.55 },
        ],
        sectors: [
          { name: topic.includes("半导体") ? "半导体" : "高端制造", direction: "up", confidence: 0.66 },
          { name: "风险偏好", direction: "mixed", confidence: 0.58 },
        ],
        signals_to_watch: ["成交额放大", "主题扩散度", "波动率变化", "政策/公告确认"],
      },
      risks: ["新闻误读", "高开低走", "外部市场波动"],
      assumptions: ["仅用于辅助研究与情景推演"],
      confidence: 0.62,
    },
  };
}

function demoReport(payload: MacroInputs): MacroTopicReportResponse {
  const topic = payload.topic || "市场事件";
  return {
    inputs: payload,
    context: {
      topic,
      event: payload.event,
      region: payload.region,
      horizon: payload.horizon,
      generated_at: new Date().toISOString(),
      notes: ["信息源暂不可用，当前展示只读结构化兜底。"],
    },
    llm_ready: false,
    result: {
      executive_summary: `${topic} 需要结合新闻真实性、产业链映射和市场量价确认。当前适合进入观察清单，并通过策略回测验证可交易性。`,
      drivers: ["主题新闻热度", "产业链预期", "成交量确认", "风险偏好变化"],
      market_dashboard: [
        { metric: "新闻热度", value: "较高", interpretation: "需要确认来源和后续扩散" },
        { metric: "风险状态", value: "中性偏高", interpretation: "建议控制仓位并等待量价确认" },
        { metric: "可操作性", value: "观察", interpretation: "先生成策略并回测，不直接执行" },
      ],
      watchlist: ["相关 ETF", "龙头公司", "成交额", "波动率", "政策公告"],
      disclaimer: "仅用于辅助研究与风险识别，不构成投资建议。",
    },
  };
}

export function generateChainOfImpact(payload: MacroInputs) {
  return fetchJson<MacroChainResponse>("/api/v1/macro/chain-of-impact", {
    method: "POST",
    body: JSON.stringify(payload),
  }).catch(() => demoChain(payload));
}

export function generateTopicReport(payload: MacroInputs) {
  return fetchJson<MacroTopicReportResponse>("/api/v1/macro/topic-report", {
    method: "POST",
    body: JSON.stringify(payload),
  }).catch(() => demoReport(payload));
}
