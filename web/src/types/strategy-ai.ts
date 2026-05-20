export type StrategyIndicatorSpec = {
  type: string;
  name?: string | null;
  field?: string;
  window?: number | null;
  fast_window?: number | null;
  slow_window?: number | null;
  params?: Record<string, unknown>;
};

export type StrategyRiskSpec = {
  max_position_pct: number;
  max_positions: number;
  stop_loss: boolean;
  stop_loss_atr_multiple?: number | null;
  take_profit: boolean;
  notes: string[];
};

export type StrategyExecutionSpec = {
  signal_time: string;
  trade_time: string;
  fee_bps: number;
  slippage_bps: number;
  rebalance_frequency: string;
};

export type StrategySpec = {
  name: string;
  description: string;
  asset_class: string;
  universe: string[];
  timeframe: string;
  direction: string;
  indicators: StrategyIndicatorSpec[];
  entry_rules: string[];
  exit_rules: string[];
  ranking?: string | null;
  risk: StrategyRiskSpec;
  execution: StrategyExecutionSpec;
  assumptions: string[];
  rationale: string[];
  disclaimer: string;
};

export type StrategyValidationIssue = {
  severity: string;
  code: string;
  message: string;
  field?: string | null;
};

export type StrategyValidationResult = {
  is_valid: boolean;
  issues: StrategyValidationIssue[];
  normalized_spec: StrategySpec;
  timing_assumptions: string[];
  supported_features: string[];
  disclaimer: string;
};

export type GenerateStrategyPayload = {
  prompt: string;
  provider?: string | null;
  market?: string | null;
  universe?: string[] | null;
  timeframe?: string;
  risk_profile?: string;
  language?: string;
};

export type GenerateStrategyResult = {
  spec: StrategySpec;
  validation: StrategyValidationResult;
  provider: string;
  llm_ready: boolean;
  used_fallback: boolean;
  raw_model_output?: Record<string, unknown> | null;
};

export type RunAiBacktestPayload = {
  spec: StrategySpec;
  start_date?: string | null;
  end_date?: string | null;
  universe?: string[] | null;
  initial_cash: number;
  fee_bps?: number | null;
  use_adj?: boolean;
  run_validation?: boolean;
};

export type RunAiBacktestResult = {
  backtest_id: string;
  created_at: string;
  summary: Record<string, unknown>;
  validation: StrategyValidationResult;
  data_health?: Record<string, unknown> | null;
};

export type LLMProviderStatus = {
  default_provider: string;
  providers: Array<{
    name: string;
    model: string;
    ready: boolean;
    endpoint: string;
    reason?: string | null;
  }>;
};
