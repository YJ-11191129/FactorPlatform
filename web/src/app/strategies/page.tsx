"use client";

import { Alert, Button, Col, Form, Input, InputNumber, Row, Select, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { MetricCard } from "@/components/common/MetricCard";
import { SectionCard } from "@/components/common/SectionCard";
import { BacktestConfigPanel } from "@/components/backtests/BacktestConfigPanel";
import { StrategyListPanel } from "@/components/backtests/StrategyListPanel";
import { PageContainer } from "@/components/layout/PageContainer";
import { getBacktestDataStatus, listBacktests, listStrategies, runBacktest } from "@/lib/api/backtests";
import { buildQlibPortfolio, generateQlibReport, listQlibFactorMiningRuns, listQlibPortfolios } from "@/lib/api/qlib-research";
import type { BacktestRunPayload, BacktestRunResult } from "@/types/backtest";
import type { StrategyInfo } from "@/types/strategy";
import type { BacktestSummary } from "@/types/backtest";
import type { BacktestDataStatus } from "@/types/backtest";
import type { QlibFactorMiningRun, QlibPortfolio } from "@/types/qlib-research";

type LoadState = "loading" | "error" | "ready";

function isAuthError(e: unknown): boolean {
  return Boolean(e && typeof e === "object" && "status" in e && (e as any).status === 401);
}

function isForbiddenError(e: unknown): boolean {
  return Boolean(e && typeof e === "object" && "status" in e && (e as any).status === 403);
}

function extractErrorMessage(e: unknown): string {
  if (!e) return "未知错误";
  if (typeof e === "string") return e;
  if (typeof e === "object") {
    if ("message" in e && typeof (e as any).message === "string") return (e as any).message;
    if ("detail" in e && typeof (e as any).detail === "string") return (e as any).detail;
  }
  return "回测失败";
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
      const [data, bt, mines, ports] = await Promise.all([
        listStrategies(),
        listBacktests(50),
        listQlibFactorMiningRuns(20).catch(() => []),
        listQlibPortfolios(20).catch(() => []),
      ]);
      setStrategies(data);
      setSelected((prev) => (prev ? data.find((s) => s.strategy_id === prev.strategy_id) || null : null));
      setBacktests(bt);
      setMiningRuns(mines);
      setPortfolios(ports);
      try {
        setDataStatus(await getBacktestDataStatus());
      } catch {

      }
      setState("ready");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const stats = useMemo(() => {
    const total = strategies.length;
    const owners = new Set(strategies.map((s) => s.owner).filter(Boolean)).size;
    return { total, owners };
  }, [strategies]);

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
      try {
        const bt = await listBacktests(50);
        setBacktests(bt);
      } catch {

      }
    } catch (e) {
      if (isAuthError(e)) {
        message.error("缺少 API Key：请到 Settings 页面配置。");
      } else if (isForbiddenError(e)) {
        message.error("权限不足：运行回测需要 operator/admin（本地可用 LOCAL_ADMIN_KEY）。");
      } else {
        message.error(extractErrorMessage(e));
      }
    } finally {
      setRunning(false);
    }
  }

  function explainApiError(e: any): string {
    const detail = e?.detail?.detail;
    if (detail && typeof detail === "object") return detail.message || detail.status || e?.message || "Request failed";
    return e?.message || "Request failed";
  }

  async function onBuildPortfolio(values: any) {
    setBuildingPortfolio(true);
    try {
      const selected = String(values.selected_factors || "")
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
      const res = await buildQlibPortfolio({
        mining_run_id: values.mining_run_id,
        selected_factors: selected.length ? selected : null,
        weighting_method: values.weighting_method || "equal",
        top_n: Number(values.top_n || 5),
        long_top_n: Number(values.long_top_n || 30),
      });
      message.success(`Portfolio built: ${res.portfolio_id}`);
      setPortfolios(await listQlibPortfolios(20));
    } catch (e: any) {
      message.error(explainApiError(e));
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
      message.success("Portfolio backtest completed");
      setBacktests(await listBacktests(50));
    } catch (e: any) {
      message.error(explainApiError(e));
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
      message.success(`Report generated: ${String(res.html_path || "")}`);
    } catch (e: any) {
      message.error(explainApiError(e));
    } finally {
      setReportPortfolioId(null);
    }
  }

  const backtestColumns: ColumnsType<BacktestSummary> = [
    {
      title: "Backtest",
      dataIndex: "backtest_id",
      key: "backtest_id",
      width: 220,
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
      title: "总收益",
      dataIndex: ["metrics", "total_return"],
      key: "total_return",
      width: 120,
      render: (v: unknown) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : "-"),
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
      render: (v: string[]) => <Typography.Text>{v.slice(0, 3).join(", ")}{v.length > 3 ? "..." : ""}</Typography.Text>,
    },
    {
      title: "Signals",
      dataIndex: "signal_count",
      key: "signal_count",
      width: 90,
    },
    {
      title: "Actions",
      key: "actions",
      width: 220,
      render: (_, r) => (
        <Space>
          <Button size="small" loading={runningPortfolioId === r.portfolio_id} onClick={() => onRunPortfolio(r.portfolio_id)}>
            Backtest
          </Button>
          <Button size="small" loading={reportPortfolioId === r.portfolio_id} onClick={() => onPortfolioReport(r.portfolio_id)}>
            Report
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer title="策略库回测" subtitle="从策略库选择策略 → 运行回测 → 查看净值曲线">
      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : state === "error" ? (
        <ErrorState title="策略列表加载失败" onRetry={load} />
      ) : strategies.length === 0 ? (
        <EmptyState title="暂无策略" actionText="重试" onAction={load} />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            <Col span={6}>
              <MetricCard title="策略数" value={stats.total} />
            </Col>
            <Col span={6}>
              <MetricCard title="Owner 数" value={stats.owners} />
            </Col>
            <Col span={12}>
              <SectionCard title="提示">
                <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
                  若接口返回 401，请先到 Settings 保存你的 `X-API-Key`。
                </Typography.Paragraph>
                {dataStatus ? (
                  <Typography.Paragraph style={{ marginTop: 8, marginBottom: 0 }} type="secondary">
                    回测数据：{dataStatus.start_date} ~ {dataStatus.end_date}，{dataStatus.asset_count} 资产，{dataStatus.row_count} 行
                  </Typography.Paragraph>
                ) : null}
                {dataStatus?.data_health?.blocking_status && dataStatus.data_health.blocking_status !== "OK" ? (
                  <Alert
                    style={{ marginTop: 8 }}
                    type={dataStatus.data_health.blocking_status === "BLOCKED" ? "error" : "warning"}
                    showIcon
                    message={dataStatus.data_health.message || "Backtest data freshness warning"}
                  />
                ) : null}
                <Space style={{ marginTop: 8 }}>
                  <Button size="small" onClick={load}>
                    刷新
                  </Button>
                  <Button size="small" onClick={() => router.push("/settings")}
                    type="default"
                  >
                    打开 Settings
                  </Button>
                </Space>
              </SectionCard>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col span={12}>
              <StrategyListPanel
                strategies={strategies}
                selectedId={selected?.strategy_id}
                onSelect={(s) => setSelected(s)}
              />
            </Col>
            <Col span={12}>
              <BacktestConfigPanel strategy={selected} loading={running} onRun={onRun} />
            </Col>
          </Row>

          <div style={{ marginTop: 16 }}>
            <SectionCard title="Native qlib portfolios">
              <Form
                layout="vertical"
                initialValues={{ weighting_method: "equal", top_n: 5, long_top_n: 30 }}
                onFinish={onBuildPortfolio}
              >
                <Row gutter={12}>
                  <Col span={8}>
                    <Form.Item label="Mining run" name="mining_run_id" rules={[{ required: true, message: "Select a mining run" }]}>
                      <Select
                        showSearch
                        placeholder="Select mining run"
                        options={miningRuns.map((r) => ({ label: r.run_id, value: r.run_id }))}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="Selected factors" name="selected_factors">
                      <Input placeholder="comma separated; empty uses top_n" />
                    </Form.Item>
                  </Col>
                  <Col span={4}>
                    <Form.Item label="Weighting" name="weighting_method">
                      <Select
                        options={[
                          { label: "Equal", value: "equal" },
                          { label: "IC weighted", value: "ic_weighted" },
                          { label: "RankIC weighted", value: "rank_ic_weighted" },
                        ]}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={2}>
                    <Form.Item label="Top N" name="top_n">
                      <InputNumber min={1} max={50} style={{ width: "100%" }} />
                    </Form.Item>
                  </Col>
                  <Col span={2}>
                    <Form.Item label="Hold" name="long_top_n">
                      <InputNumber min={1} max={500} style={{ width: "100%" }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Button type="primary" htmlType="submit" loading={buildingPortfolio}>
                  Build portfolio
                </Button>
              </Form>
              <div style={{ marginTop: 16 }}>
                <Table
                  size="small"
                  rowKey={(r) => r.portfolio_id}
                  dataSource={portfolios}
                  columns={portfolioColumns}
                  pagination={{ pageSize: 5 }}
                />
              </div>
            </SectionCard>
          </div>

          <div style={{ marginTop: 16 }}>
            <SectionCard title="回测">
              {lastRun ? (
                <Row gutter={[16, 16]}>
                  <Col span={8}>
                    <MetricCard title="Backtest ID" value={lastRun.backtest_id} />
                  </Col>
                  <Col span={8}>
                    <MetricCard title="Created" value={lastRun.created_at} />
                  </Col>
                  <Col span={8}>
                    <MetricCard
                      title="查看净值"
                      value="Open"
                      onClick={() => router.push(`/backtests/${encodeURIComponent(lastRun.backtest_id)}`)}
                    />
                  </Col>
                </Row>
              ) : (
                <Typography.Text type="secondary">尚未运行回测。</Typography.Text>
              )}

              <div style={{ marginTop: 16 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                  <Typography.Text strong>最近回测</Typography.Text>
                  <Tag color="blue">{backtests.length}</Tag>
                </div>
                <Table
                  size="small"
                  rowKey={(r) => r.backtest_id}
                  dataSource={backtests}
                  columns={backtestColumns}
                  pagination={{ pageSize: 5 }}
                  onRow={(record) => ({
                    onClick: () => router.push(`/backtests/${encodeURIComponent(record.backtest_id)}`),
                  })}
                />
              </div>
            </SectionCard>
          </div>
        </>
      )}
    </PageContainer>
  );
}
