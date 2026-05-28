import { fetchJson } from "@/lib/api/client";

export type DataSourceStatus = {
  source_id: string;
  label: string;
  path: string;
  kind: string;
  exists: boolean;
  status: string;
  file_size_bytes?: number | null;
  mtime?: string | null;
  row_count?: number | null;
  asset_count?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  freshness_days?: number | null;
  days_since_latest?: number | null;
  is_blocking?: boolean;
  freshness_reason?: string | null;
  notes?: string[];
  child_count?: number | null;
  sample_children?: string[] | null;
  calendar_count?: number | null;
  instrument_counts?: Record<string, number> | null;
  feature_dir_count?: number | null;
  database_backed?: boolean;
  package_version?: string | null;
  available?: Record<string, boolean> | null;
  latest_query?: Record<string, unknown> | null;
};

export type DataHealthItem = {
  source_id: string;
  label?: string;
  status?: string;
  path?: string;
  reason?: string;
  updater_id?: string | null;
};

export type DataRecommendation = {
  source_id: string;
  status?: string;
  updater_id: string;
  label?: string;
  reason?: string;
};

export type DataPathAudit = {
  generated_at: string;
  overall_status: string;
  blocking_status?: "OK" | "WARN" | "BLOCKED";
  blockers?: DataHealthItem[];
  recommendations?: DataRecommendation[];
  status_counts: Record<string, number>;
  sources: DataSourceStatus[];
};

export type RunDailyMaintenancePayload = {
  dry_run?: boolean;
  refresh_factor_registry?: boolean;
  refresh_stock_screen?: boolean;
  run_radar_smoke?: boolean;
  run_external_updater?: boolean;
  updater_id?: string | null;
};

export type DataMaintenanceRun = {
  run_id: string;
  generated_at: string;
  dry_run: boolean;
  overall_status: string;
  audit: DataPathAudit;
  audit_before: DataPathAudit;
  steps: Record<string, unknown>[];
  artifacts?: Record<string, string> | null;
};

export async function getDataPathAudit(): Promise<DataPathAudit> {
  return fetchJson<DataPathAudit>("/api/data-maintenance/paths");
}

export async function runDailyDataMaintenance(payload: RunDailyMaintenancePayload): Promise<DataMaintenanceRun> {
  return fetchJson<DataMaintenanceRun>("/api/data-maintenance/daily-update", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getLatestDataMaintenanceReport(): Promise<DataMaintenanceRun> {
  return fetchJson<DataMaintenanceRun>("/api/data-maintenance/latest");
}
