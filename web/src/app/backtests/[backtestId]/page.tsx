"use client";

import dynamic from "next/dynamic";
import { Alert, Button, Card, Col, Descriptions, Row, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { CopyableCodeBlock } from "@/components/common/CopyableCodeBlock";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { MetricCard } from "@/components/common/MetricCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { getEquityCurve, listBacktests } from "@/lib/api/backtests";
import type { BacktestSummary, EquityPoint } from "@/types/backtest";

type LoadState = "loading" | "error" | "ready";

const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });

function isAuthError(e: unknown): boolean {
  return Boolean(e && typeof e === "object" && "status" in e && (e as any).status === 401);
}

function formatPercent(value: unknown): string {
  return typeof value === "number" ? `${(value * 100).toFixed(2)}%` : "-";
}

function formatNumber(value: unknown, digits = 2): string {
  return typeof value === "number" ? value.toFixed(digits) : "-";
}

function sourceLabel(summary: BacktestSummary | null, advancedMode: boolean): string {
  const source = summary?.price_data_source || {};
  const kind = String(source.kind || "-");
  const region = source.region ? ` / ${String(source.region).toUpperCase()}` : "";
  const sourceId = source.source_id ? ` / ${String(source.source_id)}` : "";
  if (!advancedMode) {
    const readableKind = kind === "qlib" ? "本地行情数据" : kind === "parquet" ? "本地历史数据" : "历史数据";
    return `${readableKind}${region}`;
  }
  return `${kind}${region}${sourceId}`;
}

function sourceDetail(summary: BacktestSummary | null): string {
  const source = summary?.price_data_source || {};
  return String(source.provider_uri || source.path || source.source_id || "-");
}

function dataHealthMessage(dataHealth: Record<string, any> | null): string {
  if (!dataHealth) return "请确认回测数据源状态。";
  if (dataHealth.using_latest_available && dataHealth.effective_end_date) {
    return `当前回测已使用最新可用历史数据，截止 ${dataHealth.effective_end_date}。该提示不影响结果查看，但不代表最新交易日已完成刷新。`;
  }
  const raw = String(dataHealth.message || "");
  if (/fresh|stale|only has data through|provider_uri|qlib_/i.test(raw)) {
    return "回测数据存在新鲜度提示，可刷新数据后重新运行，或将结束日期设为已有数据区间内。";
  }
  return raw || "请确认回测数据源状态。";
}

function timingDescription(summary: BacktestSummary | null, executionModel: Record<string, any>, advancedMode: boolean): string {
  if (advancedMode) return summary?.timing_note || String(executionModel.return_alignment || "-");
  if (!summary?.timing_note && !executionModel.return_alignment) return "-";
  return "信号在当期收盘后形成，并从下一可交易周期开始计入收益，避免未来函数。";
}

function costDescription(summary: BacktestSummary | null, executionModel: Record<string, any>, advancedMode: boolean): string {
  if (advancedMode) return String(executionModel.cost_model || `${summary?.fee_bps ?? "-"} bps`);
  return `单边交易成本 ${summary?.fee_bps ?? "-"} bps`;
}

