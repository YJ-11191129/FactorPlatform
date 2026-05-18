export type ResearchOpsStatus =
  | "OK"
  | "WARN"
  | "BLOCKED"
  | "SUCCESS"
  | "FAILED"
  | "PENDING"
  | "NO_TRADE"
  | "SHADOW_EVALUATED"
  | "CLOSED"
  | "OPEN"
  | string;

export type ResearchOpsObjectType =
  | "data_snapshot"
  | "factor_run"
  | "validation_result"
  | "signal_snapshot"
  | "router_decision"
  | "portfolio_proposal"
  | "outcome"
  | "report_artifact"
  | "external_evidence"
  | "external_reference"
  | string;

export type ResearchOpsObject = {
  object_id: string;
  object_type: ResearchOpsObjectType;
  asof_date: string;
  created_at: string;
  status: ResearchOpsStatus;
  source_system: string;
  source_run_id?: string | null;
  artifact_paths: string[];
  summary: Record<string, unknown>;
  parents: string[];
  tags: string[];
  external_ids?: string[];
};

export type ResearchOpsEdge = {
  source: string;
  target: string;
  relation: string;
};

export type ResearchOpsMissingReference = {
  object_id?: string;
  artifact_path?: string;
  reason: string;
};

export type ResearchOpsLineage = {
  root: ResearchOpsObject;
  nodes: ResearchOpsObject[];
  edges: ResearchOpsEdge[];
  missing_references: ResearchOpsMissingReference[];
};

export type ResearchOpsDailyBrief = {
  asof_date: string;
  data_health: {
    status: ResearchOpsStatus;
    object_id?: string | null;
    blocking_status?: string | null;
    blockers: unknown[];
    recommendations: unknown[];
  };
  latest_signal_snapshot?: ResearchOpsObject | null;
  router_summary: {
    status_counts: Record<string, number>;
    latest_decision?: ResearchOpsObject | null;
    blocked_count?: number | null;
    risk_scale?: number | null;
    block_reason?: string | null;
  };
  shadow_summary: {
    shadow_count?: number | null;
    router_blocked_count?: number | null;
  };
  latest_outcome?: ResearchOpsObject | null;
  latest_reports: ResearchOpsObject[];
  open_gaps: { code: string; message: string }[];
  object_status_counts: Record<string, number>;
};
