import { fetchJson } from "@/lib/api/client";
import { allowMockFallback } from "@/lib/api/mockPolicy";
import { adaptFactorDetail, adaptFactorItem, type BackendFactorInfo } from "@/lib/adapters/factorAdapter";
import { mockFactorDetail, mockFactors } from "@/lib/mock/factors";
import type { FactorDetail, FactorItem } from "@/types/factor";

export type { BackendFactorInfo } from "@/lib/adapters/factorAdapter";

export async function listFactors(): Promise<FactorItem[]> {
  try {
    const raw = await fetchJson<BackendFactorInfo[]>("/api/factors", { timeoutMs: 4500 });
    return raw.map(adaptFactorItem);
  } catch (e) {
    if (!allowMockFallback()) throw e;
    return mockFactors;
  }
}

export async function listFactorMetadata(): Promise<BackendFactorInfo[]> {
  return fetchJson<BackendFactorInfo[]>("/api/factors", { timeoutMs: 4500 });
}

export async function getFactorDetail(factorName: string): Promise<FactorDetail | null> {
  try {
    const raw = await fetchJson<BackendFactorInfo>(`/api/factors/${encodeURIComponent(factorName)}`);
    return adaptFactorDetail(raw);
  } catch (e) {
    if (!allowMockFallback()) throw e;
    return mockFactorDetail[factorName] || null;
  }
}

export type RunDemoPayload = {
  factor_name: string;
  params: Record<string, unknown>;
  save?: boolean;
};

export type RunQlibPayload = RunDemoPayload & {
  provider_uri: string;
  universe: string;
  start_date?: string | null;
  end_date?: string | null;
  instrument_limit?: number;
};

export type RunResult = {
  factor_name: string;
  row_count: number;
  columns: string[];
  preview: Record<string, unknown>[];
  message?: string;
  calc_batch_id?: string | null;
  download_url?: string | null;
};

export type StockRadarFactorSpec = {
  factor_name: string;
  params: Record<string, unknown>;
  weight: number;
  direction: "positive" | "negative";
};

export type StockRadarPayload = {
  provider_uri: string;
  universe: string;
  factors: StockRadarFactorSpec[];
  start_date?: string | null;
  end_date?: string | null;
  asof_date?: string | null;
  instrument_limit?: number | null;
  topn: number;
  min_score?: number | null;
  min_factor_count?: number;
  winsorize_q?: number;
};

export type StockRadarItem = {
  rank: number;
  trade_date: string;
  asset_code: string;
  close?: number | null;
  volume?: number | null;
  score: number;
  score_percentile: number;
  valid_factor_count?: number;
  missing_factor_count?: number;
  factor_coverage?: number;
  factor_values: Record<string, number | null>;
  factor_scores: Record<string, number | null>;
  factor_ranks: Record<string, number | null>;
  factor_contributions?: Record<string, number | null>;
  top_factor_contributors?: { key: string; contribution: number | null }[];
};

export type StockRadarResult = {
  universe: string;
  provider_uri: string;
  signal_date: string;
  effective_trade_date: string;
  row_count_on_signal_date?: number;
  row_count_before_score_filter: number;
  row_count: number;
  topn: number;
  min_score?: number | null;
  min_factor_count?: number;
  factors: Record<string, unknown>[];
  items: StockRadarItem[];
  timing_note: string;
  data_health?: {
    blocking_status?: "OK" | "WARN" | "BLOCKED";
    message?: string;
    status?: string;
    source_id?: string;
    latest_date?: string | null;
    requested_end_date?: string | null;
  } | null;
};