export default function BacktestResultPage(props: { params: { backtestId: string } }) {
  const router = useRouter();
  const [advancedMode] = useAdvancedMode();
  const backtestId = props.params.backtestId;

  const [state, setState] = useState<LoadState>("loading");
  const [rows, setRows] = useState<EquityPoint[]>([]);
  const [summary, setSummary] = useState<BacktestSummary | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const curve = await getEquityCurve(backtestId);
      setRows(curve.items || []);
      let summaryFromList: BacktestSummary | null = null;
      try {
        const list = await listBacktests(200);
        summaryFromList = list.find((x) => x.backtest_id === backtestId) || null;
      } catch {
        summaryFromList = null;
      }
      setSummary(summaryFromList || curve.summary || null);
      setState("ready");
    } catch (e) {
      if (isAuthError(e)) {
        message.error("API key 不匹配：请到 Settings 更新 FP_API_KEY。");
      }
      setState("error");
    }
  }, [backtestId]);

  useEffect(() => {
    load();
  }, [load]);

  const metrics = useMemo(() => summary?.metrics || {}, [summary]);
  const chartData = useMemo(() => rows.map((r) => ({ date: r.trade_date, equity: r.equity })), [rows]);
  const drawdownData = useMemo(() => {
    let peak = 0;
    return rows.map((row) => {
      peak = Math.max(peak, row.equity || 0);
      const drawdown = peak > 0 ? row.equity / peak - 1 : 0;
      return { date: row.trade_date, drawdown };
    });
  }, [rows]);
  const monthlyRows = useMemo(() => {
    const buckets = new Map<string, { first: number; last: number }>();
    rows.forEach((row) => {
      const month = row.trade_date.slice(0, 7);
      const current = buckets.get(month);
      if (!current) {
        buckets.set(month, { first: row.equity, last: row.equity });
        return;
      }
      current.last = row.equity;
    });
    return Array.from(buckets.entries()).slice(-12).map(([month, item]) => ({
      month,
      return: item.first ? item.last / item.first - 1 : 0,
    }));
  }, [rows]);
  const isAiStrategy = summary?.strategy_id === "ai_strategy_spec";
  const aiStrategySpec = summary?.strategy_spec;
  const diagnostics = summary?.diagnostics || {};
  const executionModel = summary?.execution_model || {};
  const dataHealth = summary?.data_health || null;

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
    [chartData],
  );
  const drawdownConfig = useMemo(
    () => ({
      data: drawdownData,
      xField: "date",
      yField: "drawdown",
      height: 260,
      smooth: true,
      color: "#ef4444",
      tooltip: { showMarkers: false },
    }),
    [drawdownData],
  );

  const columns: ColumnsType<EquityPoint> = [
    { title: "日期", dataIndex: "trade_date", key: "trade_date", width: 120, fixed: "left" },
    { title: "净值", dataIndex: "equity", key: "equity", width: 150, render: (v) => formatNumber(v, 2) },
    { title: "净收益", dataIndex: "net_ret", key: "net_ret", width: 110, render: formatPercent },
    { title: "毛收益", dataIndex: "gross_ret", key: "gross_ret", width: 110, render: formatPercent },
    { title: "换手", dataIndex: "turnover", key: "turnover", width: 100, render: formatPercent },
    { title: "成本", dataIndex: "cost", key: "cost", width: 100, render: formatPercent },
  ];

  return (
    <PageContainer title="回测结果" subtitle={advancedMode ? backtestId : "历史回测报告"}>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Space wrap>
            <Button onClick={() => router.push("/strategies")}>返回回测工作台</Button>
            <Button onClick={load}>刷新</Button>
            {advancedMode ? (
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
            ) : null}
            <Tag>{sourceLabel(summary, advancedMode)}</Tag>
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
          {dataHealth && dataHealth.blocking_status && dataHealth.blocking_status !== "OK" ? (
            <Alert
              type={dataHealth.blocking_status === "BLOCKED" ? "error" : "warning"}
              showIcon
              style={{ marginBottom: 16 }}
              message="数据新鲜度提示"
              description={dataHealthMessage(dataHealth as Record<string, any> | null)}
            />
          ) : null}

          <Row gutter={[16, 16]}>
            <Col xs={12} lg={4}>
              <MetricCard title="总收益" value={formatPercent(metrics.total_return)} />
            </Col>
            <Col xs={12} lg={4}>
              <MetricCard title="年化收益" value={formatPercent(metrics.annual_return)} />
            </Col>
            <Col xs={12} lg={4}>
              <MetricCard title="Sharpe" value={formatNumber(metrics.sharpe)} />
            </Col>
            <Col xs={12} lg={4}>
              <MetricCard title="最大回撤" value={formatPercent(metrics.max_drawdown)} />
            </Col>
            <Col xs={12} lg={4}>
              <MetricCard title="日均换手" value={formatPercent(metrics.avg_daily_turnover)} />
            </Col>
            <Col xs={12} lg={4}>
              <MetricCard title="交易成本" value={formatNumber(metrics.total_transaction_cost, 0)} />
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} xl={16}>
              <Card title="净值曲线">
                <Line {...(chartConfig as any)} />
              </Card>
            </Col>
            <Col xs={24} xl={8}>
              <Card title="回撤曲线">
                <Line {...(drawdownConfig as any)} />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} xl={14}>
              <Card title="净值明细">
                <Table
                  size="middle"
                  rowKey={(r) => r.trade_date}
                  dataSource={rows}
                  columns={columns}
                  pagination={{ pageSize: 30 }}
                  scroll={{ x: 700, y: 520 }}
                />
              </Card>
            </Col>
            <Col xs={24} xl={10}>
              <Card title="月度收益">
                <Table
                  size="small"
                  rowKey="month"
                  dataSource={monthlyRows}
                  pagination={false}
                  columns={[
                    { title: "月份", dataIndex: "month" },
                    { title: "收益", dataIndex: "return", render: formatPercent },
                  ]}
                />
              </Card>
              <Card title="回测说明" style={{ marginTop: 16 }}>
                <Descriptions column={1} size="small" bordered>
                  <Descriptions.Item label="策略">{summary?.strategy_name || "-"}</Descriptions.Item>
                  {advancedMode ? <Descriptions.Item label="策略 ID">{summary?.strategy_id || "-"}</Descriptions.Item> : null}
                  <Descriptions.Item label="数据源">{sourceLabel(summary, advancedMode)}</Descriptions.Item>
                  {advancedMode ? <Descriptions.Item label="数据路径">{sourceDetail(summary)}</Descriptions.Item> : null}
                  <Descriptions.Item label="价格区间">
                    {String(diagnostics.price_start_date || "-")} ~ {String(diagnostics.price_end_date || "-")}
                  </Descriptions.Item>
                  <Descriptions.Item label="资产数">{String(diagnostics.simulated_asset_count || diagnostics.price_asset_count || "-")}</Descriptions.Item>
                  <Descriptions.Item label="时序假设">{timingDescription(summary, executionModel, advancedMode)}</Descriptions.Item>
                  <Descriptions.Item label="成本模型">{costDescription(summary, executionModel, advancedMode)}</Descriptions.Item>
                </Descriptions>
                <Alert
                  showIcon
                  type="info"
                  style={{ marginTop: 12 }}
                  message="时序保护"
                  description="本回测使用上一期持仓计算下一期收益，避免用当日收盘生成信号后直接吃到同一根 bar 的收益。"
                />
              </Card>
            </Col>
          </Row>

          {summary ? (
            <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
              <Col span={24}>
                <Card title={advancedMode ? "结构化摘要" : "回测结论"}>
                  <Space wrap style={{ marginBottom: 12 }}>
                    {isAiStrategy ? <Button onClick={() => router.push("/ai-strategy-builder")}>AI 策略生成器</Button> : null}
                    <Button onClick={() => router.push("/strategies")}>继续回测</Button>
                  </Space>
                  {!advancedMode ? (
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      回测报告已生成，可结合净值曲线、回撤、换手和数据区间提示进行复盘。本页面仅用于辅助研究与风险识别。
                    </Typography.Paragraph>
                  ) : isAiStrategy && aiStrategySpec ? (
                    <CopyableCodeBlock code={JSON.stringify(aiStrategySpec, null, 2)} />
                  ) : (
                    <CopyableCodeBlock
                      code={JSON.stringify(
                        {
                          backtest_id: summary.backtest_id,
                          metrics: summary.metrics,
                          price_data_source: summary.price_data_source,
                          execution_model: summary.execution_model,
                          diagnostics: summary.diagnostics,
                        },
                        null,
                        2,
                      )}
                    />
                  )}
                </Card>
              </Col>
            </Row>
          ) : null}
        </>
      )}
    </PageContainer>
  );
}
