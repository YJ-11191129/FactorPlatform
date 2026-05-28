"use client";

import { Alert, Button, Col, Form, Input, InputNumber, Row, Select, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { BacktestConfigPanel } from "@/components/backtests/BacktestConfigPanel";
import { StrategyListPanel } from "@/components/backtests/StrategyListPanel";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { MetricCard } from "@/components/common/MetricCard";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { getBacktestDataStatus, listBacktests, listStrategies, runBacktest } from "@/lib/api/backtests";
import { buildQlibPortfolio, generateQlibReport, listQlibFactorMiningRuns, listQlibPortfolios } from "@/lib/api/qlib-research";
import type { ApiError } from "@/lib/api/client";
import type { BacktestDataStatus, BacktestRunPayload, BacktestRunResult, BacktestSummary } from "@/types/backtest";
import type { QlibFactorMiningRun, QlibPortfolio } from "@/types/qlib-research";
import type { StrategyInfo } from "@/types/strategy";

type LoadState = "loading" | "error" | "ready";

function isApiError(e: unknown, status: number): boolean {
  return Boolean(e && typeof e === "object" && "status" in e && (e as ApiError).status === status);
}

function extractErrorMessage(e: unknown): string {
  if (!e) return "未知错误";
  if (typeof e === "string") return e;
  if (typeof e === "object") {
    if ("message" in e && typeof (e as any).message === "string") return (e as any).message;
    const detail = (e as any).detail?.detail || (e as any).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && typeof detail.message === "string") return detail.message;
  }
  return "请求失败";
}

function formatPercent(value: unknown): string {
  return typeof value === "number" ? `${(value * 100).toFixed(2)}%` : "-";
}

function formatNumber(value: unknown, digits = 2): string {
  return typeof value === "number" ? value.toFixed(digits) : "-";
}

function sourceLabel(summary: BacktestSummary | null | undefined): string {
  const source = summary?.price_data_source || {};
  const kind = String(source.kind || "-");
  const region = source.region ? ` / ${String(source.region).toUpperCase()}` : "";
  const sourceId = source.source_id ? ` / ${String(source.source_id)}` : "";
  return `${kind}${region}${sourceId}`;
}

function dataHealthWarning(dataHealth: Record<string, unknown> | null | undefined): string | null {
  if (!dataHealth || dataHealth.blocking_status === "OK") return null;
  return typeof dataHealth.message === "string" && dataHealth.message ? dataHealth.message : "数据新鲜度需要确认";
}

