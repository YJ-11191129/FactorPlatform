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
import { getResearchOpsLineage } from "@/lib/api/research-ops";
import { getSignalDetail } from "@/lib/api/signal-center";
import type { ResearchOpsLineage, ResearchOpsObject } from "@/types/research-ops";
import type { SignalDetail } from "@/types/signal-center";

const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });

type LoadState = "loading" | "error" | "ready";

export default function SignalDetailPage() {
  const params = useParams<{ signalId: string }>();
  const searchParams = useSearchParams();
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
        getResearchOpsLineage(signalId),
      ]);
      if (detailRes.status === "rejected") throw detailRes.reason;
      setDetail(detailRes.value);
      setLineage(lineageRes.status === "fulfilled" ? lineageRes.value : null);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [signalId, executionMode]);

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
  if (state === "error" || !detail) return <ErrorState title="Signal detail load failed" onRetry={load} />;

  const s = detail.signal;
  const provenanceNodes = (lineage?.nodes || []).filter((node) => node.object_type !== "external_reference");

  return (
    <PageContainer
      title={`Signal Detail - ${s.instrument}`}
      subtitle="Explainability, risk controls, and similar signal review"
      breadcrumb={["Signal Center", s.signal_id]}
      extra={
        <Space>
          <Button onClick={() => navigator.clipboard.writeText(location.href).then(() => message.success("Link copied"))}>Copy Link</Button>
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
            Shadow detail preserves the real Stock Radar candidate and proposed parameters for research validation only. It is blocked from live execution and live PnL.
          </Typography.Text>
        </Card>
      ) : null}

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

      <Card style={{ marginTop: 16 }} title="Outcome Price Path">
        {chartData.length > 0 ? (
          <Line data={chartData} xField="t" yField="value" seriesField="series" height={280} />
        ) : (
          <EmptyState
            title={s.execution_mode === "shadow" ? "SHADOW_PENDING" : "PENDING_OUTCOME"}
            description="No post-entry daily price coverage has been materialized for this signal yet."
          />
        )}
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={12} xs={24}>
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <Card title="Core Trade Params">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Entry Type">{s.entry_type}</Descriptions.Item>
                <Descriptions.Item label="Entry Price">{s.entry_price}</Descriptions.Item>
                <Descriptions.Item label="Stop Loss">{s.stop_loss}</Descriptions.Item>
                <Descriptions.Item label="Take Profit">{s.take_profit}</Descriptions.Item>
                <Descriptions.Item label="Position Scale">{Math.round(s.position_scale * 100)}%</Descriptions.Item>
                <Descriptions.Item label="Proposed Scale">{s.proposed_position_scale != null ? `${Math.round(s.proposed_position_scale * 100)}%` : "-"}</Descriptions.Item>
                <Descriptions.Item label="Router Risk Scale">{s.router_risk_scale ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="Router Block Reason">{s.router_block_reason || "-"}</Descriptions.Item>
                <Descriptions.Item label="Expected Holding Bars">{s.expected_holding_bars}</Descriptions.Item>
                <Descriptions.Item label="Risk Level"><RiskBadge value={s.risk_level} /></Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title="Reason Tags">
              <ReasonTagList tags={s.reason_tags} max={10} />
            </Card>

            <Card title="Factor Contributions">
              <Table
                size="small"
                rowKey="factor"
                dataSource={detail.factor_contributions}
                pagination={false}
                columns={[
                  { title: "Factor", dataIndex: "factor" },
                  { title: "Raw", dataIndex: "raw_value" },
                  { title: "Z", dataIndex: "zscore" },
                  { title: "Contribution", dataIndex: "contribution" },
                  { title: "Direction", dataIndex: "direction" },
                ]}
              />
            </Card>
          </Space>
        </Col>

        <Col xl={12} xs={24}>
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <Card title="Regime Snapshot">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Regime"><RegimeBadge value={detail.regime_snapshot.regime_label} /></Descriptions.Item>
                <Descriptions.Item label="CPD Score">{detail.regime_snapshot.cpd_score}</Descriptions.Item>
                <Descriptions.Item label="Cluster">{detail.regime_snapshot.cluster_id}</Descriptions.Item>
                <Descriptions.Item label="Severity">{detail.regime_snapshot.severity_score}</Descriptions.Item>
                <Descriptions.Item label="Volatility">{detail.regime_snapshot.volatility_state}</Descriptions.Item>
                <Descriptions.Item label="Liquidity">{detail.regime_snapshot.liquidity_state}</Descriptions.Item>
                <Descriptions.Item label="Tail Risk">{detail.regime_snapshot.tail_risk_state}</Descriptions.Item>
                <Descriptions.Item label="Shock Proximity">{detail.regime_snapshot.shock_proximity}</Descriptions.Item>
                <Descriptions.Item label="Data Source">{detail.regime_snapshot.data_source || "unknown"}</Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title="Filter Results">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Allow Signal">{String(detail.filter_results.allow_signal)}</Descriptions.Item>
                <Descriptions.Item label="Risk Level">{detail.filter_results.risk_level}</Descriptions.Item>
                <Descriptions.Item label="Filter Reasons">{detail.filter_results.filter_reasons.join(", ")}</Descriptions.Item>
                <Descriptions.Item label="Suppressed Alternatives">{detail.filter_results.suppressed_alternatives.join(", ")}</Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title="Notification Logs">
              <Table
                size="small"
                rowKey={(r) => `${r.time}-${r.title}`}
                dataSource={detail.notification_logs}
                pagination={false}
                columns={[
                  { title: "Time", dataIndex: "time", width: 180 },
                  { title: "Channel", dataIndex: "channel", width: 110 },
                  { title: "Title", dataIndex: "title" },
                ]}
              />
            </Card>

            <Card title="Similar Signals">
              <Table
                size="small"
                rowKey="signal_id"
                dataSource={detail.similar_signals}
                pagination={false}
                columns={[
                  { title: "Date", dataIndex: "signal_time", width: 180 },
                  { title: "Instrument", dataIndex: "instrument", width: 110 },
                  { title: "Regime", dataIndex: "regime_label" },
                  { title: "Template", dataIndex: "signal_template" },
                  { title: "PnL", dataIndex: "realized_pnl", width: 90 },
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
              label: "Outcome",
              children: (
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="Status">{detail.performance_tracking.status || detail.outcome_status || "PENDING_OUTCOME"}</Descriptions.Item>
                  <Descriptions.Item label="Entry Date">{detail.performance_tracking.entry_date || "-"}</Descriptions.Item>
                  <Descriptions.Item label="Last Date">{detail.performance_tracking.last_date || "-"}</Descriptions.Item>
                  <Descriptions.Item label="Unrealized PnL">{detail.performance_tracking.unrealized_pnl}</Descriptions.Item>
                  <Descriptions.Item label="Realized PnL">{detail.performance_tracking.realized_pnl ?? "-"}</Descriptions.Item>
                  <Descriptions.Item label="MFE">{detail.performance_tracking.mfe}</Descriptions.Item>
                  <Descriptions.Item label="MAE">{detail.performance_tracking.mae}</Descriptions.Item>
                  <Descriptions.Item label="Bars Elapsed">{detail.performance_tracking.bars_elapsed}</Descriptions.Item>
                  <Descriptions.Item label="Source Run">{detail.performance_tracking.source_run_id || "-"}</Descriptions.Item>
                  <Descriptions.Item label="Execution Mode">{detail.performance_tracking.execution_mode || s.execution_mode || "live"}</Descriptions.Item>
                </Descriptions>
              ),
            },
            {
              key: "audit",
              label: "Audit",
              children: <Typography.Text>Audit trail is sourced from snapshot metadata, notification logs, and filter results above.</Typography.Text>,
            },
            { key: "raw", label: "Raw JSON", children: <JsonViewer value={detail} /> },
          ]}
        />
      </Card>
    </PageContainer>
  );
}


