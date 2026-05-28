"use client";

import dynamic from "next/dynamic";
import { Button, Card, Col, Descriptions, Row, Skeleton, Space, Table, Tabs, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { PageContainer } from "@/components/layout/PageContainer";
import { ConfidenceBar } from "@/components/signal/ConfidenceBar";
import { ReasonTagList } from "@/components/signal/ReasonTagList";
import { RegimeBadge, RiskBadge, SideBadge, StatusBadge } from "@/components/signal/SignalBadge";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { getResearchOpsLineage } from "@/lib/api/research-ops";
import { getSignalDetail } from "@/lib/api/signal-center";
import { useLanguage } from "@/lib/i18n";
import type { ResearchOpsLineage, ResearchOpsObject } from "@/types/research-ops";
import type { SignalDetail } from "@/types/signal-center";

const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });

type LoadState = "loading" | "error" | "ready";

const reasonLabels: Record<string, string> = {
  stock_radar_candidate: "候选池命中",
  regime_post_shock_rebound: "冲击后修复",
  router_liquidity_shock_observe_only_profile: "流动性冲击观察",
  router_blocked_template: "风险过滤",
};

function friendlyReasonTags(tags: string[] | undefined) {
  return (tags || []).map((tag) => reasonLabels[tag] || (tag.startsWith("router_") ? "" : tag.replace(/_/g, " "))).filter(Boolean);
}

function formatBlockReason(value?: string | null) {
  if (!value) return "风险过滤";
  if (value === "EXTREME_RISK_BLOCKED") return "高风险过滤";
  if (value.includes("LIQUIDITY")) return "流动性风险过滤";
  return value.toLowerCase().includes("blocked") ? "风险过滤" : value.replace(/_/g, " ");
}

