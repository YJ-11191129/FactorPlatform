import type { RunItem } from "@/types/run";

export const mockRuns: RunItem[] = [
  {
    calc_batch_id: "batch_20260320_101226_xxx",
    task_name: "MOM_RET_N_D_V1",
    task_type: "run-qlib",
    submitted_at: "2026-03-20T10:12:26Z",
    finished_at: "2026-03-20T10:12:31Z",
    duration_sec: 5,
    status: "success",
    message: "数据源：qlib_bin",
    artifact_count: 1,
  },
  {
    calc_batch_id: "batch_20260320_093144_yyy",
    task_name: "TREND_MA_BIAS_N_D_V1",
    task_type: "run-demo",
    submitted_at: "2026-03-20T09:31:44Z",
    finished_at: "2026-03-20T09:31:45Z",
    duration_sec: 1,
    status: "success",
    message: "demo 数据源",
    artifact_count: 1,
  },
];

