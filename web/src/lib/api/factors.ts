import { fetchJson } from "@/lib/api/client";
import { allowMockFallback } from "@/lib/api/mockPolicy";
import { adaptFactorDetail, adaptFactorItem, type BackendFactorInfo } from "@/lib/adapters/factorAdapter";
import { mockFactorDetail, mockFactors } from "@/lib/mock/factors";
import type { FactorDetail, FactorItem } from "@/types/factor";

export type { BackendFactorInfo } from "@/lib/adapters/factorAdapter";

export async function listFactors(): Promise<FactorItem[]> {
  try {
    const raw = await fetchJson<BackendFactorInfo[]>("/api/factors");
    return raw.map(adaptFactorItem);
  } catch {
    if (!allowMockFallback()) throw new Error("Failed to load factors from backend");
    return mockFactors;
  }
}

export async function listFactorMetadata(): Promise<BackendFactorInfo[]> {
  return fetchJson<BackendFactorInfo[]>("/api/factors");
}

export async function getFactorDetail(factorName: string): Promise<FactorDetail | null> {
  try {
    const raw = await fetchJson<BackendFactorInfo>(`/api/factors/${encodeURIComponent(factorName)}`);
    return adaptFactorDetail(raw);
  } catch {
    if (!allowMockFallback()) throw new Error(`Failed to load factor detail: ${factorName}`);
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
  return fetchJson<StockRadarResult>("/api/factor-library/radar/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

