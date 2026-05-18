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

export function listLiveSignals(query: SignalQuery = {}) {
  return fetchJson<Paginated<Signal>>(`/api/v1/signals/live${toQuery(query)}`);
}

export function listShadowSignals(query: SignalQuery = {}) {
  return fetchJson<Paginated<Signal>>(`/api/v1/signals/shadow${toQuery(query)}`);
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
    fetchJson<SignalDetail>(`/api/v1/signals/${signalId}`),
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
  return fetchJson<RegimeSnapshot>("/api/v1/regime/current");
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
  return fetchJson<{ items: ShockEvent[] }>("/api/v1/shocks");
}

export function getNotificationLogs() {
  return fetchJson<{
    items: Array<{ time: string; channel: string; title: string; signal_id: string | null }>;
  }>("/api/v1/notifications/logs");
}

export function getEnumsMeta() {
  return fetchJson<EnumsMeta>("/api/v1/metadata/enums");
}

export function getSignalTemplates() {
  return fetchJson<{ items: Array<{ template: string; description: string }> }>("/api/v1/metadata/signal-templates");
}
