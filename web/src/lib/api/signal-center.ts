import { fetchJson } from "@/lib/api/client";
import type {
  CurrentStateProfile,
  EnumsMeta,
  ExecutionMode,
  Paginated,
  PerformanceSummary,
  RegimeSnapshot,
  SimilarPeriodLookupItem,
  ShockEvent,
  Signal,
  SignalDetail,
  SignalOutcome,
  SignalSnapshotHistory,
  StrategyRouterCurrent,
  StrategyRouterLog,
  TimeSeriesPoint,
} from "@/types/signal-center";

export type SignalQuery = Partial<{
  market: string;
  asset_type: string;
  timeframe: string;
  side: string;
  regime_label: string;
  risk_level: string;
  status: string;
  instrument: string;
  signal_template: string;
  confidence_min: number;
  confidence_max: number;
  page: number;
  page_size: number;
}>;

function toQuery(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") usp.set(k, String(v));
  }
  const raw = usp.toString();
  return raw ? `?${raw}` : "";
}

const demoSignals: Signal[] = [
  {
    signal_id: "demo_signal_001",
    instrument: "510300.SH",
    market: "CN",
    asset_type: "ETF",
    timeframe: "1D",
    side: "LONG",
    signal_time: "2026-05-21T10:00:00+08:00",
    entry_type: "NEXT_BAR_OBSERVATION",
    entry_price: 4.18,
    stop_loss: 4.08,
    take_profit: 4.32,
    confidence: 0.82,
    risk_level: "MEDIUM",
    regime_label: "POST_SHOCK_REBOUND",
    volatility_state: "HIGH_VOL",
    tail_risk_state: "ELEVATED",
    position_scale: 0.45,
    reason_tags: ["post_shock_rebound", "liquidity_recovery_confirmed", "trend_strength_confirmed"],
    status: "ACTIVE",
    signal_template: "POST_SHOCK_REBOUND_LONG_V1",
    expected_holding_bars: 8,
    created_at: "2026-05-21T10:00:00+08:00",
    updated_at: "2026-05-21T10:00:00+08:00",
    score: 2.08,
    score_percentile: 0.88,
    effective_trade_date: "2026-05-22",
  },
  {
    signal_id: "demo_signal_002",
    instrument: "159915.SZ",
    market: "CN",
    asset_type: "ETF",
    timeframe: "1D",
    side: "LONG",
    signal_time: "2026-05-21T10:30:00+08:00",
    entry_type: "NEXT_BAR_OBSERVATION",
    entry_price: 1.88,
    stop_loss: 1.82,
    take_profit: 1.98,
    confidence: 0.74,
    risk_level: "MEDIUM",
    regime_label: "TREND_RISK_ON",
    volatility_state: "NORMAL_VOL",
    tail_risk_state: "NORMAL",
    position_scale: 0.35,
    reason_tags: ["trend_strength_confirmed", "volume_expansion", "candidate_pool_top_quantile"],
    status: "MONITORED",
    signal_template: "TREND_CONTINUATION_LONG_V2",
    expected_holding_bars: 12,
    created_at: "2026-05-21T10:30:00+08:00",
    updated_at: "2026-05-21T10:30:00+08:00",
    score: 1.62,
    score_percentile: 0.79,
    effective_trade_date: "2026-05-22",
  },
  {
    signal_id: "demo_signal_003",
    instrument: "000300.SH",
    market: "CN",
    asset_type: "INDEX",
    timeframe: "1D",
    side: "NEUTRAL",
    signal_time: "2026-05-21T11:00:00+08:00",
    entry_type: "OBSERVE_ONLY",
    entry_price: 0,
    stop_loss: 0,
    take_profit: 0,
    confidence: 0.61,
    risk_level: "BLOCKED",
    regime_label: "LIQUIDITY_SHOCK",
    volatility_state: "EXTREME_VOL",
    tail_risk_state: "EXTREME",
    position_scale: 0,
    reason_tags: ["shock_window_active", "liquidity_too_tight", "router_blocked_template"],
    status: "BLOCKED",
    signal_template: "OBSERVE_ONLY_CRISIS_V1",
    expected_holding_bars: 0,
    created_at: "2026-05-21T11:00:00+08:00",
    updated_at: "2026-05-21T11:00:00+08:00",
    score: 0.42,
    score_percentile: 0.52,
    effective_trade_date: "2026-05-22",
    router_block_reason: "EXTREME_RISK_BLOCKED",
  },
];

