export type QlibStatus = {
  status: "READY" | "QLIB_NOT_READY" | "DATA_NOT_READY" | string;
  provider_uri: string;
  universe: string;
  freq: string;
  package: string;
  package_available: boolean;
  package_version?: string | null;
  data_available: boolean;
  checks: Record<string, boolean>;
  notes: string[];
};

export type QlibFactorMiningRun = {
  run_id: string;
  status: string;
  factor_count: number;
  date_range: Record<string, unknown>;
  artifact_path: string;
  top_factors: Record<string, unknown>[];
  generated_at?: string;
  universe?: string;
  provider_uri?: string;
  quality_gate?: ResearchQualitySummary | null;
  promotion_status?: string | null;
  not_executable?: boolean | null;
  quality_reason_codes?: string[];
};

export type QlibPortfolio = {
  portfolio_id: string;
  created_at: string;
  mining_run_id: string;
  provider_uri?: string | null;
  universe?: string | null;
  selected_factors: string[];
  weighting_method: string;
  weights: Record<string, number>;
  signal_artifact_path: string;
  signal_count: number;
  date_count: number;
  timing_note: string;
  quality_gate?: ResearchQualitySummary | null;
  promotion_status?: string | null;
  not_executable?: boolean;
  quality_reason_codes?: string[];
};

export type ResearchQualityCheck = {
  check_id: string;
  status: "PASS" | "WARN" | "FAIL" | "NOT_TESTED" | string;
  reason_code: string;
  message: string;
  evidence?: Record<string, unknown>;
  threshold?: Record<string, unknown>;
};

export type ResearchQualitySummary = {
  source_run_id?: string;
  quality_status?: "PASS" | "WARN" | "FAIL" | string;
  quality_score?: number;
  promotion_status?: string;
  reason_codes?: string[];
  research_ops_object_id?: string | null;
  artifact_path?: string;
  factor_status?: Record<string, string>;
};

export type ResearchQualityReport = ResearchQualitySummary & {
  source_type: string;
  evaluated_at: string;
  asof_date?: string;
  not_executable: boolean;
  checks: ResearchQualityCheck[];
  thresholds: Record<string, unknown>;
  findings_path?: string;
  source_artifact_path?: string;
  timing_note?: string;
};

export type QlibMiningPayload = {
  provider_uri?: string | null;
  universe: string;
  start_date?: string | null;
  end_date?: string | null;
  horizon: number;
  quantiles: number;
  top_k: number;
  freq?: string;
  factor_pool?: string[] | null;
  factor_limit?: number | null;
};

export type BuildQlibPortfolioPayload = {
  mining_run_id: string;
  selected_factors?: string[] | null;
  weighting_method: "equal" | "ic_weighted" | "rank_ic_weighted" | string;
  top_n: number;
  long_top_n: number;
};
