import { fetchJson, apiBasePath } from "@/lib/api/client";
import { adaptRunItem, type BackendRunRecord } from "@/lib/adapters/runAdapter";
import { allowMockFallback } from "@/lib/api/mockPolicy";
import { mockRuns } from "@/lib/mock/runs";
import type { RunItem, RunMeta } from "@/types/run";

export async function listRuns(limit = 50): Promise<RunItem[]> {
  try {
    const raw = await fetchJson<BackendRunRecord[]>(`/api/runs?limit=${limit}`);
    return raw.map(adaptRunItem);
  } catch {
    if (!allowMockFallback()) throw new Error("Failed to load runs from backend");
    return mockRuns;
  }
}

export async function getRunMeta(calcBatchId: string): Promise<RunMeta | null> {
  try {
    return await fetchJson<RunMeta>(`/api/runs/${encodeURIComponent(calcBatchId)}/meta`);
  } catch {
    return null;
  }
}

export function runDownloadUrl(calcBatchId: string): string {
  const base = apiBasePath();
  return `${base}/api/runs/${encodeURIComponent(calcBatchId)}/download`;
}

