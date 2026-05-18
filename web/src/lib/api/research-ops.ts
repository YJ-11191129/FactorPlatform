import { fetchJson } from "@/lib/api/client";
import type { ResearchOpsDailyBrief, ResearchOpsLineage, ResearchOpsObject } from "@/types/research-ops";

function toQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    q.set(key, String(value));
  }
  const text = q.toString();
  return text ? `?${text}` : "";
}

export function listResearchOpsObjects(params: {
  object_type?: string;
  asof_date?: string;
  source_run_id?: string;
  limit?: number;
} = {}) {
  return fetchJson<{ items: ResearchOpsObject[] }>(`/api/research-ops/objects${toQuery(params)}`);
}

export function getResearchOpsLineage(objectId: string) {
  return fetchJson<ResearchOpsLineage>(`/api/research-ops/lineage/${encodeURIComponent(objectId)}`);
}

export function getResearchOpsDailyBrief(asofDate?: string) {
  return fetchJson<ResearchOpsDailyBrief>(`/api/research-ops/daily-brief${toQuery({ asof_date: asofDate })}`);
}

export function rebuildResearchOpsIndex(reset = false) {
  return fetchJson<Record<string, unknown>>(`/api/research-ops/rebuild-index${toQuery({ reset })}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

