import { fetchJson } from "@/lib/api/client";
import type {
  BuildQlibPortfolioPayload,
  QlibFactorMiningRun,
  QlibMiningPayload,
  QlibPortfolio,
  QlibStatus,
} from "@/types/qlib-research";

export async function getQlibStatus(params?: { provider_uri?: string; universe?: string; freq?: string }): Promise<QlibStatus> {
  const qs = new URLSearchParams();
  if (params?.provider_uri) qs.set("provider_uri", params.provider_uri);
  if (params?.universe) qs.set("universe", params.universe);
  if (params?.freq) qs.set("freq", params.freq);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return fetchJson<QlibStatus>(`/api/qlib/status${suffix}`);
}

export async function runQlibFactorMining(payload: QlibMiningPayload): Promise<QlibFactorMiningRun> {
  return fetchJson<QlibFactorMiningRun>("/api/qlib/factor-mining/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listQlibFactorMiningRuns(limit = 20): Promise<QlibFactorMiningRun[]> {
  const res = await fetchJson<{ items: QlibFactorMiningRun[] }>(`/api/qlib/factor-mining/runs?limit=${limit}`);
  return res.items;
}

export async function getQlibFactorMiningRun(runId: string): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/api/qlib/factor-mining/runs/${encodeURIComponent(runId)}`);
}

export async function buildQlibPortfolio(payload: BuildQlibPortfolioPayload): Promise<QlibPortfolio> {
  return fetchJson<QlibPortfolio>("/api/qlib/portfolios/build", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listQlibPortfolios(limit = 20): Promise<QlibPortfolio[]> {
  const res = await fetchJson<{ items: QlibPortfolio[] }>(`/api/qlib/portfolios?limit=${limit}`);
  return res.items;
}

export async function generateQlibReport(payload: {
  report_type: "qlib_factor_mining" | "qlib_portfolio_backtest";
  run_id?: string;
  portfolio_id?: string;
  backtest_id?: string;
  enable_pdf?: boolean;
}): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/reports/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