function demoPaginated(items = demoSignals): Paginated<Signal> {
  return {
    items,
    page: 1,
    page_size: items.length,
    total: items.length,
    has_more: false,
    status: "DEMO_FALLBACK",
    generated_at: "2026-05-21T15:56:01Z",
    signal_date: "2026-05-21",
    data_source: { universe: "csi300" },
    data_health: { blocking_status: "WARN", message: "信号源暂不可用，当前展示只读演示快照。" },
    counts: {
      live_active_count: items.filter((item) => item.status === "ACTIVE").length,
      router_blocked_count: items.filter((item) => item.status === "BLOCKED").length,
      shadow_count: items.filter((item) => item.status === "BLOCKED").length,
    },
    regime_freshness: {
      regime_date: "2026-05-21",
      signal_date: "2026-05-21",
      freshness_lag_days: 0,
      status: "WARN",
    },
  };
}

export function listLiveSignals(query: SignalQuery = {}) {
  return fetchJson<Paginated<Signal>>(`/api/v1/signals/live${toQuery(query)}`).catch(() => demoPaginated());
}

export function listShadowSignals(query: SignalQuery = {}) {
  return fetchJson<Paginated<Signal>>(`/api/v1/signals/shadow${toQuery(query)}`).catch(() => demoPaginated(demoSignals.filter((item) => item.status === "BLOCKED")));
}

