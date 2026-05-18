import { fetchJson } from "@/lib/api/client";
import type { NewsSearchResponse, NewsSummaryResponse } from "@/types/news";

type NewsQuery = {
  topic: string;
  limit?: number;
  lang?: string;
  region?: string;
  source?: "google_news_rss" | "openbb" | string;
  provider?: string;
  symbol?: string;
  start_date?: string;
  end_date?: string;
  topics?: string;
};

function toQuery(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") usp.set(k, String(v));
  }
  const raw = usp.toString();
  return raw ? `?${raw}` : "";
}

export function searchNews(query: NewsQuery) {
  return fetchJson<NewsSearchResponse>(`/api/v1/news/search${toQuery(query)}`);
}

export function summarizeNews(query: NewsQuery) {
  return fetchJson<NewsSummaryResponse>(`/api/v1/news/summary${toQuery(query)}`);
}
