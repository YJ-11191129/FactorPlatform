export type RunStatus = "queued" | "running" | "success" | "failed" | "cancelled";

export type RunTaskType = "run-demo" | "run-qlib" | "scoring" | "analysis";

export type RunItem = {
  calc_batch_id: string;
  task_name: string;
  task_type: RunTaskType;
  trigger_by?: string;
  submitted_at: string;
  finished_at?: string;
  duration_sec?: number;
  status: RunStatus;
  message?: string;
  artifact_count?: number;
};

export type RunMeta = Record<string, unknown>;