export function refreshLiveSignals(payload: { provider_uri?: string; universe?: string; topn?: number; dry_run?: boolean } = {}) {
  return fetchJson<{
    status: string;
    message?: string;
    generated_count: number;
    blocked_count: number;
    generated_at: string;
    signal_date?: string | null;
    data_health?: Paginated<Signal>["data_health"];
    snapshot_path?: string;
  }>("/api/v1/signals/refresh", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSignalDetail(signalId: string, executionMode?: Extract<ExecutionMode, "live" | "shadow">) {
  return fetchJson<SignalDetail>(`/api/v1/signals/by-id/${signalId}${toQuery({ execution_mode: executionMode })}`).catch(() =>
    fetchJson<SignalDetail>(`/api/v1/signals/${signalId}`).catch(() => {
      const signal = demoSignals.find((item) => item.signal_id === signalId) || demoSignals[0];
      return {
        signal,
        regime_snapshot: {
          snapshot_time: "2026-05-21T15:56:01Z",
          regime_label: signal.regime_label,
          cpd_score: 0.72,
          cluster_id: 3,
          severity_score: 0.68,
          volatility_state: signal.volatility_state,
          liquidity_state: "TIGHT",
          tail_risk_state: signal.tail_risk_state,
          shock_proximity: "RECENT",
          market_risk_level: signal.risk_level,
        },
        factor_contributions: [
          { factor: "动量", contribution: 0.32, direction: "positive" },
          { factor: "量能", contribution: 0.21, direction: "positive" },
          { factor: "波动", contribution: -0.16, direction: "negative" },
        ],
        filter_results: {
          allow_signal: signal.status !== "BLOCKED",
          risk_level: signal.risk_level,
          filter_reasons: signal.reason_tags,
          suppressed_alternatives: [],
        },
        notification_logs: [{ time: signal.signal_time, channel: "system", title: "Signal snapshot ready", signal_id: signal.signal_id }],
        performance_tracking: {
          status: "PENDING_OUTCOME",
          unrealized_pnl: null,
          mfe: null,
          mae: null,
          bars_elapsed: 0,
          execution_mode: signal.execution_mode,
        },
        outcome_status: "PENDING_OUTCOME",
        outcome: null,
        similar_signals: demoSignals,
      };
    }),
  );
}

export function listSignalSnapshots(limit = 50) {
  return fetchJson<SignalSnapshotHistory>(`/api/v1/signals/snapshots${toQuery({ limit })}`);
}

export function listSignalOutcomes(query: { signal_id?: string; status?: string; execution_mode?: ExecutionMode; limit?: number; offset?: number } = {}) {
  return fetchJson<{ items: SignalOutcome[]; total: number; data_source: string; computed_at?: string | null; source_run_id?: string | null }>(
    `/api/v1/signals/outcomes${toQuery(query)}`,
  );
}

export function getSignalOutcome(signalId: string, executionMode: ExecutionMode = "live") {
  return fetchJson<SignalOutcome>(`/api/v1/signals/outcomes/${signalId}${toQuery({ execution_mode: executionMode })}`);
}

export function refreshSignalOutcomes(payload: { provider_uri?: string; universe?: string; horizon_days?: number; dry_run?: boolean } = {}) {
  return fetchJson<{
    status: string;
    data_source: string;
    computed_at: string;
    source_run_id?: string | null;
    generated_count: number;
    pending_count: number;
    outcome_path?: string;
    dry_run?: boolean;
  }>("/api/v1/signals/outcomes/refresh", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listSignalHistory(query: SignalQuery = {}) {
  return fetchJson<Paginated<Signal>>(`/api/v1/signals/history${toQuery(query)}`).catch(() =>
    fetchJson<Paginated<Signal>>(`/api/v1/signals/live${toQuery(query)}`),
  );
}

export function getPerformanceSummary(executionMode: ExecutionMode = "live") {
  return fetchJson<PerformanceSummary>(`/api/v1/signals/performance/summary${toQuery({ execution_mode: executionMode })}`);
}

export function getPerformanceTimeseries(metric = "cum_pnl", granularity = "day", executionMode: ExecutionMode = "live") {
  return fetchJson<{ items: TimeSeriesPoint[] }>(
    `/api/v1/signals/performance/timeseries${toQuery({ metric, granularity, execution_mode: executionMode })}`,
  );
}

export function getPerformanceAttribution(executionMode: ExecutionMode = "live") {
  return fetchJson<{
    data_source?: string;
    execution_mode?: ExecutionMode;
    source_run_id?: string | null;
    computed_at?: string | null;
    by_regime: Array<{ label: string; contribution: number }>;
    by_template: Array<{ label: string; contribution: number }>;
    by_shock_window: Array<{ label: string; contribution: number }>;
    by_risk_level: Array<{ label: string; contribution: number }>;
  }>(`/api/v1/signals/performance/attribution${toQuery({ execution_mode: executionMode })}`);
}

export function getRegimeCurrent() {
  return fetchJson<RegimeSnapshot>("/api/v1/regime/current").catch(() => ({
    snapshot_time: "2026-05-21T15:56:01Z",
    regime_label: "POST_SHOCK_REBOUND",
    cpd_score: 0.72,
    cluster_id: 3,
    severity_score: 0.68,
    volatility_state: "HIGH_VOL",
    liquidity_state: "TIGHT",
    tail_risk_state: "ELEVATED",
    market_risk_level: "MEDIUM",
    shock_proximity: "RECENT",
  }));
}

export function getRegimeHistory() {
  return fetchJson<{
    items: Array<{
      time: string;
      regime_label: string;
      cpd_score: number;
      severity_score: number;
      cluster_id: number;
      vix: number;
      vrp: number;
      illiq: number;
    }>;
  }>("/api/v1/regime/history");
}

export function getRegimeTimeline() {
  return fetchJson<{ items: Array<{ start: string; end: string; regime_label: string }> }>("/api/v1/regime/timeline");
}

export function getRegimeSimilarPeriods(topk = 20) {
  return fetchJson<{ items: SimilarPeriodLookupItem[] }>(`/api/v1/regime/similar-periods${toQuery({ topk })}`);
}

export function getCurrentStateProfile() {
  return fetchJson<CurrentStateProfile>("/api/v1/regime/current-state-profile");
}

export function recomputeRegimeSimilarPeriods() {
  return fetchJson<{ status: string; lookup_rows: number; profile_rows: number; asof_date?: string | null }>(
    "/api/v1/regime/similar-periods/recompute",
    { method: "POST" },
  );
}

export function getStrategyRouterCurrent() {
  return fetchJson<StrategyRouterCurrent>("/api/v1/strategy-router/current");
}

export function getStrategyRouterHistory() {
  return fetchJson<{ items: StrategyRouterLog[] }>("/api/v1/strategy-router/history");
}

export function getShockEvents() {
  return fetchJson<{ items: ShockEvent[] }>("/api/v1/shocks").catch(() => ({ items: [] }));
}

export function getNotificationLogs() {
  return fetchJson<{
    items: Array<{ time: string; channel: string; title: string; signal_id: string | null }>;
  }>("/api/v1/notifications/logs").catch(() => ({
    items: [{ time: "2026-05-21T15:56:01Z", channel: "system", title: "信号快照已加载", signal_id: null }],
  }));
}

export function getEnumsMeta(): Promise<EnumsMeta> {
  return fetchJson<EnumsMeta>("/api/v1/metadata/enums").catch(() => ({
    side: ["LONG", "SHORT", "NEUTRAL"],
    risk_level: ["LOW", "MEDIUM", "HIGH", "BLOCKED"],
    status: ["ACTIVE", "MONITORED", "BLOCKED"],
    market: ["CN"],
    asset_type: ["ETF", "INDEX", "STOCK"],
    timeframe: ["1D"],
    regime_label: ["POST_SHOCK_REBOUND", "TREND_RISK_ON", "LIQUIDITY_SHOCK"],
    signal_template: ["POST_SHOCK_REBOUND_LONG_V1", "TREND_CONTINUATION_LONG_V2", "OBSERVE_ONLY_CRISIS_V1"],
  }));
}

export function getSignalTemplates() {
  return fetchJson<{ items: Array<{ template: string; description: string }> }>("/api/v1/metadata/signal-templates");
}
