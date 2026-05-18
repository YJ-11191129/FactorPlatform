export type FactorStatus = "draft" | "research" | "online" | "offline";

export type FactorFrequency = "daily" | "weekly" | "monthly";

export type FactorDirection = "positive" | "negative" | "unknown";

export type FactorItem = {
  factor_id: string;
  factor_name: string;
  display_name: string;
  category: string;
  tags: string[];
  frequency: FactorFrequency;
  market_scope: string[];
  direction: FactorDirection;
  coverage?: number;
  missing_rate?: number;
  ic_mean?: number;
  rank_ic?: number;
  latest_run_at?: string;
  status: FactorStatus;
  owner?: string;
  version?: string;
};

export type FactorDetail = FactorItem & {
  description?: string;
  formula?: string;
  data_source?: string[];
  neutralization?: string[];
  winsorize?: string;
  standardize?: string;
  dependencies?: string[];
  code_snippet?: string;
  diagnostics?: {
    skew?: number;
    kurtosis?: number;
    turnover?: number;
  };
};

