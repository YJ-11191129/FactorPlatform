"use client";

import dynamic from "next/dynamic";
import { Button, Card, Col, Row, Skeleton, Space, Table, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { MetricCard } from "@/components/common/MetricCard";
import { CopyableCodeBlock } from "@/components/common/CopyableCodeBlock";
import { PageContainer } from "@/components/layout/PageContainer";
import { getEquityCurve, listBacktests } from "@/lib/api/backtests";
import type { BacktestSummary, EquityPoint } from "@/types/backtest";

type LoadState = "loading" | "error" | "ready";

const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });

function isAuthError(e: unknown): boolean {
  return Boolean(e && typeof e === "object" && "status" in e && (e as any).status === 401);
}

export default function BacktestResultPage(props: { params: { backtestId: string } }) {
  const router = useRouter();
  const backtestId = props.params.backtestId;

  const [state, setState] = useState<LoadState>("loading");
  const [rows, setRows] = useState<EquityPoint[]>([]);
  const [summary, setSummary] = useState<BacktestSummary | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const [curve, list] = await Promise.all([getEquityCurve(backtestId), listBacktests(200)]);
      setRows(curve.items || []);
      setSummary(list.find((x) => x.backtest_id === backtestId) || null);
      setState("ready");
    } catch (e) {
      if (isAuthError(e)) {
        message.error("缺少 API Key：请到 Settings 页面配置。");
      }
      setState("error");
    }
  }, [backtestId]);

  useEffect(() => {
    load();
  }, [load]);

  const metrics = useMemo(() => {
    const m = summary?.metrics || {};
    const pick = (k: string) => {
      const v = (m as any)[k];
      return typeof v === "number" ? Math.round(v * 10000) / 10000 : v;
    };
    return {
      total_return: pick("total_return"),
      annual_return: pick("annual_return"),
      sharpe: pick("sharpe"),
      max_drawdown: pick("max_drawdown"),
    };
  }, [summary]);

  const chartData = useMemo(() => rows.map((r) => ({ date: r.trade_date, equity: r.equity })), [rows]);
  const isAiStrategy = summary?.strategy_id === "ai_strategy_spec";
  const aiStrategySpec = summary?.strategy_spec;

  const chartConfig = useMemo(
    () => ({
      data: chartData,
      xField: "date",
      yField: "equity",
      height: 360,
      smooth: true,
      tooltip: { showMarkers: false },
      slider: { start: 0, end: 1 },
    }),
    [chartData]
  );

  const columns: ColumnsType<EquityPoint> = [
    { title: "日期", dataIndex: "trade_date", key: "trade_date", width: 120, fixed: "left" },
    { title: "净值", dataIndex: "equity", key: "equity", width: 160, render: (v) => (typeof v === "number" ? v.toFixed(2) : "-") },
    { title: "日收益", dataIndex: "net_ret", key: "net_ret", width: 120, render: (v) => (typeof v === "number" ? v.toFixed(6) : "-") },
  ];

  return (
    <PageContainer title="回测结果" subtitle={backtestId}>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Space wrap>
            <Button onClick={() => router.push("/strategies")}>返回策略库</Button>
            <Button onClick={load}>
              刷新
            </Button>
            <Button
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(backtestId);
                  message.success("已复制 Backtest ID");
                } catch {
                  message.error("复制失败");
                }
              }}
            >
              复制 ID
            </Button>
          </Space>
        </Col>
      </Row>

      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : state === "error" ? (
        <ErrorState title="回测结果加载失败" onRetry={load} />
      ) : rows.length === 0 ? (
        <EmptyState title="暂无净值数据" actionText="重试" onAction={load} />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            <Col span={6}>
              <MetricCard title="总收益" value={metrics.total_return ?? "-"} />
            </Col>
            <Col span={6}>
              <MetricCard title="年化收益" value={metrics.annual_return ?? "-"} />
            </Col>
            <Col span={6}>
              <MetricCard title="Sharpe" value={metrics.sharpe ?? "-"} />
            </Col>
            <Col span={6}>
              <MetricCard title="最大回撤" value={metrics.max_drawdown ?? "-"} />
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col span={24}>
              <Card title="净值曲线">
                <Line {...(chartConfig as any)} />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col span={24}>
              <Card title="净值明细">
                <Table
                  size="middle"
                  rowKey={(r) => r.trade_date}
                  dataSource={rows}
                  columns={columns}
                  pagination={{ pageSize: 30 }}
                  scroll={{ x: 520, y: 520 }}
                />
              </Card>
            </Col>
          </Row>

          {summary ? (
            <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
              <Col span={24}>
                <Card title="回测信息">
                  <Typography.Paragraph style={{ marginBottom: 0 }}>
                    <Typography.Text type="secondary">策略：</Typography.Text>
                    <Typography.Text>{summary.strategy_name}</Typography.Text>
                    <Typography.Text type="secondary">（{summary.strategy_id}）</Typography.Text>
                  </Typography.Paragraph>
                  {isAiStrategy ? (
                    <Space wrap style={{ marginTop: 12 }}>
                      <Button onClick={() => router.push("/ai-strategy-builder")}>AI Strategy Builder</Button>
                      <Typography.Text type="secondary">Generated by controlled StrategySpec backtest flow.</Typography.Text>
                    </Space>
                  ) : null}
                  {isAiStrategy && aiStrategySpec ? (
                    <div style={{ marginTop: 12 }}>
                      <CopyableCodeBlock code={JSON.stringify(aiStrategySpec, null, 2)} />
                    </div>
                  ) : null}
                </Card>
              </Col>
            </Row>
          ) : null}
        </>
      )}
    </PageContainer>
  );
}
