import { fetchJson } from "@/lib/api/client";
import { allowMockFallback } from "@/lib/api/mockPolicy";
import { mockBacktests, mockEquityCurve, mockStrategies } from "@/lib/mock/backtests";
import type { BacktestDataStatus, BacktestRunPayload, BacktestRunResult, BacktestSummary, EquityCurve } from "@/types/backtest";
import type { StrategyInfo } from "@/types/strategy";

export async function listStrategies(): Promise<StrategyInfo[]> {
  try {
    return await fetchJson<StrategyInfo[]>("/api/strategies");
  } catch {
    if (!allowMockFallback()) throw new Error("Failed to load strategies from backend");
    return mockStrategies;
  }
}

export async function runBacktest(payload: BacktestRunPayload): Promise<BacktestRunResult> {
  return fetchJson<BacktestRunResult>("/api/backtests/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listBacktests(limit = 50): Promise<BacktestSummary[]> {
  try {
    return await fetchJson<BacktestSummary[]>(`/api/backtests?limit=${limit}`);
  } catch {
    if (!allowMockFallback()) throw new Error("Failed to load backtests from backend");
    return mockBacktests;
  }
}

export async function getEquityCurve(backtestId: string): Promise<EquityCurve> {
  try {
    return await fetchJson<EquityCurve>(`/api/backtests/${encodeURIComponent(backtestId)}/equity`);
  } catch {
    if (!allowMockFallback()) throw new Error(`Failed to load equity curve: ${backtestId}`);
    return mockEquityCurve;
  }
}

export async function getBacktestDataStatus(): Promise<BacktestDataStatus> {
  return fetchJson<BacktestDataStatus>("/api/backtests/data-status");
}
