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
import { RiskMeter, SignalGauge } from "@/components/visual/ResearchVisuals";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { getEnumsMeta, getNotificationLogs, getRegimeCurrent, getShockEvents, listLiveSignals, listShadowSignals, refreshLiveSignals } from "@/lib/api/signal-center";
import type { ApiError } from "@/lib/api/client";
import { useLanguage } from "@/lib/i18n";
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

const statusColors: Record<string, string> = {
  ACTIVE: "green",
  BLOCKED: "gold",
  FILTERED: "cyan",
  MONITORED: "processing",
  NOTIFIED: "blue",
  CLOSED: "default",
  INVALIDATED: "magenta",
};

const reasonLabels: Record<string, string> = {
  stock_radar_candidate: "候选池命中",
  regime_post_shock_rebound: "冲击后修复",
  router_liquidity_shock_observe_only_profile: "流动性冲击观察",
  router_blocked_template: "风险过滤",
  shock_window_active: "冲击窗口",
  liquidity_too_tight: "流动性偏紧",
  post_shock_rebound: "冲击后修复",
};

function dataHealthLabel(value: string, advancedMode: boolean) {
  if (advancedMode) return value;
  if (value === "OK") return "正常";
  if (value === "WARN") return "需关注";
  if (value === "BLOCKED") return "已暂停";
  return "待确认";
}

function formatBlockReason(value?: string | null) {
  if (!value) return "风险过滤";
  if (value === "EXTREME_RISK_BLOCKED") return "高风险过滤";
  if (value.includes("LIQUIDITY")) return "流动性风险过滤";
  if (value.includes("VOLATILITY")) return "波动风险过滤";
  return value.toLowerCase().includes("blocked") ? "风险过滤" : value.replace(/_/g, " ");
}

function friendlyReasonTags(tags: string[] | undefined) {
  return (tags || [])
    .map((tag) => reasonLabels[tag] || (tag.startsWith("router_") ? "" : tag.replace(/_/g, " ")))
    .filter(Boolean);
}

function friendlyMarketText(signal: Signal) {
  const market = signal.market === "CN" ? "A股" : signal.market;
  const asset = signal.asset_type === "STOCK" ? "股票" : signal.asset_type;
  const timeframe = signal.timeframe === "1D" ? "日线" : signal.timeframe;
  return `${market} / ${asset} / ${timeframe}`;
}

function friendlyStatusTag(value: string) {
  const label = value === "ACTIVE" ? "观察中" : value === "BLOCKED" ? "已过滤" : value === "FILTERED" ? "已筛选" : value;
  return <Tag color={statusColors[value] || "default"}>{label}</Tag>;
}

function researchActionFromSignals(signals: Signal[], blocked: number) {
  const longs = signals.filter((s) => s.side === "LONG").length;
  const shorts = signals.filter((s) => s.side === "SHORT").length;
  if (blocked >= Math.max(3, signals.length * 0.5)) return { label: "观望", tone: "warning" as const, description: "风险过滤较多，优先观察和回测验证。" };
  if (longs > shorts) return { label: "偏多观察", tone: "positive" as const, description: "候选信号偏多，需结合止损纪律和仓位上限。" };
  if (shorts > longs) return { label: "偏空观察", tone: "negative" as const, description: "候选信号偏空，关注尾部风险和反向冲击。" };
  return { label: "中性观察", tone: "neutral" as const, description: "多空结构均衡，等待更明确触发条件。" };
}

function friendlySideTag(value: string) {
  if (value === "LONG") return <Tag color="green">偏多</Tag>;
  if (value === "SHORT") return <Tag color="red">偏空</Tag>;
  return <Tag>中性</Tag>;
}

function friendlyRiskTag(value: string) {
  if (value === "LOW") return <Tag color="blue">低风险</Tag>;
  if (value === "MEDIUM") return <Tag color="gold">中风险</Tag>;
  if (value === "HIGH") return <Tag color="orange">高风险</Tag>;
  if (value === "BLOCKED") return <Tag color="default">风险过滤</Tag>;
  return <Tag>{value}</Tag>;
}

