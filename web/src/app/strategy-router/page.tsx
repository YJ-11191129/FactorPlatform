"use client";

import { Alert, Card, Col, Descriptions, Row, Skeleton, Space, Table, Tag } from "antd";
import { useEffect, useMemo, useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { getEnumsMeta, getStrategyRouterCurrent, getStrategyRouterHistory } from "@/lib/api/signal-center";
import type { StrategyRouterCurrent, StrategyRouterLog } from "@/types/signal-center";

const regimes = ["CALM_LOW_VOL", "TREND_RISK_ON", "FRAGILE_HIGH_VOL", "LIQUIDITY_SHOCK", "POST_SHOCK_REBOUND"];

export default function StrategyRouterPage() {
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");
  const [current, setCurrent] = useState<StrategyRouterCurrent | null>(null);
  const [logs, setLogs] = useState<StrategyRouterLog[]>([]);
  const [templates, setTemplates] = useState<string[]>([]);

  async function load() {
    setState("loading");
    try {
      const [currentRes, historyRes, enums] = await Promise.all([getStrategyRouterCurrent(), getStrategyRouterHistory(), getEnumsMeta()]);
      setCurrent(currentRes);
      setLogs(historyRes.items);
      setTemplates(enums.signal_template || []);
      setState("ready");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const matrixData = useMemo(() => {
    if (!current) return [];
    const usedTemplates = templates.slice(0, 6);
    return regimes.map((regime) => {
      const row: Record<string, string> = { regime };
      for (const t of usedTemplates) {
        if (current.enabled_templates.includes(t)) row[t] = "enabled";
        else if (current.blocked_templates.includes(t)) row[t] = "blocked";
        else row[t] = "conditional";
      }
      return row;
    });
  }, [current, templates]);

  if (state === "loading") return <Skeleton active paragraph={{ rows: 10 }} />;
  if (state === "error" || !current) return <ErrorState title="Strategy router load failed" onRetry={load} />;

  const displayedTemplates = templates.slice(0, 6);

  return (
    <PageContainer title="Strategy Router" subtitle="Regime-to-template routing and threshold governance">
      <Alert
        type={current.is_live_blocked || current.risk_scale === 0 ? "warning" : "info"}
        showIcon
        style={{ marginBottom: 16 }}
        message="Router is computed from the latest Regime snapshot"
        description={`Source: ${current.source || "regime_snapshot"}; snapshot time: ${current.regime_snapshot_time || "-"}; regime_date=${current.regime_freshness?.regime_date || "-"}; signal_date=${current.regime_freshness?.signal_date || "-"}; lag=${current.regime_freshness?.freshness_lag_days ?? "-"}; block_reason=${current.block_reason || current.regime_freshness?.block_reason || "-"}`}
      />
      <Card title="Current Router Summary">
        <Descriptions column={3}>
          <Descriptions.Item label="Router Version">{current.router_version}</Descriptions.Item>
          <Descriptions.Item label="Source">{current.source || "regime_snapshot"}</Descriptions.Item>
          <Descriptions.Item label="Current Regime">{current.current_regime}</Descriptions.Item>
          <Descriptions.Item label="Regime Snapshot">{current.regime_snapshot_time || "-"}</Descriptions.Item>
          <Descriptions.Item label="Risk Scale">{current.risk_scale}</Descriptions.Item>
          <Descriptions.Item label="Turnover Limit">{current.turnover_limit ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Threshold Profile">{current.threshold_profile}</Descriptions.Item>
          <Descriptions.Item label="Block Reason">{current.block_reason || "-"}</Descriptions.Item>
          <Descriptions.Item label="Regime Freshness">{current.regime_freshness?.status || "-"}</Descriptions.Item>
          <Descriptions.Item label="Enabled Templates">{current.enabled_templates.join(", ")}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="Regime-to-Template Matrix" style={{ marginTop: 16 }}>
        <Table
          rowKey="regime"
          dataSource={matrixData}
          scroll={{ x: 1000 }}
          columns={[
            { title: "Regime", dataIndex: "regime", fixed: "left", width: 180 },
            ...displayedTemplates.map((template) => ({
              title: template,
              dataIndex: template,
              key: template,
              render: (v: string) =>
                v === "enabled" ? <Tag color="green">enabled</Tag> : v === "blocked" ? <Tag color="red">blocked</Tag> : <Tag>conditional</Tag>,
            })),
          ]}
        />
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={12} xs={24}>
          <Card title="Threshold Profiles / Risk Scale">
            <Space direction="vertical" style={{ width: "100%" }}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Confidence Threshold">0.70</Descriptions.Item>
                <Descriptions.Item label="Volatility Ceiling">HIGH_VOL</Descriptions.Item>
                <Descriptions.Item label="Liquidity Threshold">RECOVERING+</Descriptions.Item>
                <Descriptions.Item label="Max Concurrent Signals">6</Descriptions.Item>
                <Descriptions.Item label="Position Scale">{Math.round(current.risk_scale * 100)}%</Descriptions.Item>
              </Descriptions>
            </Space>
          </Card>
        </Col>

        <Col xl={12} xs={24}>
          <Card title="Enabled / Blocked Templates">
            <Space direction="vertical" style={{ width: "100%" }}>
              <div>
                Enabled: {current.enabled_templates.map((x) => <Tag key={x} color="green">{x}</Tag>)}
              </div>
              <div>
                Blocked: {current.blocked_templates.map((x) => <Tag key={x} color="red">{x}</Tag>)}
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="Change Logs" style={{ marginTop: 16 }}>
        <Table
          rowKey={(r) => `${r.changed_at}-${r.field}`}
          dataSource={logs}
          columns={[
            { title: "Changed At", dataIndex: "changed_at", width: 180 },
            { title: "Changed By", dataIndex: "changed_by", width: 120 },
            { title: "Regime", dataIndex: "regime", width: 170 },
            { title: "Field", dataIndex: "field", width: 140 },
            { title: "Old Value", dataIndex: "old_value" },
            { title: "New Value", dataIndex: "new_value" },
          ]}
        />
      </Card>
    </PageContainer>
  );
}
