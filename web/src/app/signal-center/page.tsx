"use client";

import { Alert, Button, Col, Input, Row, Segmented, Select, Skeleton, Slider, Space, Tag, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { MetricCard } from "@/components/common/MetricCard";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { ConfidenceBar } from "@/components/signal/ConfidenceBar";
import { ReasonTagList } from "@/components/signal/ReasonTagList";
import { RegimeBadge, RiskBadge, SideBadge, StatusBadge } from "@/components/signal/SignalBadge";
import { getEnumsMeta, getNotificationLogs, getRegimeCurrent, getShockEvents, listLiveSignals, listShadowSignals, refreshLiveSignals } from "@/lib/api/signal-center";
import type { ApiError } from "@/lib/api/client";
import type { EnumsMeta, Paginated, RegimeSnapshot, ShockEvent, Signal } from "@/types/signal-center";

type LoadState = "loading" | "error" | "ready";
type ViewMode = "live" | "shadow";

type Filters = {
  market?: string;
  asset_type?: string;
  instrument?: string;
  timeframe?: string;
  side?: string;
  risk_level?: string;
  regime_label?: string;
  status?: string;
  signal_template?: string;
  confidence_min?: number;
};

const defaultFilters: Filters = { confidence_min: 0.4 };

type LiveMeta = Omit<Paginated<Signal>, "items" | "page" | "page_size" | "total" | "has_more">;

export default function SignalCenterPage() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>("loading");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [enums, setEnums] = useState<EnumsMeta>({});
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [viewMode, setViewMode] = useState<ViewMode>("live");
  const [signals, setSignals] = useState<Signal[]>([]);
  const [liveMeta, setLiveMeta] = useState<LiveMeta>({});
  const [regime, setRegime] = useState<RegimeSnapshot | null>(null);
  const [shocks, setShocks] = useState<ShockEvent[]>([]);
  const [notifications, setNotifications] = useState<Array<{ time: string; title: string; channel: string; signal_id: string | null }>>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (nextFilters: Filters, nextMode: ViewMode, attempt = 0) => {
    setState("loading");
    setErrorMsg("");
    const signalRequest = nextMode === "shadow" ? listShadowSignals({ ...nextFilters, page_size: 50 }) : listLiveSignals({ ...nextFilters, page_size: 50 });
    const [liveRes, metaRes, regimeRes, notificationRes, shockRes] = await Promise.allSettled([
      signalRequest,
      getEnumsMeta(),
      getRegimeCurrent(),
      getNotificationLogs(),
      getShockEvents(),
    ]);

    if (liveRes.status !== "fulfilled") {
      const e = liveRes.reason as ApiError;
      const msg = e?.message || "Request failed";
      if (attempt < 1) {
        setTimeout(() => load(nextFilters, nextMode, attempt + 1), 800);
        return;
      }
      setErrorMsg(msg);
      setState("error");
      return;
    }

    const { items, page, page_size, total, has_more, ...meta } = liveRes.value;
    void page;
    void page_size;
    void total;
    void has_more;
    setSignals(items || []);
    setLiveMeta(meta);
    setEnums(metaRes.status === "fulfilled" ? metaRes.value : {});
    setRegime(regimeRes.status === "fulfilled" ? regimeRes.value : null);
    setNotifications(notificationRes.status === "fulfilled" ? notificationRes.value.items.slice(0, 5) : []);
    setShocks(shockRes.status === "fulfilled" ? shockRes.value.items.slice(0, 5) : []);
    setState("ready");
  }, []);

  useEffect(() => {
    load(defaultFilters, "live");
  }, [load]);

  const summary = useMemo(() => {
    const active = signals.filter((s) => s.status === "ACTIVE").length;
    const blocked = signals.filter((s) => s.status === "BLOCKED").length;
    const longs = signals.filter((s) => s.side === "LONG").length;
    const shorts = signals.filter((s) => s.side === "SHORT").length;
    const avgConfidence = signals.length ? signals.reduce((sum, s) => sum + s.confidence, 0) / signals.length : 0;
    return {
      active,
      blocked,
      shadow: liveMeta.counts?.shadow_count ?? 0,
      currentRegime: regime?.regime_label || "UNKNOWN",
      marketRisk: regime?.market_risk_level || "N/A",
      longShortRatio: shorts === 0 ? `${longs}:0` : `${(longs / Math.max(shorts, 1)).toFixed(2)}:1`,
      avgConfidence: `${Math.round(avgConfidence * 100)}%`,
      dataHealth: liveMeta.data_health?.blocking_status || liveMeta.status || "UNKNOWN",
    };
  }, [signals, regime, liveMeta]);

  function updateFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    const next = { ...filters, [key]: value || undefined };
    setFilters(next);
  }

  function applyFilters() {
    load(filters, viewMode);
  }

  function resetFilters() {
    setFilters(defaultFilters);
    load(defaultFilters, viewMode);
  }

  function changeViewMode(nextMode: ViewMode) {
    setViewMode(nextMode);
    load(filters, nextMode);
  }

  async function refreshSnapshot() {
    setRefreshing(true);
    setErrorMsg("");
    try {
      await refreshLiveSignals();
      await load(filters, viewMode);
    } catch (e) {
      const err = e as ApiError;
      setErrorMsg(err?.message || "Signal refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  if (state === "loading") {
    return <Skeleton active paragraph={{ rows: 12 }} />;
  }

  if (state === "error") {
    return <ErrorState title="Signal Center load failed" subtitle={errorMsg || "Check API key in Settings"} onRetry={() => load(filters, viewMode)} />;
  }

  return (
    <PageContainer
      title="Research Terminal"
      subtitle="Regime-aware signal screening, Router decisions, shadow validation, and outcome evidence in one controlled workspace"
      extra={
        <Space>
          <Button onClick={resetFilters}>Reset</Button>
          <Segmented
            value={viewMode}
            onChange={(v) => changeViewMode(v as ViewMode)}
            options={[
              { label: "Live", value: "live" },
              { label: "Shadow Candidates", value: "shadow" },
            ]}
          />
          <Button type="primary" loading={refreshing} onClick={refreshSnapshot}>Refresh Snapshot</Button>
        </Space>
      }
    >
      <Row gutter={[12, 12]}>
        <Col xs={12} md={8} xl={4}><MetricCard title="Live Active" value={summary.active} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Router Blocked" value={summary.blocked} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Shadow Queue" value={summary.shadow} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Market Risk" value={summary.marketRisk} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Long / Short" value={summary.longShortRatio} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Avg Confidence" value={summary.avgConfidence} /></Col>
      </Row>

      <SectionCard
        title={viewMode === "shadow" ? "Shadow Candidate Snapshot" : "Live Snapshot"}
        extra={<Tag color={summary.dataHealth === "BLOCKED" ? "red" : summary.dataHealth === "WARN" ? "gold" : "green"}>{summary.dataHealth}</Tag>}
      >
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          {errorMsg ? <Alert type="error" showIcon message="Signal snapshot refresh failed" description={errorMsg} /> : null}
          {liveMeta.data_health?.blocking_status === "BLOCKED" ? (
            <Alert
              type="error"
              showIcon
              message="Data freshness gate is blocking live signals"
              description={liveMeta.data_health.message || liveMeta.message || "Refresh raw data in Data Maintenance before generating live signals."}
            />
          ) : liveMeta.data_health?.blocking_status === "WARN" ? (
            <Alert
              type="warning"
              showIcon
              message="Live signals carry a data freshness warning"
              description={liveMeta.data_health.message || "The snapshot was generated with a non-blocking data freshness warning."}
            />
          ) : null}
          {liveMeta.router_decision?.is_live_blocked || liveMeta.router_decision?.risk_scale === 0 ? (
            <Alert
              type="warning"
              showIcon
              message="Router decision: live execution is blocked"
              description={`regime_date=${liveMeta.regime_freshness?.regime_date || "-"} | signal_date=${liveMeta.regime_freshness?.signal_date || liveMeta.signal_date || "-"} | risk_scale=${liveMeta.router_decision?.risk_scale ?? "-"} | reason=${liveMeta.router_decision?.block_reason || liveMeta.regime_freshness?.block_reason || "router_blocked"}`}
            />
          ) : null}
          {viewMode === "shadow" ? (
            <Alert
              type="info"
              showIcon
              message="Shadow candidates are research-only evidence"
              description="These rows preserve real Stock Radar candidates and proposed trade parameters, but they are not executable and never enter live PnL."
            />
          ) : null}
          <Space wrap>
            <Tag color={summary.dataHealth === "BLOCKED" ? "red" : summary.dataHealth === "WARN" ? "gold" : "green"}>{summary.dataHealth}</Tag>
            <Tag color={viewMode === "shadow" ? "blue" : "green"}>{viewMode}</Tag>
            <Typography.Text>Generated: {liveMeta.generated_at || "-"}</Typography.Text>
            <Typography.Text>Signal date: {liveMeta.signal_date || "-"}</Typography.Text>
            <Typography.Text>Regime date: {liveMeta.regime_freshness?.regime_date || "-"}</Typography.Text>
            <Typography.Text>Lag: {liveMeta.regime_freshness?.freshness_lag_days ?? "-"} trading day(s)</Typography.Text>
            <Typography.Text>Universe: {liveMeta.data_source?.universe || "-"}</Typography.Text>
            <Typography.Text>Source: {liveMeta.data_source?.provider_uri || "-"}</Typography.Text>
          </Space>
        </Space>
      </SectionCard>

      <SectionCard title="Signal filters">
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6} xl={3}><Select placeholder="Market" allowClear style={{ width: "100%" }} value={filters.market} options={(enums.market || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("market", v)} /></Col>
          <Col xs={12} md={6} xl={3}><Select placeholder="Asset" allowClear style={{ width: "100%" }} value={filters.asset_type} options={(enums.asset_type || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("asset_type", v)} /></Col>
          <Col xs={24} md={8} xl={4}><Input placeholder="Instrument" value={filters.instrument} onChange={(e) => updateFilter("instrument", e.target.value)} /></Col>
          <Col xs={12} md={6} xl={3}><Select placeholder="Timeframe" allowClear style={{ width: "100%" }} value={filters.timeframe} options={(enums.timeframe || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("timeframe", v)} /></Col>
          <Col xs={12} md={6} xl={3}><Select placeholder="Side" allowClear style={{ width: "100%" }} value={filters.side} options={(enums.side || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("side", v)} /></Col>
          <Col xs={12} md={6} xl={3}><Select placeholder="Risk" allowClear style={{ width: "100%" }} value={filters.risk_level} options={(enums.risk_level || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("risk_level", v)} /></Col>
          <Col xs={12} md={6} xl={5}><Select placeholder="Regime" allowClear style={{ width: "100%" }} value={filters.regime_label} options={(enums.regime_label || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("regime_label", v)} /></Col>
          <Col xs={12} md={6} xl={4}><Select placeholder="Status" allowClear style={{ width: "100%" }} value={filters.status} options={(enums.status || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("status", v)} /></Col>
          <Col xs={24} md={10} xl={6}><Select placeholder="Template" allowClear style={{ width: "100%" }} value={filters.signal_template} options={(enums.signal_template || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("signal_template", v)} /></Col>
          <Col xs={24} md={10} xl={10}>
            <Typography.Text type="secondary">Confidence Min</Typography.Text>
            <Slider min={0} max={1} step={0.01} value={filters.confidence_min ?? 0} onChange={(v) => updateFilter("confidence_min", Number(v))} />
          </Col>
          <Col xs={24} md={4} xl={4}><Button type="primary" block onClick={applyFilters}>Apply Filters</Button></Col>
        </Row>
      </SectionCard>

      <Row gutter={[16, 16]}>
        <Col xxl={17} xl={16} lg={24}>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {signals.length === 0 ? (
              <SectionCard title="Signals">
                <EmptyState
                  title={liveMeta.status === "NO_SNAPSHOT" ? "No real signal snapshot yet" : "No active signals"}
                  description={
                    liveMeta.data_health?.blocking_status === "BLOCKED"
                      ? "Data is currently blocked by the freshness gate. Use Data Maintenance to refresh raw sources before generating live signals."
                      : viewMode === "shadow"
                        ? "No router-blocked Stock Radar candidates are available in the latest snapshot."
                      : "Run Refresh Snapshot after data maintenance completes."
                  }
                />
              </SectionCard>
            ) : (
              signals.map((signal) => (
                <SectionCard
                  key={signal.signal_id}
                  title={
                    <Space>
                      <Typography.Text strong>{signal.instrument}</Typography.Text>
                      <Typography.Text type="secondary">{signal.market} / {signal.asset_type} / {signal.timeframe}</Typography.Text>
                    </Space>
                  }
                  extra={<StatusBadge value={signal.status} />}
                >
                  <Space direction="vertical" style={{ width: "100%" }} size={10}>
                    <Space style={{ width: "100%", justifyContent: "space-between" }}>
                      <Space>
                        <SideBadge value={signal.side} />
                        <RiskBadge value={signal.risk_level} />
                        <RegimeBadge value={signal.regime_label} />
                        {signal.execution_mode === "shadow" ? <Tag color="blue">Not executable</Tag> : null}
                      </Space>
                      <Space>
                        <Button
                          size="small"
                          onClick={() => router.push(`/signal-center/${signal.signal_id}${signal.execution_mode === "shadow" ? "?execution_mode=shadow" : ""}`)}
                        >
                          View Detail
                        </Button>
                      </Space>
                    </Space>
                    <Row gutter={[12, 8]}>
                      <Col span={6}><Typography.Text type="secondary">Trigger Time</Typography.Text><div>{signal.signal_time}</div></Col>
                      <Col span={4}><Typography.Text type="secondary">Entry</Typography.Text><div>{signal.entry_price}</div></Col>
                      <Col span={4}><Typography.Text type="secondary">SL / TP</Typography.Text><div>{signal.stop_loss} / {signal.take_profit}</div></Col>
                      <Col span={4}><Typography.Text type="secondary">Position Scale</Typography.Text><div>{Math.round(signal.position_scale * 100)}%</div></Col>
                      <Col span={6}><ConfidenceBar value={signal.confidence} /></Col>
                    </Row>
                    <Row gutter={[12, 8]}>
                      <Col span={6}><Typography.Text type="secondary">Score</Typography.Text><div>{typeof signal.score === "number" ? signal.score.toFixed(4) : "-"}</div></Col>
                      <Col span={6}><Typography.Text type="secondary">Percentile</Typography.Text><div>{signal.score_percentile != null ? `${Math.round(signal.score_percentile * 100)}%` : "-"}</div></Col>
                      <Col span={6}><Typography.Text type="secondary">Trade From</Typography.Text><div>{signal.effective_trade_date || "-"}</div></Col>
                      <Col span={6}><Typography.Text type="secondary">Router</Typography.Text><div>{signal.router_block_reason || signal.router_threshold_profile || "OK"}</div></Col>
                    </Row>
                    <ReasonTagList tags={signal.reason_tags} max={4} />
                  </Space>
                </SectionCard>
              ))
            )}
          </Space>
        </Col>

        <Col xxl={7} xl={8} lg={24}>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <SectionCard title="Regime Snapshot">
              {regime ? (
                <Space direction="vertical" size={4}>
                  <div>Regime: <RegimeBadge value={regime.regime_label} /></div>
                  <div>Volatility: {regime.volatility_state}</div>
                  <div>Tail Risk: {regime.tail_risk_state}</div>
                  <div>CPD Score: {regime.cpd_score}</div>
                  <div>Severity: {regime.severity_score}</div>
                  <div>Last Changed: {regime.snapshot_time}</div>
                  <div>Data Source: {regime.data_source || "unknown"}</div>
                </Space>
              ) : null}
            </SectionCard>
            <SectionCard title="Recent Notifications">
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {notifications.map((n) => (
                  <div key={`${n.time}-${n.title}`}>
                    <Typography.Text>{n.title}</Typography.Text>
                    <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{n.channel} • {n.time}</Typography.Text></div>
                  </div>
                ))}
              </Space>
            </SectionCard>
            <SectionCard title="Shock Alerts">
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {shocks.map((s) => (
                  <div key={s.event_id}>
                    <Typography.Text>{s.event_type}</Typography.Text>
                    <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{s.event_date} • severity {s.severity}</Typography.Text></div>
                  </div>
                ))}
              </Space>
            </SectionCard>
          </Space>
        </Col>
      </Row>
    </PageContainer>
  );
}