export default function SignalCenterPage() {
  const router = useRouter();
  const { language } = useLanguage();
  const [advancedMode] = useAdvancedMode();
  const zh = language === "zh";
  const t = useCallback((cn: string, en: string) => (zh ? cn : en), [zh]);
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
  const researchAction = useMemo(() => researchActionFromSignals(signals, summary.blocked), [signals, summary.blocked]);

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
      setErrorMsg(advancedMode ? (err?.message || "Signal refresh failed") : t("信号刷新暂不可用，可稍后重试。", "Signal refresh is temporarily unavailable; please retry later."));
    } finally {
      setRefreshing(false);
    }
  }

  if (state === "loading") {
    return <Skeleton active paragraph={{ rows: 12 }} />;
  }

  if (state === "error") {
    return <ErrorState title={advancedMode ? "Signal Center load failed" : t("信号中心加载失败", "Signal Center load failed")} subtitle={advancedMode ? (errorMsg || "Check API key in Settings") : t("数据服务暂不可用，可稍后刷新。", "The data service is temporarily unavailable; please refresh later.")} onRetry={() => load(filters, viewMode)} />;
  }

  return (
    <PageContainer
      title={advancedMode ? "Research Terminal" : t("信号中心", "Signal Center")}
      subtitle={advancedMode ? "Regime-aware signal screening, Router decisions, shadow validation, and outcome evidence in one controlled workspace" : t("聚合候选信号、风险过滤与市场状态，用于辅助研究与观察。", "Aggregates candidate signals, risk filters, and market state for research support.")}
      extra={
        <Space>
          <Button onClick={resetFilters}>{t("重置", "Reset")}</Button>
          <Segmented
            value={viewMode}
            onChange={(v) => changeViewMode(v as ViewMode)}
            options={[
              { label: advancedMode ? "Live" : t("当前信号", "Current"), value: "live" },
              { label: advancedMode ? "Shadow Candidates" : t("观察候选", "Watchlist"), value: "shadow" },
            ]}
          />
          <Button type="primary" loading={refreshing} onClick={refreshSnapshot}>{advancedMode ? "Refresh Snapshot" : t("刷新信号", "Refresh Signals")}</Button>
        </Space>
      }
    >
      <Row gutter={[12, 12]}>
        <Col xs={12} md={8} xl={4}><MetricCard title={advancedMode ? "Live Active" : t("可观察信号", "Observable")} value={summary.active} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title={advancedMode ? "Router Blocked" : t("风险过滤", "Risk filtered")} value={summary.blocked} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title={advancedMode ? "Shadow Queue" : t("观察候选", "Watchlist")} value={summary.shadow} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title={advancedMode ? "Market Risk" : t("市场风险", "Market risk")} value={summary.marketRisk} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title={advancedMode ? "Long / Short" : t("多空结构", "Long / Short")} value={summary.longShortRatio} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title={advancedMode ? "Avg Confidence" : t("平均置信度", "Avg confidence")} value={summary.avgConfidence} /></Col>
      </Row>

      {!advancedMode ? (
        <div style={{ marginTop: 12, marginBottom: 12 }}>
          <SectionCard title={t("研究建议仪表盘", "Research Recommendation Dashboard")}>
            <Row gutter={[12, 12]} align="stretch">
              <Col xs={24} md={7}>
                <SignalGauge
                  label={researchAction.label}
                  value={Number(summary.avgConfidence.replace("%", "")) || 0}
                  tone={researchAction.tone}
                  caption={researchAction.description}
                />
              </Col>
              <Col xs={24} md={17}>
                <Row gutter={[12, 12]}>
                  <Col xs={24} lg={8}>
                    <RiskMeter label={t("风险过滤", "Risk Filter")} value={Math.min(100, summary.blocked * 8)} status={summary.blocked ? t("已触发", "Active") : t("正常", "Normal")} tone={summary.blocked ? "warning" : "positive"} />
                  </Col>
                  <Col xs={24} lg={8}>
                    <RiskMeter label={t("仓位纪律", "Position Discipline")} value={signals.length ? Math.round(Math.max(...signals.map((s) => s.position_scale || 0)) * 100) : 0} status={signals.length ? t("已配置", "Configured") : t("待生成", "Pending")} tone="positive" />
                  </Col>
                  <Col xs={24} lg={8}>
                    <RiskMeter label={t("止损纪律", "Stop-loss Discipline")} value={signals.some((s) => Number(s.stop_loss) > 0) ? 84 : 28} status={signals.some((s) => Number(s.stop_loss) > 0) ? t("已配置", "Configured") : t("待补充", "Pending")} tone={signals.some((s) => Number(s.stop_loss) > 0) ? "positive" : "warning"} />
                  </Col>
                </Row>
                <Alert
                  type="info"
                  showIcon
                  style={{ marginTop: 12 }}
                  message={t("仅作研究观察", "Research observation only")}
                  description={t("本页展示概率化信号、风险状态和观察纪律，不提供直接交易指令。", "This page shows probabilistic signals, risk state, and observation discipline, not direct trading instructions.")}
                />
              </Col>
            </Row>
          </SectionCard>
        </div>
      ) : null}

      <SectionCard
        title={advancedMode ? (viewMode === "shadow" ? "Shadow Candidate Snapshot" : "Live Snapshot") : (viewMode === "shadow" ? t("观察候选快照", "Watchlist Snapshot") : t("信号快照", "Signal Snapshot"))}
        extra={<Tag color={summary.dataHealth === "BLOCKED" ? "red" : summary.dataHealth === "WARN" ? "gold" : "green"}>{dataHealthLabel(summary.dataHealth, advancedMode)}</Tag>}
      >
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          {errorMsg ? <Alert type="error" showIcon message={advancedMode ? "Signal snapshot refresh failed" : t("信号刷新暂不可用", "Signal refresh unavailable")} description={errorMsg} /> : null}
          {liveMeta.data_health?.blocking_status === "BLOCKED" ? (
            <Alert
              type="error"
              showIcon
              message={advancedMode ? "Data freshness gate is blocking live signals" : t("数据状态不足，已暂停信号观察", "Data state is insufficient; signal observation is paused")}
              description={advancedMode ? (liveMeta.data_health.message || liveMeta.message || "Refresh raw data in Data Maintenance before generating live signals.") : t("请稍后刷新，或等待数据源更新后再查看。", "Please refresh later or wait for the data source to update.")}
            />
          ) : liveMeta.data_health?.blocking_status === "WARN" ? (
            <Alert
              type="warning"
              showIcon
              message={advancedMode ? "Live signals carry a data freshness warning" : t("数据状态需关注", "Data state needs attention")}
              description={advancedMode ? (liveMeta.data_health.message || "The snapshot was generated with a non-blocking data freshness warning.") : t("当前信号仍可用于研究观察，但应结合数据更新时间谨慎解读。", "Signals remain available for research, but should be interpreted with the update time in mind.")}
            />
          ) : null}
          {liveMeta.router_decision?.is_live_blocked || liveMeta.router_decision?.risk_scale === 0 ? (
            <Alert
              type="warning"
              showIcon
              message={advancedMode ? "Router decision: live execution is blocked" : t("当前仅建议观察", "Observation only")}
              description={advancedMode ? `regime_date=${liveMeta.regime_freshness?.regime_date || "-"} | signal_date=${liveMeta.regime_freshness?.signal_date || liveMeta.signal_date || "-"} | risk_scale=${liveMeta.router_decision?.risk_scale ?? "-"} | reason=${liveMeta.router_decision?.block_reason || liveMeta.regime_freshness?.block_reason || "router_blocked"}` : t(`风险过滤已触发，排序日期 ${liveMeta.regime_freshness?.signal_date || liveMeta.signal_date || "-"}，暂不进入执行链路。`, `Risk filtering is active for ranking date ${liveMeta.regime_freshness?.signal_date || liveMeta.signal_date || "-"}; execution is paused.`)}
            />
          ) : null}
          {viewMode === "shadow" ? (
            <Alert
              type="info"
              showIcon
              message={advancedMode ? "Shadow candidates are research-only evidence" : t("观察候选仅用于研究验证", "Watchlist candidates are research-only")}
              description={advancedMode ? "These rows preserve real Stock Radar candidates and proposed trade parameters, but they are not executable and never enter live PnL." : t("这些候选保留了筛选依据和参数建议，用于后续研究与回测，不构成交易建议。", "These candidates preserve screening evidence and proposed parameters for research and backtesting; not financial advice.")}
            />
          ) : null}
          <Space wrap>
            <Tag color={summary.dataHealth === "BLOCKED" ? "red" : summary.dataHealth === "WARN" ? "gold" : "green"}>{dataHealthLabel(summary.dataHealth, advancedMode)}</Tag>
            <Tag color={viewMode === "shadow" ? "blue" : "green"}>{advancedMode ? viewMode : viewMode === "shadow" ? t("观察候选", "Watchlist") : t("当前信号", "Current")}</Tag>
            <Typography.Text>{advancedMode ? "Generated" : t("生成时间", "Generated")}: {liveMeta.generated_at || "-"}</Typography.Text>
            <Typography.Text>{advancedMode ? "Signal date" : t("排序日期", "Ranking date")}: {liveMeta.signal_date || "-"}</Typography.Text>
            <Typography.Text>{advancedMode ? "Regime date" : t("状态日期", "Regime date")}: {liveMeta.regime_freshness?.regime_date || "-"}</Typography.Text>
            <Typography.Text>{advancedMode ? "Lag" : t("延迟", "Lag")}: {liveMeta.regime_freshness?.freshness_lag_days ?? "-"} {advancedMode ? "trading day(s)" : t("个交易日", "trading day(s)")}</Typography.Text>
            <Typography.Text>{advancedMode ? "Universe" : t("范围", "Universe")}: {liveMeta.data_source?.universe || "-"}</Typography.Text>
            {advancedMode ? <Typography.Text>Source: {liveMeta.data_source?.provider_uri || "-"}</Typography.Text> : null}
          </Space>
        </Space>
      </SectionCard>

      <SectionCard title={advancedMode ? "Signal filters" : t("筛选条件", "Signal filters")}>
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6} xl={3}><Select placeholder={t("市场", "Market")} allowClear style={{ width: "100%" }} value={filters.market} options={(enums.market || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("market", v)} /></Col>
          <Col xs={12} md={6} xl={3}><Select placeholder={t("资产", "Asset")} allowClear style={{ width: "100%" }} value={filters.asset_type} options={(enums.asset_type || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("asset_type", v)} /></Col>
          <Col xs={24} md={8} xl={4}><Input placeholder={t("标的", "Instrument")} value={filters.instrument} onChange={(e) => updateFilter("instrument", e.target.value)} /></Col>
          <Col xs={12} md={6} xl={3}><Select placeholder={t("周期", "Timeframe")} allowClear style={{ width: "100%" }} value={filters.timeframe} options={(enums.timeframe || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("timeframe", v)} /></Col>
          <Col xs={12} md={6} xl={3}><Select placeholder={t("方向", "Side")} allowClear style={{ width: "100%" }} value={filters.side} options={(enums.side || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("side", v)} /></Col>
          <Col xs={12} md={6} xl={3}><Select placeholder={t("风险", "Risk")} allowClear style={{ width: "100%" }} value={filters.risk_level} options={(enums.risk_level || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("risk_level", v)} /></Col>
          <Col xs={12} md={6} xl={5}><Select placeholder={t("市场状态", "Regime")} allowClear style={{ width: "100%" }} value={filters.regime_label} options={(enums.regime_label || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("regime_label", v)} /></Col>
          <Col xs={12} md={6} xl={4}><Select placeholder={t("状态", "Status")} allowClear style={{ width: "100%" }} value={filters.status} options={(enums.status || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("status", v)} /></Col>
          <Col xs={24} md={10} xl={6}><Select placeholder={advancedMode ? "Template" : t("策略模板", "Template")} allowClear style={{ width: "100%" }} value={filters.signal_template} options={(enums.signal_template || []).map((v) => ({ label: v, value: v }))} onChange={(v) => updateFilter("signal_template", v)} /></Col>
          <Col xs={24} md={10} xl={10}>
            <Typography.Text type="secondary">{advancedMode ? "Confidence Min" : t("最低置信度", "Confidence Min")}</Typography.Text>
            <Slider min={0} max={1} step={0.01} value={filters.confidence_min ?? 0} onChange={(v) => updateFilter("confidence_min", Number(v))} />
          </Col>
          <Col xs={24} md={4} xl={4}><Button type="primary" block onClick={applyFilters}>{t("应用筛选", "Apply Filters")}</Button></Col>
        </Row>
      </SectionCard>

      <Row gutter={[16, 16]}>
        <Col xxl={17} xl={16} lg={24}>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {signals.length === 0 ? (
              <SectionCard title={advancedMode ? "Signals" : t("信号列表", "Signals")}>
                <EmptyState
                  title={advancedMode ? (liveMeta.status === "NO_SNAPSHOT" ? "No real signal snapshot yet" : "No active signals") : (liveMeta.status === "NO_SNAPSHOT" ? t("暂无信号快照", "No signal snapshot yet") : t("暂无可观察信号", "No observable signals"))}
                  description={
                    advancedMode ? (liveMeta.data_health?.blocking_status === "BLOCKED"
                      ? "Data is currently blocked by the freshness gate. Use Data Maintenance to refresh raw sources before generating live signals."
                      : viewMode === "shadow"
                        ? "No router-blocked Stock Radar candidates are available in the latest snapshot."
                        : "Run Refresh Snapshot after data maintenance completes.") : (liveMeta.data_health?.blocking_status === "BLOCKED"
                          ? t("数据状态不足，暂不展示信号。", "Data state is insufficient; signals are paused.")
                          : viewMode === "shadow"
                            ? t("当前没有进入观察队列的候选。", "No watchlist candidates are available.")
                            : t("刷新后可查看最新候选信号。", "Refresh to view the latest candidate signals."))
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
                      <Typography.Text type="secondary">{advancedMode ? `${signal.market} / ${signal.asset_type} / ${signal.timeframe}` : friendlyMarketText(signal)}</Typography.Text>
                    </Space>
                  }
                  extra={advancedMode ? <StatusBadge value={signal.status} /> : friendlyStatusTag(signal.status)}
                >
                  <Space direction="vertical" style={{ width: "100%" }} size={10}>
                    <Space style={{ width: "100%", justifyContent: "space-between" }}>
                      <Space>
                        {advancedMode ? <SideBadge value={signal.side} /> : friendlySideTag(signal.side)}
                        {advancedMode ? <RiskBadge value={signal.risk_level} /> : friendlyRiskTag(signal.risk_level)}
                        <RegimeBadge value={signal.regime_label} />
                        {signal.execution_mode === "shadow" ? <Tag color="blue">{advancedMode ? "Not executable" : t("仅观察", "Observation only")}</Tag> : null}
                      </Space>
                      <Space>
                        <Button
                          size="small"
                          onClick={() => router.push(`/signal-center/${signal.signal_id}${signal.execution_mode === "shadow" ? "?execution_mode=shadow" : ""}`)}
                        >
                          {t("查看详情", "View Detail")}
                        </Button>
                      </Space>
                    </Space>
                    <Row gutter={[12, 8]}>
                      <Col span={6}><Typography.Text type="secondary">{advancedMode ? "Trigger Time" : t("触发时间", "Trigger Time")}</Typography.Text><div>{signal.signal_time}</div></Col>
                      <Col span={4}><Typography.Text type="secondary">{advancedMode ? "Entry" : t("入场参考", "Entry")}</Typography.Text><div>{signal.entry_price}</div></Col>
                      <Col span={4}><Typography.Text type="secondary">{advancedMode ? "SL / TP" : t("止损 / 止盈", "SL / TP")}</Typography.Text><div>{signal.stop_loss} / {signal.take_profit}</div></Col>
                      <Col span={4}><Typography.Text type="secondary">{advancedMode ? "Position Scale" : t("仓位比例", "Position Scale")}</Typography.Text><div>{Math.round(signal.position_scale * 100)}%</div></Col>
                      <Col span={6}><ConfidenceBar value={signal.confidence} /></Col>
                    </Row>
                    <Row gutter={[12, 8]}>
                      <Col span={6}><Typography.Text type="secondary">{advancedMode ? "Score" : t("综合分", "Score")}</Typography.Text><div>{typeof signal.score === "number" ? signal.score.toFixed(4) : "-"}</div></Col>
                      <Col span={6}><Typography.Text type="secondary">{advancedMode ? "Percentile" : t("分位", "Percentile")}</Typography.Text><div>{signal.score_percentile != null ? `${Math.round(signal.score_percentile * 100)}%` : "-"}</div></Col>
                      <Col span={6}><Typography.Text type="secondary">{advancedMode ? "Trade From" : t("可观察日", "Observable From")}</Typography.Text><div>{signal.effective_trade_date || "-"}</div></Col>
                      <Col span={6}><Typography.Text type="secondary">{advancedMode ? "Router" : t("风险状态", "Risk state")}</Typography.Text><div>{advancedMode ? (signal.router_block_reason || signal.router_threshold_profile || "OK") : formatBlockReason(signal.router_block_reason || signal.router_threshold_profile)}</div></Col>
                    </Row>
                    <ReasonTagList tags={advancedMode ? signal.reason_tags : friendlyReasonTags(signal.reason_tags)} max={advancedMode ? 4 : 3} />
                  </Space>
                </SectionCard>
              ))
            )}
          </Space>
        </Col>

        <Col xxl={7} xl={8} lg={24}>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <SectionCard title={advancedMode ? "Regime Snapshot" : t("市场状态", "Regime Snapshot")}>
              {regime ? (
                <Space direction="vertical" size={4}>
                  <div>{advancedMode ? "Regime" : t("状态", "Regime")}: <RegimeBadge value={regime.regime_label} /></div>
                  <div>{advancedMode ? "Volatility" : t("波动状态", "Volatility")}: {regime.volatility_state}</div>
                  <div>{advancedMode ? "Tail Risk" : t("尾部风险", "Tail Risk")}: {regime.tail_risk_state}</div>
                  {advancedMode ? <div>CPD Score: {regime.cpd_score}</div> : null}
                  <div>{advancedMode ? "Severity" : t("严重度", "Severity")}: {regime.severity_score}</div>
                  <div>{advancedMode ? "Last Changed" : t("更新时间", "Last Changed")}: {regime.snapshot_time}</div>
                  {advancedMode ? <div>Data Source: {regime.data_source || "unknown"}</div> : null}
                </Space>
              ) : null}
            </SectionCard>
            <SectionCard title={advancedMode ? "Recent Notifications" : t("最近通知", "Recent Notifications")}>
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {notifications.map((n) => (
                  <div key={`${n.time}-${n.title}`}>
                    <Typography.Text>{n.title}</Typography.Text>
                    <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{advancedMode ? `${n.channel} • ${n.time}` : n.time}</Typography.Text></div>
                  </div>
                ))}
              </Space>
            </SectionCard>
            <SectionCard title={advancedMode ? "Shock Alerts" : t("冲击事件", "Shock Alerts")}>
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {shocks.map((s) => (
                  <div key={s.event_id}>
                    <Typography.Text>{s.event_type}</Typography.Text>
                    <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{s.event_date} • {advancedMode ? "severity" : t("强度", "severity")} {s.severity}</Typography.Text></div>
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
