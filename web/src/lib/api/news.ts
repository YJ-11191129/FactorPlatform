import { fetchJson } from "@/lib/api/client";
import type { NewsSearchResponse, NewsSummaryResponse } from "@/types/news";

type NewsQuery = {
  topic: string;
  limit?: number;
  lang?: string;
  region?: string;
};

function toQuery(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") usp.set(k, String(v));
  }
  const raw = usp.toString();
  return raw ? `?${raw}` : "";
}

function demoNews(query: NewsQuery): NewsSummaryResponse {
  const topic = query.topic || "市场事件";
  const isHuawei = /华为|韬|半导体|芯片/.test(topic);
  const items = isHuawei
    ? [
      { title: "华为发表韬(τ)定律，实现晶体管密度与系统性能突破", link: "", source: "公开新闻", published_at: new Date().toISOString() },
      { title: "半导体产业链关注先进封装、系统级优化与国产替代进展", link: "", source: "公开新闻", published_at: new Date().toISOString() },
      { title: "市场关注高端制造主题扩散，仍需成交量与公告验证", link: "", source: "公开新闻", published_at: new Date().toISOString() },
    ]
    : [
      { title: `${topic} 相关新闻热度上升，市场等待进一步确认`, link: "", source: "公开新闻", published_at: new Date().toISOString() },
      { title: `${topic} 产业链影响仍需结合量价与政策信号观察`, link: "", source: "公开新闻", published_at: new Date().toISOString() },
      { title: `${topic} 主题资金活跃，但风险偏好仍需验证`, link: "", source: "公开新闻", published_at: new Date().toISOString() },
    ];
  return {
    topic,
    fetched_at: new Date().toISOString(),
    count: items.length,
    source: "fallback",
    warnings: ["信息源暂不可用，当前展示只读兜底摘要。"],
    summary: {
      highlights: [
        `${topic} 新闻热度进入观察区间。`,
        "需要结合公告、成交量和波动率确认影响强度。",
        "当前结果仅用于辅助研究与风险识别。",
      ],
      sources: { "公开新闻": items.length },
    },
    items,
  };
}

export function searchNews(query: NewsQuery) {
  return fetchJson<NewsSearchResponse>(`/api/v1/news/search${toQuery(query)}`, { timeoutMs: 4500 }).catch(() => {
    const fallback = demoNews(query);
    return {
      topic: fallback.topic,
      source: fallback.source || "fallback",
      request_url: "",
      fetched_at: fallback.fetched_at,
      items: fallback.items,
      count: fallback.count,
      latency_ms: 0,
      warnings: fallback.warnings,
    };
  });
}

export function summarizeNews(query: NewsQuery) {
  return fetchJson<NewsSummaryResponse>(`/api/v1/news/summary${toQuery(query)}`, { timeoutMs: 4500 }).catch(() => demoNews(query));
}
