export type BacktestRunPayload = {
  strategy_id?: string | null;
  portfolio_id?: string | null;
  params: Record<string, unknown>;
  start_date?: string | null;
  end_date?: string | null;
  universe?: string[] | null;
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
};

export type EquityPoint = {
  trade_date: string;
  equity: number;
  net_ret: number;
};

export type EquityCurve = {
  items: EquityPoint[];
  row_count: number;
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
  } | null;
};