export function buildDemoStockRadar(payload: StockRadarPayload): StockRadarResult {
  const factorSpecs = payload.factors?.length ? payload.factors : [
    { factor_name: "QLIB_ALPHA_ROC20_V1", params: {}, weight: 0.4, direction: "positive" },
    { factor_name: "QLIB_ALPHA_RANK20_V1", params: {}, weight: 0.25, direction: "positive" },
    { factor_name: "QLIB_ALPHA_SUMP20_V1", params: {}, weight: 0.35, direction: "positive" },
  ];
  const factorKeys = factorSpecs.map((factor, index) => `factor_${index + 1}`);
  const isUs = /sp500|nasdaq|us/i.test(payload.universe || payload.provider_uri || "");
  const names = isUs
    ? ["NASDAQ:NVDA", "NASDAQ:MSFT", "NASDAQ:AAPL", "NASDAQ:AVGO", "NASDAQ:AMD"]
    : ["300750.SZ", "300760.SZ", "300308.SZ", "600519.SH", "002475.SZ"];
  const today = new Date().toISOString().slice(0, 10);
  const topn = Math.max(1, Math.min(Number(payload.topn || 5), names.length));
  const items: StockRadarItem[] = names.slice(0, topn).map((assetCode, index) => {
    const score = 1.62 - index * 0.23;
    const factor_values = Object.fromEntries(factorKeys.map((key, factorIndex) => [key, Number((score - factorIndex * 0.18).toFixed(4))]));
    const factor_scores = Object.fromEntries(factorKeys.map((key, factorIndex) => [key, Number((score - factorIndex * 0.12).toFixed(4))]));
    const factor_ranks = Object.fromEntries(factorKeys.map((key, factorIndex) => [key, Number(Math.max(0.58, 0.94 - index * 0.06 - factorIndex * 0.03).toFixed(4))]));
    const factor_contributions = Object.fromEntries(factorKeys.map((key, factorIndex) => [key, Number(((score / factorKeys.length) - factorIndex * 0.04).toFixed(4))]));
    return {
      rank: index + 1,
      trade_date: today,
      asset_code: assetCode,
      close: Number((index % 2 === 0 ? 86.8 + index * 12.4 : 42.6 + index * 8.7).toFixed(3)),
      volume: 1200000 + index * 260000,
      score: Number(score.toFixed(4)),
      score_percentile: Number((0.94 - index * 0.07).toFixed(4)),
      valid_factor_count: factorKeys.length,
      missing_factor_count: 0,
      factor_coverage: 1,
      factor_values,
      factor_scores,
      factor_ranks,
      factor_contributions,
      top_factor_contributors: factorKeys.map((key) => ({ key, contribution: factor_contributions[key] })),
    };
  });

  return {
    universe: payload.universe || (isUs ? "sp500" : "csi300"),
    provider_uri: payload.provider_uri,
    signal_date: today,
    effective_trade_date: today,
    row_count_on_signal_date: items.length,
    row_count_before_score_filter: items.length,
    row_count: items.length,
    topn,
    min_score: payload.min_score,
    min_factor_count: payload.min_factor_count,
    factors: factorSpecs.map((factor, index) => ({
      key: factorKeys[index],
      factor_name: factor.factor_name,
      display_name: factor.factor_name.replace(/^QLIB_ALPHA_/, "").replace(/_V1$/, ""),
      category: factor.factor_name.includes("STD") ? "QLIB_VOLATILITY" : "QLIB_MOMENTUM",
      weight: factor.weight,
      normalized_weight: factor.weight,
      coverage_ratio: 1,
    })),
    items,
    timing_note: "Backend stock radar is unavailable. This is a read-only fallback candidate pool; refresh after the API recovers to get computed results.",
    data_health: {
      blocking_status: "WARN",
      message: "Backend stock radar is unavailable. Frontend read-only fallback is active.",
      status: "FALLBACK",
      source_id: "frontend-demo",
      latest_date: today,
      requested_end_date: payload.end_date || null,
    },
  };
}

export async function runDemo(payload: RunDemoPayload): Promise<RunResult> {
  return fetchJson<RunResult>("/api/factors/run-demo", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runQlib(payload: RunQlibPayload): Promise<RunResult> {
  return fetchJson<RunResult>("/api/factors/run-qlib", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runStockRadar(payload: StockRadarPayload): Promise<StockRadarResult> {
  try {
    return await fetchJson<StockRadarResult>("/api/factor-library/radar/run", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 6500,
    });
  } catch (e) {
    return buildDemoStockRadar(payload);
  }
}

