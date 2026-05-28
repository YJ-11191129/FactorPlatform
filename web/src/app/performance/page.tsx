"use client";

import dynamic from "next/dynamic";
import { Alert, Col, Row, Segmented, Select, Skeleton, Space, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { MetricCard } from "@/components/common/MetricCard";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { getPerformanceAttribution, getPerformanceSummary, getPerformanceTimeseries } from "@/lib/api/signal-center";
import type { ExecutionMode, PerformanceSummary, TimeSeriesPoint } from "@/types/signal-center";

const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });
const Column = dynamic(() => import("@ant-design/charts").then((m) => m.Column), { ssr: false });

type Attribution = {
  data_source?: string;
  source_run_id?: string | null;
  computed_at?: string | null;
  by_regime: Array<{ label: string; contribution: number }>;
  by_template: Array<{ label: string; contribution: number }>;
  by_shock_window: Array<{ label: string; contribution: number }>;
  by_risk_level: Array<{ label: string; contribution: number }>;
};

export default function PerformancePage() {
  const [advancedMode] = useAdvancedMode();
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");
  const [summary, setSummary] = useState<PerformanceSummary | null>(null);
  const [timeseries, setTimeseries] = useState<TimeSeriesPoint[]>([]);
  const [attribution, setAttribution] = useState<Attribution | null>(null);
  const [metric, setMetric] = useState("cum_pnl");
  const [executionMode, setExecutionMode] = useState<Extract<ExecutionMode, "live" | "shadow">>("live");

  const load = useCallback(async (nextMetric: string, nextMode: Extract<ExecutionMode, "live" | "shadow">) => {
    setState("loading");
    try {
      const [s, t, a] = await Promise.all([
        getPerformanceSummary(nextMode),
        getPerformanceTimeseries(nextMetric, "day", nextMode),
        getPerformanceAttribution(nextMode),
      ]);
      setSummary(s);
      setTimeseries(t.items);
      setAttribution(a);
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    load(metric, executionMode);
  }, [load, metric, executionMode]);

  if (state === "loading") return <Skeleton active paragraph={{ rows: 10 }} />;
  if (state === "error" || !summary || !attribution) return <ErrorState title="Performance page load failed" onRetry={() => load(metric, executionMode)} />;
  const evaluatedSignals = summary.summary.evaluated_signals ?? summary.evaluated_signals ?? 0;
  const pendingSignals = summary.summary.pending_signals ?? summary.pending_signals ?? 0;
  const noTradeSignals = summary.summary.no_trade_signals ?? summary.no_trade_signals ?? 0;

  return (
    <PageContainer
      title="Performance"
      subtitle="KPI overview, time-series curves, and attribution breakdowns"
      extra={
        <Space>
          <Segmented
            value={executionMode}
            onChange={(v) => setExecutionMode(v as Extract<ExecutionMode, "live" | "shadow">)}
            options={[
              { label: "Live", value: "live" },
              { label: "Shadow", value: "shadow" },
            ]}
          />
          <Select
            value={metric}
            style={{ width: 200 }}
            onChange={(v) => {
              setMetric(v);
            }}
            options={[
              { label: "Cumulative PnL", value: "cum_pnl" },
              { label: "Win Rate", value: "win_rate" },
              { label: "Drawdown", value: "drawdown" },
              { label: "Profit Factor", value: "profit_factor" },
            ]}
          />
        </Space>
      }
    >
      <SectionCard
        title="Outcome source"
        extra={<Tag color={executionMode === "shadow" ? "blue" : evaluatedSignals > 0 ? "green" : "gold"}>{summary.execution_mode || executionMode}</Tag>}
      >
        <Alert
          type={executionMode === "shadow" ? "info" : evaluatedSignals > 0 ? "success" : "warning"}
          showIcon
          message={`Performance source: ${summary.data_source || "signal_outcomes"}`}
          description={
            advancedMode
              ? `computed_at=${summary.computed_at || "-"} | source_run_id=${summary.source_run_id || "-"} | evaluated=${evaluatedSignals} | pending=${pendingSignals} | no_trade=${noTradeSignals}${executionMode === "shadow" ? " | research-only, not live PnL" : ""}`
              : `computed_at=${summary.computed_at || "-"} | evaluated=${evaluatedSignals} | pending=${pendingSignals} | no_trade=${noTradeSignals}${executionMode === "shadow" ? " | research-only, not live PnL" : ""}`
          }
        />
      </SectionCard>

      <Row gutter={[12, 12]}>
        <Col xs={12} md={8} xl={4}><MetricCard title="Total Signals" value={summary.summary.total_signals} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Evaluated" value={evaluatedSignals} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Win Rate" value={Math.round(summary.summary.win_rate * 100)} suffix="%" /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Avg PnL" value={summary.summary.avg_pnl.toFixed(4)} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Profit Factor" value={summary.summary.profit_factor.toFixed(2)} /></Col>
        <Col xs={12} md={8} xl={4}><MetricCard title="Max Drawdown" value={summary.summary.max_drawdown.toFixed(4)} /></Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xl={24} xs={24}>
          <SectionCard title="Time Series">
            {timeseries.length > 0 ? (
              <Line data={timeseries} xField="date" yField="value" height={280} />
            ) : (
              <EmptyState
                title="No evaluated outcomes"
                description={executionMode === "shadow" ? "Refresh shadow outcomes after daily bars cover the paper candidate window." : "Refresh signal outcomes after daily bars cover at least one live signal."}
              />
            )}
          </SectionCard>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xl={12} xs={24}>
          <SectionCard title="Attribution by Regime">
            {attribution.by_regime.length > 0 ? (
              <Column data={attribution.by_regime} xField="label" yField="contribution" height={250} />
            ) : (
              <EmptyState title="No regime attribution" />
            )}
          </SectionCard>
        </Col>
        <Col xl={12} xs={24}>
          <SectionCard title="Attribution by Template">
            {attribution.by_template.length > 0 ? (
              <Column data={attribution.by_template} xField="label" yField="contribution" height={250} />
            ) : (
              <EmptyState title="No template attribution" />
            )}
          </SectionCard>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xl={12} xs={24}>
          <SectionCard title="Attribution by Shock Window">
            {attribution.by_shock_window.length > 0 ? (
              <Column data={attribution.by_shock_window} xField="label" yField="contribution" height={250} />
            ) : (
              <EmptyState title="No shock-window attribution" />
            )}
          </SectionCard>
        </Col>
        <Col xl={12} xs={24}>
          <SectionCard title="Attribution by Risk Level">
            {attribution.by_risk_level.length > 0 ? (
              <Column data={attribution.by_risk_level} xField="label" yField="contribution" height={250} />
            ) : (
              <EmptyState title="No risk-level attribution" />
            )}
          </SectionCard>
        </Col>
      </Row>
    </PageContainer>
  );
}