export default function SignalDetailPage() {
  const params = useParams<{ signalId: string }>();
  const searchParams = useSearchParams();
  const { language } = useLanguage();
  const [advancedMode] = useAdvancedMode();
  const zh = language === "zh";
  const t = useCallback((cn: string, en: string) => (zh ? cn : en), [zh]);
  const signalId = params.signalId;
  const executionMode = searchParams.get("execution_mode") === "shadow" ? "shadow" : "live";

  const [state, setState] = useState<LoadState>("loading");
  const [detail, setDetail] = useState<SignalDetail | null>(null);
  const [lineage, setLineage] = useState<ResearchOpsLineage | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const [detailRes, lineageRes] = await Promise.allSettled([
        getSignalDetail(signalId, executionMode),
        advancedMode ? getResearchOpsLineage(signalId) : Promise.resolve(null),
      ]);
      if (detailRes.status === "rejected") throw detailRes.reason;
      setDetail(detailRes.value);
      setLineage(lineageRes.status === "fulfilled" ? lineageRes.value : null);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [advancedMode, signalId, executionMode]);

  useEffect(() => {
    load();
  }, [load]);

  const chartData = useMemo(() => {
    if (!detail) return [];
    return (detail.outcome?.price_path || [])
      .filter((point) => typeof point.close === "number")
      .flatMap((point) => [
        { t: point.date, series: "close", value: point.close },
        { t: point.date, series: "entry", value: detail.outcome?.entry_price ?? detail.signal.entry_price },
      ]);
  }, [detail]);

  if (state === "loading") return <Skeleton active paragraph={{ rows: 12 }} />;
  if (state === "error" || !detail) return <ErrorState title={advancedMode ? "Signal detail load failed" : t("信号详情加载失败", "Signal detail load failed")} onRetry={load} />;

  const s = detail.signal;
  const provenanceNodes = (lineage?.nodes || []).filter((node) => node.object_type !== "external_reference");

  return (
    <PageContainer
      title={advancedMode ? `Signal Detail - ${s.instrument}` : `${s.instrument} 信号详情`}
      subtitle={advancedMode ? "Explainability, risk controls, and similar signal review" : t("查看信号依据、风险控制与后续观察结果。", "Review signal rationale, risk controls, and follow-up observations.")}
      breadcrumb={[advancedMode ? "Signal Center" : t("信号中心", "Signal Center"), advancedMode ? s.signal_id : s.instrument]}
      extra={
        <Space>
          <Button onClick={() => navigator.clipboard.writeText(location.href).then(() => message.success(t("链接已复制", "Link copied")))}>{t("复制链接", "Copy Link")}</Button>
        </Space>
      }
    >
      <Card>
        <Space size={8} wrap>
          <Typography.Title level={4} style={{ margin: 0 }}>{s.instrument}</Typography.Title>
          <SideBadge value={s.side} />
          <StatusBadge value={s.status} />
          <RegimeBadge value={s.regime_label} />
          <RiskBadge value={s.risk_level} />
          <Typography.Text type="secondary">{s.signal_time}</Typography.Text>
          <Tag color={s.execution_mode === "shadow" ? "blue" : "green"}>{s.execution_mode || "live"}</Tag>
          {s.not_executable ? <Tag color="red">Not executable</Tag> : null}
          <Tag color={detail.outcome_status === "PENDING_OUTCOME" ? "gold" : "green"}>{detail.outcome_status || "PENDING_OUTCOME"}</Tag>
        </Space>
        <div style={{ marginTop: 8, maxWidth: 320 }}><ConfidenceBar value={s.confidence} /></div>
      </Card>
      {s.execution_mode === "shadow" ? (
        <Card style={{ marginTop: 16 }}>
          <Typography.Text type="secondary">
            {advancedMode
              ? "Shadow detail preserves the real Stock Radar candidate and proposed parameters for research validation only. It is blocked from live execution and live PnL."
              : t("该候选仅用于研究验证和回测观察，不构成交易建议。", "This candidate is for research validation and backtesting review only; not financial advice.")}
          </Typography.Text>
        </Card>
      ) : null}

      {advancedMode ? (
        <Card style={{ marginTop: 16 }} title="ResearchOps Provenance">
          {lineage && provenanceNodes.length ? (
            <Table<ResearchOpsObject>
              size="small"
              rowKey="object_id"
              dataSource={provenanceNodes}
              pagination={false}
              columns={[
                {
                  title: "Object",
                  dataIndex: "object_id",
                  render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
                },
                { title: "Type", dataIndex: "object_type", width: 160, render: (v: string) => <Tag>{v}</Tag> },
                {
                  title: "Status",
                  dataIndex: "status",
                  width: 130,
                  render: (v: string) => <Tag color={v === "OK" || v === "SUCCESS" || v === "OPEN" ? "green" : v === "BLOCKED" || v === "FAILED" ? "red" : "gold"}>{v}</Tag>,
                },
                { title: "Source", dataIndex: "source_system", width: 180 },
              ]}
            />
          ) : (
            <EmptyState title="No registered provenance" description="Run ResearchOps rebuild-index after materializing signal artifacts." />
          )}
          {lineage?.missing_references.length ? (
            <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              Missing references: {lineage.missing_references.map((item) => item.object_id || item.artifact_path || item.reason).join(", ")}
            </Typography.Paragraph>
          ) : null}
        </Card>
      ) : null}

      <Card style={{ marginTop: 16 }} title={advancedMode ? "Outcome Price Path" : t("后续价格观察", "Outcome Price Path")}>
        {chartData.length > 0 ? (
          <Line data={chartData} xField="t" yField="value" seriesField="series" height={280} />
        ) : (
          <EmptyState
            title={advancedMode ? (s.execution_mode === "shadow" ? "SHADOW_PENDING" : "PENDING_OUTCOME") : t("暂无后续价格观察", "Outcome pending")}
            description={advancedMode ? "No post-entry daily price coverage has been materialized for this signal yet." : t("该信号暂未形成完整的后续价格路径。", "The follow-up price path is not available yet.")}
          />
        )}
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={12} xs={24}>
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <Card title={advancedMode ? "Core Trade Params" : t("信号参数", "Signal Parameters")}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label={advancedMode ? "Entry Type" : t("入场类型", "Entry Type")}>{s.entry_type}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Entry Price" : t("入场参考", "Entry Price")}>{s.entry_price}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Stop Loss" : t("止损参考", "Stop Loss")}>{s.stop_loss}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Take Profit" : t("止盈参考", "Take Profit")}>{s.take_profit}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Position Scale" : t("仓位比例", "Position Scale")}>{Math.round(s.position_scale * 100)}%</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Proposed Scale" : t("建议比例", "Proposed Scale")}>{s.proposed_position_scale != null ? `${Math.round(s.proposed_position_scale * 100)}%` : "-"}</Descriptions.Item>
                {advancedMode ? <Descriptions.Item label="Router Risk Scale">{s.router_risk_scale ?? "-"}</Descriptions.Item> : null}
                <Descriptions.Item label={advancedMode ? "Router Block Reason" : t("风险状态", "Risk State")}>{advancedMode ? (s.router_block_reason || "-") : formatBlockReason(s.router_block_reason)}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Expected Holding Bars" : t("预期观察周期", "Expected Holding Bars")}>{s.expected_holding_bars}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Risk Level" : t("风险等级", "Risk Level")}><RiskBadge value={s.risk_level} /></Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title={advancedMode ? "Reason Tags" : t("信号依据", "Reason Tags")}>
              <ReasonTagList tags={advancedMode ? s.reason_tags : friendlyReasonTags(s.reason_tags)} max={advancedMode ? 10 : 5} />
            </Card>

            <Card title={advancedMode ? "Factor Contributions" : t("因子贡献", "Factor Contributions")}>
              <Table
                size="small"
                rowKey="factor"
                dataSource={detail.factor_contributions}
                pagination={false}
                columns={advancedMode ? [
                  { title: "Factor", dataIndex: "factor" },
                  { title: "Raw", dataIndex: "raw_value" },
                  { title: "Z", dataIndex: "zscore" },
                  { title: "Contribution", dataIndex: "contribution" },
                  { title: "Direction", dataIndex: "direction" },
                ] : [
                  { title: t("因子", "Factor"), dataIndex: "factor" },
                  { title: t("贡献", "Contribution"), dataIndex: "contribution" },
                  { title: t("方向", "Direction"), dataIndex: "direction" },
                ]}
              />
            </Card>
          </Space>
        </Col>

        <Col xl={12} xs={24}>
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <Card title={advancedMode ? "Regime Snapshot" : t("市场状态", "Regime Snapshot")}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label={advancedMode ? "Regime" : t("状态", "Regime")}><RegimeBadge value={detail.regime_snapshot.regime_label} /></Descriptions.Item>
                {advancedMode ? <Descriptions.Item label="CPD Score">{detail.regime_snapshot.cpd_score}</Descriptions.Item> : null}
                {advancedMode ? <Descriptions.Item label="Cluster">{detail.regime_snapshot.cluster_id}</Descriptions.Item> : null}
                <Descriptions.Item label={advancedMode ? "Severity" : t("严重度", "Severity")}>{detail.regime_snapshot.severity_score}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Volatility" : t("波动状态", "Volatility")}>{detail.regime_snapshot.volatility_state}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Liquidity" : t("流动性", "Liquidity")}>{detail.regime_snapshot.liquidity_state}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Tail Risk" : t("尾部风险", "Tail Risk")}>{detail.regime_snapshot.tail_risk_state}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Shock Proximity" : t("冲击距离", "Shock Proximity")}>{detail.regime_snapshot.shock_proximity}</Descriptions.Item>
                {advancedMode ? <Descriptions.Item label="Data Source">{detail.regime_snapshot.data_source || "unknown"}</Descriptions.Item> : null}
              </Descriptions>
            </Card>

            <Card title={advancedMode ? "Filter Results" : t("风险过滤", "Filter Results")}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label={advancedMode ? "Allow Signal" : t("观察状态", "Allow Signal")}>{detail.filter_results.allow_signal ? t("可观察", "Observable") : t("已过滤", "Filtered")}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Risk Level" : t("风险等级", "Risk Level")}>{detail.filter_results.risk_level}</Descriptions.Item>
                <Descriptions.Item label={advancedMode ? "Filter Reasons" : t("过滤原因", "Filter Reasons")}>{advancedMode ? detail.filter_results.filter_reasons.join(", ") : friendlyReasonTags(detail.filter_results.filter_reasons).join("，")}</Descriptions.Item>
                {advancedMode ? <Descriptions.Item label="Suppressed Alternatives">{detail.filter_results.suppressed_alternatives.join(", ")}</Descriptions.Item> : null}
              </Descriptions>
            </Card>

            <Card title={advancedMode ? "Notification Logs" : t("通知记录", "Notification Logs")}>
              <Table
                size="small"
                rowKey={(r) => `${r.time}-${r.title}`}
                dataSource={detail.notification_logs}
                pagination={false}
                columns={advancedMode ? [
                  { title: "Time", dataIndex: "time", width: 180 },
                  { title: "Channel", dataIndex: "channel", width: 110 },
                  { title: "Title", dataIndex: "title" },
                ] : [
                  { title: t("时间", "Time"), dataIndex: "time", width: 180 },
                  { title: t("标题", "Title"), dataIndex: "title" },
                ]}
              />
            </Card>

            <Card title={advancedMode ? "Similar Signals" : t("相似信号", "Similar Signals")}>
              <Table
                size="small"
                rowKey="signal_id"
                dataSource={detail.similar_signals}
                pagination={false}
                columns={advancedMode ? [
                  { title: "Date", dataIndex: "signal_time", width: 180 },
                  { title: "Instrument", dataIndex: "instrument", width: 110 },
                  { title: "Regime", dataIndex: "regime_label" },
                  { title: "Template", dataIndex: "signal_template" },
                  { title: "PnL", dataIndex: "realized_pnl", width: 90 },
                ] : [
                  { title: t("日期", "Date"), dataIndex: "signal_time", width: 180 },
                  { title: t("标的", "Instrument"), dataIndex: "instrument", width: 110 },
                  { title: t("市场状态", "Regime"), dataIndex: "regime_label" },
                  { title: t("结果", "PnL"), dataIndex: "realized_pnl", width: 90 },
                ]}
              />
            </Card>
          </Space>
        </Col>
      </Row>

      <Card style={{ marginTop: 16 }}>
        <Tabs
          items={[
            {
              key: "outcome",
              label: advancedMode ? "Outcome" : t("结果观察", "Outcome"),
              children: (
                <Descriptions column={2} size="small">
                  <Descriptions.Item label={advancedMode ? "Status" : t("状态", "Status")}>{detail.performance_tracking.status || detail.outcome_status || t("等待观察", "PENDING_OUTCOME")}</Descriptions.Item>
                  <Descriptions.Item label={advancedMode ? "Entry Date" : t("入场日期", "Entry Date")}>{detail.performance_tracking.entry_date || "-"}</Descriptions.Item>
                  <Descriptions.Item label={advancedMode ? "Last Date" : t("最近日期", "Last Date")}>{detail.performance_tracking.last_date || "-"}</Descriptions.Item>
                  <Descriptions.Item label={advancedMode ? "Unrealized PnL" : t("浮动结果", "Unrealized PnL")}>{detail.performance_tracking.unrealized_pnl}</Descriptions.Item>
                  <Descriptions.Item label={advancedMode ? "Realized PnL" : t("已实现结果", "Realized PnL")}>{detail.performance_tracking.realized_pnl ?? "-"}</Descriptions.Item>
                  <Descriptions.Item label="MFE">{detail.performance_tracking.mfe}</Descriptions.Item>
                  <Descriptions.Item label="MAE">{detail.performance_tracking.mae}</Descriptions.Item>
                  <Descriptions.Item label={advancedMode ? "Bars Elapsed" : t("观察周期", "Bars Elapsed")}>{detail.performance_tracking.bars_elapsed}</Descriptions.Item>
                  {advancedMode ? <Descriptions.Item label="Source Run">{detail.performance_tracking.source_run_id || "-"}</Descriptions.Item> : null}
                  {advancedMode ? <Descriptions.Item label="Execution Mode">{detail.performance_tracking.execution_mode || s.execution_mode || "live"}</Descriptions.Item> : null}
                </Descriptions>
              ),
            },
            ...(advancedMode ? [{
              key: "audit",
              label: "Audit",
              children: <Typography.Text>Audit trail is sourced from snapshot metadata, notification logs, and filter results above.</Typography.Text>,
            },
            { key: "raw", label: "Raw JSON", children: <JsonViewer value={detail} /> }] : []),
          ]}
        />
      </Card>
    </PageContainer>
  );
}


