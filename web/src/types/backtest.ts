export type BacktestRunPayload = {
  strategy_id?: string | null;
  portfolio_id?: string | null;
  params: Record<string, unknown>;
  start_date?: string | null;
  end_date?: string | null;
  universe?: string[] | null;
  data_source?: string | null;
  provider_uri?: string | null;
  qlib_region?: string | null;
  qlib_universe?: string | null;
  initial_cash: number;
  fee_bps: number;
  use_adj?: boolean;
};

export type BacktestRunResult = {
  backtest_id: string;
  created_at: string;
  summary: Record<string, unknown>;
  data_health?: Record<string, unknown> | null;
};

export type BacktestSummary = {
  backtest_id: string;
  created_at: string;
  strategy_id: string;
  strategy_name: string;
  portfolio_id?: string | null;
  params: Record<string, unknown>;
  initial_cash: number;
  fee_bps: number;
  universe_size: number;
  metrics: Record<string, unknown>;
  strategy_spec?: Record<string, unknown>;
  validation?: Record<string, unknown>;
  price_data_source?: Record<string, unknown>;
  execution_model?: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
  data_health?: Record<string, unknown> | null;
  timing_note?: string;
  source?: string;
};

export type EquityPoint = {
  trade_date: string;
  equity: number;
  gross_ret?: number;
  turnover?: number;
  cost?: number;
  net_ret: number;
};

export type EquityCurve = {
  items: EquityPoint[];
  row_count: number;
  summary?: BacktestSummary | null;
};

export type BacktestDataStatus = {
  source: string;
  columns: string[];
  start_date: string;
  end_date: string;
  asset_count: number;
  row_count: number;
  data_health?: {
    blocking_status?: string;
    message?: string;
    status?: string;
    source_id?: string;
    latest_date?: string;
    effective_end_date?: string;
    using_latest_available?: boolean;
    price_data_source?: Record<string, unknown>;
  } | null;
};
