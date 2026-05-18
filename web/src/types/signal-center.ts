export type SignalStatus = "DRAFT" | "FILTERED" | "ACTIVE" | "NOTIFIED" | "MONITORED" | "CLOSED" | "BLOCKED" | "INVALIDATED";
export type Side = "LONG" | "SHORT" | "NEUTRAL";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "BLOCKED";
export type ExecutionMode = "live" | "shadow" | "all";
export type OutcomeStatus = "PENDING_OUTCOME" | "SHADOW_PENDING" | "SHADOW_EVALUATED" | "OPEN" | "CLOSED" | "NO_TRADE" | "UNKNOWN";

export type Signal = {
  signal_id: string;
  execution_mode?: ExecutionMode;
  not_executable?: boolean;
  instrument: string;
  market: string;
  asset_type: string;
  timeframe: string;
  side: Side;
  signal_time: string;
  entry_type: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  confidence: number;
  risk_level: RiskLevel;
  regime_label: string;
  volatility_state: string;
  tail_risk_state: string;
  position_scale: number;
  reason_tags: string[];
  status: SignalStatus;
  signal_template: string;
  expected_holding_bars: number;
  created_at: string;
  updated_at: string;
  realized_pnl?: number;
  holding_bars?: number;
  score?: number | null;
  score_percentile?: number | null;
  effective_trade_date?: string | null;
  freshness_note?: string | null;
  proposed_position_scale?: number | null;
  router_risk_scale?: number | null;
  router_block_reason?: string | null;
  router_threshold_profile?: string | null;
};

export type RouterDecision = {
  router_version?: string;
  source?: string;
  current_regime?: string;
  regime_snapshot_time?: string | null;
  enabled_templates?: string[];
  blocked_templates?: string[];
  risk_scale?: number;
  turnover_limit?: number;
  threshold_profile?: string;
  block_reason?: string | null;
  is_live_blocked?: boolean;
};

export type RegimeFreshness = {
  regime_date?: string | null;
  signal_date?: string | null;
  provider_uri?: string | null;
  universe?: string | null;
  freshness_lag_days?: number | null;
  status?: string | null;
  is_stale?: boolean;
  block_reason?: string | null;
};

export type Paginated<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
  status?: string;
  message?: string | null;
  generated_at?: string | null;
  signal_date?: string | null;
  data_source?: { provider_uri?: string; universe?: string } | null;
  data_health?: {
    blocking_status?: "OK" | "WARN" | "BLOCKED";
    message?: string;
    reason?: string;
    source_id?: string;
    latest_date?: string | null;
  } | null;
  source_run_id?: string | null;
  snapshot_path?: string | null;
  execution_mode?: ExecutionMode;
  router_decision?: RouterDecision | null;
  counts?: {
    live_active_count?: number;
    router_blocked_count?: number;
    shadow_count?: number;
  } | null;
  regime_freshness?: RegimeFreshness | null;
};

export type RegimeSnapshot = {
  snapshot_time: string;
  regime_label: string;
  risk_regime?: string;
  market_state?: string;
  event_context?: string;
  trend_strength?: string;
  cluster_label?: string;
  geo_energy_flag?: boolean;
  cpd_score: number;
  cluster_id: number;
  severity_score: number;
  volatility_state: string;
  liquidity_state: string;
  tail_risk_state: string;
  market_risk_level?: string;
  shock_proximity?: string;
  data_source?: string;
  fwd5_down_prob?: number | null;
  fwd10_es05?: number | null;
  cluster_persist_prob?: number | null;
};

export type SimilarPeriodLookupItem = {
  asof_date: string;
  current_cluster_label: number;
  current_is_noise: boolean;
  match_rank: number;
  matched_date: string;
  distance_total: number;
  distance_level1: number;
  distance_level2: number;
  distance_sequence: number;
  matched_risk_regime: string;
  matched_market_state: string;
  matched_event_context: string;
  matched_fwd5_return?: number | null;
  matched_fwd10_return?: number | null;
  matched_fwd10_es05?: number | null;
  model_version: string;
};

export type CurrentStateProfile = {
  asof_date: string;
  risk_regime: string;
  market_state: string;
  event_context: string;
  trend_strength: string;
  market_risk_level: string;
  dbscan_label: number;
  is_noise: boolean;
  nearest_cluster_label: string;
  similar_period_count: number;
  similarity_confidence: number;
  model_version: string;
  computed_at: string;
};

