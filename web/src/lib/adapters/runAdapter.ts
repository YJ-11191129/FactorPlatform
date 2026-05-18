import type { RunItem, RunStatus, RunTaskType } from "@/types/run";

export type BackendRunRecord = {
  calc_batch_id: string;
  created_at?: string;
  factor_name?: string;
  mode?: string;
  universe?: string | null;
  row_count?: number;
  params?: Record<string, unknown>;
  message?: string;
};

function normalizeTaskType(mode?: string): RunTaskType {
  if (!mode) return "run-qlib";
  if (mode === "demo") return "run-demo";
  if (mode === "qlib_bin") return "run-qlib";
  return "analysis";
}

function normalizeStatus(_raw: BackendRunRecord): RunStatus {
  return "success";
}

export function adaptRunItem(raw: BackendRunRecord): RunItem {
  const id = raw.calc_batch_id;
  const taskType = normalizeTaskType(raw.mode);
  const name = raw.factor_name ? `${raw.factor_name}` : id;
  return {
    calc_batch_id: id,
    task_name: name,
    task_type: taskType,
    submitted_at: raw.created_at || "",
    finished_at: raw.created_at || "",
    status: normalizeStatus(raw),
    message: raw.message,
    artifact_count: 1,
  };
}

