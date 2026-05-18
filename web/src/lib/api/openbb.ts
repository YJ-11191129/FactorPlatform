import { fetchJson } from "@/lib/api/client";
import type { OpenBBQueryResponse, OpenBBStatus } from "@/types/openbb";

function toQuery(params: Record<string, string | number | undefined | null>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") usp.set(key, String(value));
  }
  const raw = usp.toString();
  return raw ? `?${raw}` : "";
}

export function getOpenBBStatus() {
  return fetchJson<OpenBBStatus>("/api/openbb/status");
}

export function getOpenBBWorldNews(params: {
  term?: string;
  topics?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  provider?: string;
}) {
  return fetchJson<OpenBBQueryResponse>(`/api/openbb/news/world${toQuery(params)}`);
}

export function getOpenBBCompanyNews(params: {
  symbol: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  provider?: string;
}) {
  return fetchJson<OpenBBQueryResponse>(`/api/openbb/news/company${toQuery(params)}`);
}

export function getOpenBBEconomyCalendar(params: {
  country?: string;
  importance?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  provider?: string;
}) {
  return fetchJson<OpenBBQueryResponse>(`/api/openbb/economy/calendar${toQuery(params)}`);
}