export default function StrategiesPage() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>("loading");
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [selected, setSelected] = useState<StrategyInfo | null>(null);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<BacktestRunResult | null>(null);
  const [backtests, setBacktests] = useState<BacktestSummary[]>([]);
  const [dataStatus, setDataStatus] = useState<BacktestDataStatus | null>(null);
  const [miningRuns, setMiningRuns] = useState<QlibFactorMiningRun[]>([]);
  const [portfolios, setPortfolios] = useState<QlibPortfolio[]>([]);
  const [buildingPortfolio, setBuildingPortfolio] = useState(false);
  const [runningPortfolioId, setRunningPortfolioId] = useState<string | null>(null);
  const [reportPortfolioId, setReportPortfolioId] = useState<string | null>(null);

  async function load() {
    setState("loading");
    try {
      const [strategyRows, recentBacktests, miningRows, portfolioRows] = await Promise.all([
        listStrategies(),
        listBacktests(50),
        listQlibFactorMiningRuns(20).catch(() => []),
        listQlibPortfolios(20).catch(() => []),
      ]);
      setStrategies(strategyRows);
      setSelected((prev) => (prev ? strategyRows.find((s) => s.strategy_id === prev.strategy_id) || null : strategyRows[0] || null));
      setBacktests(recentBacktests);
      setMiningRuns(miningRows);
      setPortfolios(portfolioRows);
      setDataStatus(await getBacktestDataStatus().catch(() => null));
      setState("ready");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const stats = useMemo(() => {
    const owners = new Set(strategies.map((s) => s.owner).filter(Boolean)).size;
    const latest = backtests[0];
    return {
      total: strategies.length,
      owners,
      recent: backtests.length,
      latestReturn: latest ? formatPercent(latest.metrics?.total_return) : "-",
    };
  }, [strategies, backtests]);

  async function onRun(payload: BacktestRunPayload) {
    setRunning(true);
    try {
      const res = await runBacktest(payload);
      setLastRun(res);
      message.success({
        content: (
          <Space>
            <span>回测完成</span>
            <Button size="small" type="link" onClick={() => router.push(`/backtests/${encodeURIComponent(res.backtest_id)}`)}>
              查看结果
            </Button>
          </Space>
        ),
      });
      const warning = dataHealthWarning(res.data_health || (res.summary.data_health as Record<string, unknown> | null | undefined));
      if (warning) message.warning(warning, 6);
      setBacktests(await listBacktests(50));
    } catch (e) {
      if (isApiError(e, 401)) {
        message.error("API key 不匹配：请到 Settings 更新 FP_API_KEY，或重启服务加载正确环境。");
      } else if (isApiError(e, 403)) {
        message.error("权限不足：运行回测需要 operator/admin，本地可使用 LOCAL_ADMIN_KEY。");
      } else if (isApiError(e, 423)) {
        message.error("当前是 Demo fallback 只读模式，不能运行真实回测。");
      } else {
        message.error(extractErrorMessage(e));
      }
    } finally {
      setRunning(false);
    }
  }

  async function onBuildPortfolio(values: any) {
    setBuildingPortfolio(true);
    try {
      const selectedFactors = String(values.selected_factors || "")
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
      const res = await buildQlibPortfolio({
        mining_run_id: values.mining_run_id,
        selected_factors: selectedFactors.length ? selectedFactors : null,
        weighting_method: values.weighting_method || "equal",
        top_n: Number(values.top_n || 5),
        long_top_n: Number(values.long_top_n || 30),
      });
      message.success(`组合已生成：${res.portfolio_id}`);
      setPortfolios(await listQlibPortfolios(20));
    } catch (e) {
      message.error(extractErrorMessage(e));
    } finally {
      setBuildingPortfolio(false);
    }
  }

  async function onRunPortfolio(portfolioId: string) {
    setRunningPortfolioId(portfolioId);
    try {
      const res = await runBacktest({
        strategy_id: null,
        portfolio_id: portfolioId,
        params: {},
        start_date: null,
        end_date: null,
        initial_cash: 1_000_000,
        fee_bps: 5,
        use_adj: true,
      });
      setLastRun(res);
      message.success("组合回测完成");
      setBacktests(await listBacktests(50));
    } catch (e) {
      message.error(extractErrorMessage(e));
    } finally {
      setRunningPortfolioId(null);
    }
  }

  async function onPortfolioReport(portfolioId: string) {
    setReportPortfolioId(portfolioId);
    try {
      const latestBacktest = backtests.find((b) => b.portfolio_id === portfolioId);
      const res = await generateQlibReport({
        report_type: "qlib_portfolio_backtest",
        portfolio_id: portfolioId,
        backtest_id: latestBacktest?.backtest_id,
      });
      message.success(`报告已生成：${String(res.html_path || "")}`);
    } catch (e) {
      message.error(extractErrorMessage(e));
    } finally {
      setReportPortfolioId(null);
    }
  }

  const backtestColumns: ColumnsType<BacktestSummary> = [
    {
      title: "Backtest",
      dataIndex: "backtest_id",
      key: "backtest_id",
      width: 230,
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: "策略",
      dataIndex: "strategy_name",
      key: "strategy_name",
      render: (_: string, r) => (
        <div>
          <Typography.Text>{r.strategy_name}</Typography.Text>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {r.strategy_id}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: "数据源",
      key: "source",
      width: 180,
      render: (_, r) => <Tag>{sourceLabel(r)}</Tag>,
    },
    {
      title: "总收益",
      dataIndex: ["metrics", "total_return"],
      key: "total_return",
      width: 110,
      render: formatPercent,
    },
    {
      title: "Sharpe",
      dataIndex: ["metrics", "sharpe"],
      key: "sharpe",
      width: 90,
      render: (v) => formatNumber(v),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
    },
  ];

  const portfolioColumns: ColumnsType<QlibPortfolio> = [
    {
      title: "Portfolio",
      dataIndex: "portfolio_id",
      key: "portfolio_id",
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: "Factors",
      dataIndex: "selected_factors",
      key: "selected_factors",
      render: (v: string[]) => <Typography.Text>{(v || []).slice(0, 3).join(", ")}{v?.length > 3 ? "..." : ""}</Typography.Text>,
    },
    { title: "Signals", dataIndex: "signal_count", key: "signal_count", width: 90 },
    {
      title: "质量状态",
      dataIndex: "promotion_status",
      key: "promotion_status",
      width: 130,
      render: (v: string) => <Tag color={v === "PROMOTED" ? "green" : "gold"}>{v || "REVIEW"}</Tag>,
    },
    {
      title: "Actions",
      key: "actions",
      width: 210,
      render: (_, r) => (
        <Space>
          <Button size="small" loading={runningPortfolioId === r.portfolio_id} onClick={() => onRunPortfolio(r.portfolio_id)}>
            回测
          </Button>
          <Button size="small" loading={reportPortfolioId === r.portfolio_id} onClick={() => onPortfolioReport(r.portfolio_id)}>
            报告
          </Button>
        </Space>
      ),
    },
  ];

  const lastSummary = lastRun?.summary as BacktestSummary | undefined;
  const lastMetrics = (lastSummary?.metrics || {}) as Record<string, unknown>;
  const latestDataHealthWarning = dataHealthWarning(lastRun?.data_health || lastSummary?.data_health);

  return (
    <PageContainer title="回测工作台" subtitle="从策略库或 qlib 因子组合发起回测，统一记录数据源、时序假设、成本与风险指标。">
      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : state === "error" ? (
        <ErrorState title="策略与回测数据加载失败" onRetry={load} />
      ) : strategies.length === 0 ? (
        <EmptyState title="暂无策略" actionText="重试" onAction={load} />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={12} lg={6}>
              <MetricCard title="策略数" value={stats.total} />
            </Col>
            <Col xs={12} lg={6}>
              <MetricCard title="Owner 数" value={stats.owners} />
            </Col>
            <Col xs={12} lg={6}>
              <MetricCard title="近期回测" value={stats.recent} />
            </Col>
            <Col xs={12} lg={6}>
              <MetricCard title="最近总收益" value={stats.latestReturn} />
            </Col>
          </Row>

          <div style={{ marginTop: 16 }}>
            <SectionCard
              title="数据与权限状态"
              extra={
                <Space>
                  <Button size="small" onClick={load}>
                    刷新
                  </Button>
                  <Button size="small" onClick={() => router.push("/settings")}>
                    Settings
                  </Button>
                </Space>
              }
            >
              <Space direction="vertical" style={{ width: "100%" }}>
                <Typography.Text type="secondary">
                  默认回测数据源是 qlib CN/US；Wind parquet 只作为 fallback。若接口返回 401，请在 Settings 保存正确的 FP_API_KEY。
                </Typography.Text>
                {dataStatus ? (
                  <Typography.Text type="secondary">
                    Wind fallback: {dataStatus.start_date || "-"} ~ {dataStatus.end_date || "-"}，{dataStatus.asset_count} 资产，{dataStatus.row_count} 行。
                  </Typography.Text>
                ) : null}
                {dataStatus?.data_health?.blocking_status && dataStatus.data_health.blocking_status !== "OK" ? (
                  <Alert
                    type={dataStatus.data_health.blocking_status === "BLOCKED" ? "warning" : "info"}
                    showIcon
                    message="Wind fallback 数据状态"
                    description={dataStatus.data_health.message || "Wind fallback freshness warning"}
                  />
                ) : null}
              </Space>
            </SectionCard>
          </div>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} xl={11}>
              <StrategyListPanel strategies={strategies} selectedId={selected?.strategy_id} onSelect={(s) => setSelected(s)} />
            </Col>
            <Col xs={24} xl={13}>
              <BacktestConfigPanel strategy={selected} loading={running} onRun={onRun} />
            </Col>
          </Row>

          {lastRun ? (
            <div style={{ marginTop: 16 }}>
              <SectionCard title="最近一次回测">
                {latestDataHealthWarning ? (
                  <Alert type="warning" showIcon message="数据新鲜度提示" description={latestDataHealthWarning} style={{ marginBottom: 12 }} />
                ) : null}
                <Row gutter={[16, 16]}>
                  <Col xs={12} lg={4}>
                    <MetricCard title="总收益" value={formatPercent(lastMetrics.total_return)} />
                  </Col>
                  <Col xs={12} lg={4}>
                    <MetricCard title="年化收益" value={formatPercent(lastMetrics.annual_return)} />
                  </Col>
                  <Col xs={12} lg={4}>
                    <MetricCard title="Sharpe" value={formatNumber(lastMetrics.sharpe)} />
                  </Col>
                  <Col xs={12} lg={4}>
                    <MetricCard title="最大回撤" value={formatPercent(lastMetrics.max_drawdown)} />
                  </Col>
                  <Col xs={12} lg={4}>
                    <MetricCard title="日均换手" value={formatPercent(lastMetrics.avg_daily_turnover)} />
                  </Col>
                  <Col xs={12} lg={4}>
                    <MetricCard title="交易成本" value={formatNumber(lastMetrics.total_transaction_cost, 0)} />
                  </Col>
                </Row>
                <Space style={{ marginTop: 12 }} wrap>
                  <Typography.Text code>{lastRun.backtest_id}</Typography.Text>
                  <Tag>{sourceLabel(lastSummary)}</Tag>
                  <Button size="small" type="primary" onClick={() => router.push(`/backtests/${encodeURIComponent(lastRun.backtest_id)}`)}>
                    查看结果
                  </Button>
                </Space>
              </SectionCard>
            </div>
          ) : null}

          <div style={{ marginTop: 16 }}>
            <SectionCard title="Native qlib 因子组合">
              <Form layout="vertical" initialValues={{ weighting_method: "equal", top_n: 5, long_top_n: 30 }} onFinish={onBuildPortfolio}>
                <Row gutter={12}>
                  <Col xs={24} lg={8}>
                    <Form.Item label="Mining run" name="mining_run_id" rules={[{ required: true, message: "请选择一个 mining run" }]}>
                      <Select showSearch placeholder="Select mining run" options={miningRuns.map((r) => ({ label: r.run_id, value: r.run_id }))} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} lg={8}>
                    <Form.Item label="Selected factors" name="selected_factors">
                      <Input placeholder="逗号分隔；留空使用 Top N" />
                    </Form.Item>
                  </Col>
                  <Col xs={12} lg={3}>
                    <Form.Item label="Weighting" name="weighting_method">
                      <Select
                        options={[
                          { label: "Equal", value: "equal" },
                          { label: "IC", value: "ic_weighted" },
                          { label: "RankIC", value: "rank_ic_weighted" },
                        ]}
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={6} lg={2}>
                    <Form.Item label="Top N" name="top_n">
                      <InputNumber min={1} max={50} style={{ width: "100%" }} />
                    </Form.Item>
                  </Col>
                  <Col xs={6} lg={3}>
                    <Form.Item label="Hold" name="long_top_n">
                      <InputNumber min={1} max={500} style={{ width: "100%" }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Button type="primary" htmlType="submit" loading={buildingPortfolio}>
                  生成组合
                </Button>
              </Form>
              <div style={{ marginTop: 16 }}>
                <Table size="small" rowKey={(r) => r.portfolio_id} dataSource={portfolios} columns={portfolioColumns} pagination={{ pageSize: 5 }} />
              </div>
            </SectionCard>
          </div>

          <div style={{ marginTop: 16 }}>
            <SectionCard title="最近回测">
              <Table
                size="small"
                rowKey={(r) => r.backtest_id}
                dataSource={backtests}
                columns={backtestColumns}
                pagination={{ pageSize: 8 }}
                scroll={{ x: 980 }}
                onRow={(record) => ({
                  onClick: () => router.push(`/backtests/${encodeURIComponent(record.backtest_id)}`),
                })}
              />
            </SectionCard>
          </div>
        </>
      )}
    </PageContainer>
  );
}
