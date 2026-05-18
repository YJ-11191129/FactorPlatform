import { fetchJson } from "@/lib/api/client";
import type { ResearchQualityReport } from "@/types/qlib-research";

function toQuery(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    q.set(key, String(value));
  }
  const text = q.toString();
  return text ? `?${text}` : "";
}

export function evaluateResearchQuality(payload: {
  source_run_id: string;
  source_type?: string;
  thresholds?: Record<string, unknown> | null;
}) {
  return fetchJson<ResearchQualityReport>("/api/research-quality/evaluate", {
    method: "POST",
    body: JSON.stringify({ source_type: "qlib_factor_mining", ...payload }),
  });
}

export async function listResearchQualityRuns(limit = 50) {
  const res = await fetchJson<{ items: ResearchQualityReport[] }>(`/api/research-quality/runs${toQuery({ limit })}`);
  return res.items;
}

export function getResearchQualityRun(sourceRunId: string) {
  return fetchJson<ResearchQualityReport>(`/api/research-quality/runs/${encodeURIComponent(sourceRunId)}`);
}