export type SignalDetail = {
  signal: Signal;
  regime_snapshot: RegimeSnapshot;
  factor_contributions: Array<{
    factor: string;
    raw_value?: number;
    zscore?: number;
    contribution: number;
    direction?: string;
  }>;
  filter_results: {
    allow_signal: boolean;
    risk_level: string;
    filter_reasons: string[];
    suppressed_alternatives: string[];
  };
  notification_logs: Array<{
    time: string;
    channel: string;
    title: string;
    signal_id: string | null;
  }>;
  performance_tracking: {
    status?: OutcomeStatus | string;
    execution_mode?: ExecutionMode;
    unrealized_pnl: number | null;
    realized_pnl?: number | null;
    mfe: number | null;
    mae: number | null;
    bars_elapsed: number;
    entry_date?: string | null;
    last_date?: string | null;
    source_run_id?: string | null;
  };
  outcome_status?: OutcomeStatus | string;
  outcome?: SignalOutcome | null;
  similar_signals: Signal[];
};

export type PerformanceSummary = {
  data_source?: string;
  execution_mode?: ExecutionMode;
  source_run_id?: string | null;
  source_snapshot_id?: string | null;
  computed_at?: string | null;
  status?: string;
  total_signals?: number;
  evaluated_signals?: number;
  pending_signals?: number;
  no_trade_signals?: number;
  avg_forward_return?: number;
  win_rate?: number;
  profit_factor?: number;
  max_drawdown?: number;
  avg_holding_bars?: number;
  summary: {
    total_signals: number;
    evaluated_signals?: number;
    pending_signals?: number;
    no_trade_signals?: number;
    win_rate: number;
    avg_pnl: number;
    avg_forward_return?: number;
    profit_factor: number;
    max_drawdown: number;
    avg_holding_bars: number;
  };
  breakdowns: {
    by_regime: Array<{ label?: string; regime_label?: string; count?: number; win_rate: number; avg_pnl: number }>;
    by_confidence_bucket: Array<{ label?: string; bucket?: string; count?: number; win_rate: number; avg_pnl: number }>;
    by_template: Array<{ label?: string; template?: string; count?: number; win_rate: number; avg_pnl: number }>;
    by_shock_window?: Array<{ label?: string; window?: string; count?: number; win_rate: number; avg_pnl: number }>;
    by_risk_level?: Array<{ label?: string; count?: number; win_rate: number; avg_pnl: number }>;
  };
};

export type TimeSeriesPoint = {
  date: string;
  metric?: string;
  value: number;
  granularity?: string;
  count?: number;
};

export type SignalOutcome = {
  signal_id: string;
  execution_mode?: ExecutionMode;
  not_executable?: boolean;
  source_run_id?: string | null;
  signal_date?: string | null;
  instrument?: string | null;
  name?: string | null;
  side?: string | null;
  regime_label?: string | null;
  signal_template?: string | null;
  risk_level?: string | null;
  confidence?: number | null;
  entry_date?: string | null;
  entry_price?: number | null;
  last_date?: string | null;
  last_price?: number | null;
  holding_bars: number;
  expected_holding_bars?: number | null;
  mfe?: number | null;
  mae?: number | null;
  realized_pnl?: number | null;
  unrealized_pnl?: number | null;
  outcome_status: OutcomeStatus | string;
  reason?: string | null;
  price_path?: Array<{ date: string; close: number | null; return: number | null }>;
};

export type SignalSnapshotHistory = {
  items: Array<{
    run_id?: string | null;
    status?: string | null;
    generated_at?: string | null;
    signal_date?: string | null;
    data_health?: Paginated<Signal>["data_health"];
    generated_count?: number | null;
    blocked_count?: number | null;
    counts?: Paginated<Signal>["counts"];
    router_decision?: RouterDecision | null;
    regime_freshness?: RegimeFreshness | null;
    snapshot_path?: string | null;
    data_source?: { provider_uri?: string; universe?: string } | string | null;
  }>;
  total: number;
  latest?: SignalSnapshotHistory["items"][number] | null;
  retention_count?: number;
};

export type StrategyRouterCurrent = {
  router_version: string;
  source?: string;
  current_regime: string;
  regime_snapshot_time?: string | null;
  enabled_templates: string[];
  blocked_templates: string[];
  risk_scale: number;
  turnover_limit?: number;
  threshold_profile: string;
  block_reason?: string | null;
  is_live_blocked?: boolean;
  regime_freshness?: RegimeFreshness | null;
};

export type StrategyRouterLog = {
  changed_at: string;
  changed_by: string;
  regime: string;
  field: string;
  old_value: string;
  new_value: string;
};

export type ShockEvent = {
  event_id: string;
  event_date: string;
  event_type: string;
  severity: number;
  detected_regime: string;
  status: string;
};

export type EnumsMeta = Record<string, string[]>;
