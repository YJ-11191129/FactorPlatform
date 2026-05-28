"use client";

import { Alert, Button, Col, Form, Input, InputNumber, Row, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { CopyableCodeBlock } from "@/components/common/CopyableCodeBlock";
import { MetricCard } from "@/components/common/MetricCard";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { RiskMeter, SignalGauge } from "@/components/visual/ResearchVisuals";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { generateStrategySpec, getStrategyAiProviders, runAiBacktest, validateStrategySpec } from "@/lib/api/strategy-ai";
import type { GenerateStrategyResult, LLMProviderStatus, StrategySpec, StrategyValidationIssue, StrategyValidationResult } from "@/types/strategy-ai";

function splitUniverse(raw: string | undefined): string[] {
  return String(raw || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

function formatPercent(value: unknown): string {
  return typeof value === "number" ? `${(value * 100).toFixed(2)}%` : "-";
}

function extractErrorMessage(e: unknown): string {
  const message = !e || typeof e !== "object" ? "Request failed" : "message" in e && typeof (e as any).message === "string" ? (e as any).message : "Request failed";
  if (/fresh|stale|only has data through|数据|新鲜度/i.test(message)) {
    return "回测所需行情数据暂未满足新鲜度要求，可先刷新数据，或指定较早结束日期后重试。";
  }
  return message;
}

function dataHealthWarning(dataHealth: Record<string, unknown> | null | undefined): string | null {
  if (!dataHealth || dataHealth.blocking_status !== "WARN") return null;
  return typeof dataHealth.message === "string" && dataHealth.message
    ? dataHealth.message
    : "回测数据存在新鲜度提示，结果已按可用数据区间生成。";
}

function qlibRegion(value: string | undefined): string | null {
  if (value === "qlib_cn") return "cn";
  if (value === "qlib_us") return "us";
  return null;
}

function safeParseSpec(raw: string): StrategySpec | null {
  if (!raw.trim()) return null;
  try {
    return JSON.parse(raw) as StrategySpec;
  } catch {
    return null;
  }
}

function riskTone(profile?: string): "positive" | "warning" | "negative" {
  if (profile === "conservative") return "positive";
  if (profile === "aggressive_research") return "warning";
  return "positive";
}

function directionLabel(value?: string) {
  const normalized = String(value || "").toLowerCase();
  if (normalized.includes("short")) return "偏空研究";
  if (normalized.includes("long")) return "偏多研究";
  if (normalized.includes("market")) return "市场中性";
  return "多因子观察";
}

const defaultFormValues = {
  provider: "deepseek",
  market: "equity",
  data_source: "qlib_auto",
  risk_profile: "balanced",
  initial_cash: 1_000_000,
  fee_bps: 5,
  prompt: "Create a volatility-aware trend strategy with explicit risk controls. Use daily bars and avoid look-ahead bias.",
};

function buildStockPickingPrompt(params: { symbol?: string; name?: string; sector?: string; universe: string }) {
  const target = [params.name, params.symbol ? `(${params.symbol})` : ""].filter(Boolean).join(" ");
  const targetLine = target
    ? `请围绕该标的 ${target}${params.sector ? `（行业：${params.sector}）` : ""} 生成可回测策略，同时保留与股票池的横截面比较。`
    : "请面向 A 股股票池生成一个可回测的多因子选股策略。";

  return [
    "生成一个用于辅助研究与风险识别的多因子选股策略，不构成投资建议。",
    targetLine,
    `股票池：${params.universe}；数据源优先使用 qlib CN daily；市场：equity。`,
    "因子方向包括质量、动量、波动率、估值与流动性筛选，要求给出入场条件、退出条件、排序逻辑、仓位上限、止损纪律和风险提示。",
    "请避免未来函数和不可交易假设，输出可被系统校验与回测的结构化方案。",
  ].join("\n");
}

function readUrlDefaults(params: Pick<URLSearchParams, "get">) {
  if (params.get("intent") !== "stock-picking") return null;

  const symbol = params.get("symbol")?.trim() || "";
  const name = params.get("name")?.trim() || "";
  const sector = params.get("sector")?.trim() || "";
  const universe = symbol || "csi300";

  return {
    market: params.get("market")?.trim() || "equity",
    data_source: "qlib_cn",
    risk_profile: "balanced",
    universe,
    prompt: buildStockPickingPrompt({ symbol, name, sector, universe }),
  };
}

export default function AiStrategyBuilderPage() {
  const router = useRouter();
  const [advancedMode] = useAdvancedMode();
  const [form] = Form.useForm();
  const initializedSearchRef = useRef("");
  const [providerStatus, setProviderStatus] = useState<LLMProviderStatus | null>(null);
  const [generated, setGenerated] = useState<GenerateStrategyResult | null>(null);
  const [validation, setValidation] = useState<StrategyValidationResult | null>(null);
  const [editableSpec, setEditableSpec] = useState<string>("");
  const [generating, setGenerating] = useState(false);
  const [validating, setValidating] = useState(false);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<Record<string, any> | null>(null);
  const [backtestErrorMsg, setBacktestErrorMsg] = useState("");

  useEffect(() => {
    getStrategyAiProviders()
      .then(setProviderStatus)
      .catch(() => setProviderStatus(null));
  }, []);

  useEffect(() => {
    const searchKey = typeof window === "undefined" ? "" : window.location.search;
    if (initializedSearchRef.current === searchKey) return;
    const urlDefaults = readUrlDefaults(new URLSearchParams(searchKey));
    if (!urlDefaults) return;
    initializedSearchRef.current = searchKey;
    form.setFieldsValue(urlDefaults);
  });

  const providerOptions = useMemo(() => {
    const base = providerStatus?.providers || [];
    if (!base.length) {
      return [
        { label: "DeepSeek", value: "deepseek" },
        { label: "Local", value: "local" },
      ];
    }
    return base.map((p) => ({
      label: `${p.name} · ${p.model}${p.ready ? "" : " · not ready"}`,
      value: p.name,
    }));
  }, [providerStatus]);

  const issueColumns: ColumnsType<StrategyValidationIssue> = useMemo(() => [
    {
      title: "级别",
      dataIndex: "severity",
      key: "severity",
      width: 110,
      render: (v: string) => <Tag color={v === "error" ? "red" : "gold"}>{v === "error" ? "阻断" : "提示"}</Tag>,
    },
    ...(advancedMode ? [
      { title: "编号", dataIndex: "code", key: "code", width: 180 },
      { title: "字段", dataIndex: "field", key: "field", width: 180, render: (v: string | null) => v || "-" },
    ] as ColumnsType<StrategyValidationIssue> : []),
    { title: "说明", dataIndex: "message", key: "message" },
  ], [advancedMode]);

  async function onGenerate(values: any) {
    setGenerating(true);
    setBacktestErrorMsg("");
    try {
      const res = await generateStrategySpec({
        prompt: values.prompt,
        provider: values.provider,
        market: values.market,
        universe: splitUniverse(values.universe),
        timeframe: "1d",
        risk_profile: values.risk_profile || "balanced",
        language: "zh",
      });
      setGenerated(res);
      setValidation(res.validation);
      setEditableSpec(JSON.stringify(res.spec, null, 2));
      message.success(res.used_fallback ? "已生成模板策略" : "已生成策略结构");
    } catch (e) {
      message.error(extractErrorMessage(e));
    } finally {
      setGenerating(false);
    }
  }

  async function onValidate() {
    setValidating(true);
    setBacktestErrorMsg("");
    try {
      const spec = JSON.parse(editableSpec) as StrategySpec;
      const res = await validateStrategySpec(spec);
      setValidation(res);
      setEditableSpec(JSON.stringify(res.normalized_spec, null, 2));
      message.success(res.is_valid ? "策略结构可回测" : "策略结构存在需要检查的问题");
    } catch (e) {
      message.error(e instanceof SyntaxError ? "策略结构 JSON 格式不正确" : extractErrorMessage(e));
    } finally {
      setValidating(false);
    }
  }

  async function onRunBacktest() {
    setRunning(true);
    setBacktestErrorMsg("");
    try {
      const values = form.getFieldsValue();
      const spec = JSON.parse(editableSpec) as StrategySpec;
      const res = await runAiBacktest({
        spec,
        start_date: values.start_date || null,
        end_date: values.end_date || null,
        universe: splitUniverse(values.universe),
        data_source: values.data_source === "wind_parquet" ? "parquet" : "qlib",
        qlib_region: qlibRegion(values.data_source),
        initial_cash: Number(values.initial_cash || 1_000_000),
        fee_bps: Number(values.fee_bps ?? spec.execution?.fee_bps ?? 5),
        use_adj: true,
        run_validation: true,
      });
      setLastRun({ backtest_id: res.backtest_id, created_at: res.created_at, ...res.summary, data_health: res.data_health || res.summary.data_health });
      setValidation(res.validation);
      message.success({
        content: (
          <Space>
            <span>AI 策略回测完成</span>
            <Button size="small" type="link" onClick={() => router.push(`/backtests/${encodeURIComponent(res.backtest_id)}`)}>
              查看结果
            </Button>
            <Button size="small" type="link" onClick={() => router.push("/dashboard")}>
              返回看板
            </Button>
          </Space>
        ),
      });
      const warning = dataHealthWarning(res.data_health || (res.summary.data_health as Record<string, unknown> | null | undefined));
      if (warning) message.warning(warning, 6);
    } catch (e) {
      const msg = e instanceof SyntaxError ? "策略结构 JSON 格式不正确" : extractErrorMessage(e);
      setBacktestErrorMsg(msg);
      message.error(msg);
    } finally {
      setRunning(false);
    }
  }

  const metrics = (lastRun?.metrics || {}) as Record<string, unknown>;
  const latestDataHealthWarning = dataHealthWarning(lastRun?.data_health as Record<string, unknown> | null | undefined);
  const latestBacktestId = String(lastRun?.backtest_id || "");
  const parsedSpec = useMemo(() => safeParseSpec(editableSpec), [editableSpec]);
  const riskProfile = String(form.getFieldValue("risk_profile") || "balanced");
  const strategyReadiness = validation?.is_valid ? 88 : parsedSpec ? 62 : 18;
  const indicatorRows = (parsedSpec?.indicators || []).map((indicator, index) => ({
    key: `${indicator.name || indicator.type}-${index}`,
    name: indicator.name || indicator.type,
    type: indicator.type,
    window: indicator.window || indicator.fast_window || indicator.slow_window || "-",
  }));

  return (
    <PageContainer
      title="AI 策略生成器"
      subtitle="将研究需求转成可校验、可回测的策略结构，并保留风险与时序约束。"
    >
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <SectionCard title="研究需求">
            <Form
              form={form}
              layout="vertical"
              initialValues={defaultFormValues}
              onFinish={onGenerate}
            >
              <Form.Item label={advancedMode ? "Model" : "分析引擎"} name="provider">
                <Select options={providerOptions} />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="市场" name="market">
                    <Select
                      options={[
                        { label: "Equity", value: "equity" },
                        { label: "Futures", value: "futures" },
                        { label: "FX", value: "fx" },
                        { label: "Crypto", value: "crypto" },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="风险偏好" name="risk_profile">
                    <Select
                      options={[
                        { label: "Conservative", value: "conservative" },
                        { label: "Balanced", value: "balanced" },
                        { label: "Aggressive research", value: "aggressive_research" },
                      ]}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="回测数据" name="data_source">
                <Select
                  options={[
                    { label: "Auto qlib (CN/US)", value: "qlib_auto" },
                    { label: "CN qlib", value: "qlib_cn" },
                    { label: "US qlib", value: "qlib_us" },
                    { label: "Wind parquet fallback", value: "wind_parquet" },
                  ]}
                />
              </Form.Item>
              <Form.Item label="股票池" name="universe">
                <Input placeholder="AAPL, MSFT or 000001.SZ, 000002.SZ" />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="开始日期" name="start_date">
                    <Input placeholder="2020-01-01" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="结束日期" name="end_date">
                    <Input placeholder="2024-12-31" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="初始资金" name="initial_cash">
                    <InputNumber min={1000} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="交易成本 bps" name="fee_bps">
                    <InputNumber min={0} max={200} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="策略需求" name="prompt" rules={[{ required: true, message: "请描述希望生成的策略。" }]}>
                <Input.TextArea rows={8} />
              </Form.Item>
              <Space wrap>
                <Button type="primary" htmlType="submit" loading={generating}>
                  生成策略
                </Button>
                <Button onClick={() => router.push("/strategies")}>回测工作台</Button>
              </Space>
            </Form>
          </SectionCard>

          {advancedMode ? (
            <div style={{ marginTop: 16 }}>
              <SectionCard title="Provider Status">
                <Space orientation="vertical" style={{ width: "100%" }}>
                  {(providerStatus?.providers || []).map((p) => (
                    <Alert
                      key={p.name}
                      type={p.ready ? "success" : "warning"}
                      showIcon
                      message={`${p.name} · ${p.model}`}
                      description={p.ready ? p.endpoint : p.reason || "not ready"}
                    />
                  ))}
                  {!providerStatus ? <Typography.Text type="secondary">Provider status is unavailable.</Typography.Text> : null}
                </Space>
              </SectionCard>
            </div>
          ) : null}
        </Col>

        <Col xs={24} xl={14}>
          <SectionCard
            title={advancedMode ? "StrategySpec" : "策略方案"}
            extra={
              <Space>
                <Button disabled={!editableSpec} loading={validating} onClick={onValidate}>
                  校验
                </Button>
                <Button type="primary" disabled={!editableSpec || validation?.is_valid === false} loading={running} onClick={onRunBacktest}>
                  运行回测
                </Button>
              </Space>
            }
          >
            {generated ? (
              <Space style={{ marginBottom: 12 }} wrap>
                <Tag color={generated.llm_ready ? "green" : "gold"}>{generated.llm_ready ? "AI 引擎" : "模板兜底"}</Tag>
                {advancedMode ? <Tag>{generated.provider}</Tag> : null}
                <Tag color={validation?.is_valid ? "blue" : "red"}>{validation?.is_valid ? "可回测" : "需检查"}</Tag>
              </Space>
            ) : null}
            {backtestErrorMsg ? (
              <Alert
                type="warning"
                showIcon
                message="回测暂未启动"
                description={backtestErrorMsg}
                action={
                  <Space wrap>
                    {advancedMode ? <Button size="small" onClick={() => router.push("/data-maintenance")}>刷新数据</Button> : null}
                    <Button size="small" onClick={() => router.push("/dashboard")}>返回看板</Button>
                  </Space>
                }
                style={{ marginBottom: 12 }}
              />
            ) : null}
            {advancedMode ? (
              <>
                <Input.TextArea
                  value={editableSpec}
                  onChange={(e) => setEditableSpec(e.target.value)}
                  placeholder="生成策略后，可在这里查看和编辑结构化策略。"
                  rows={18}
                  style={{ fontFamily: "var(--font-mono, Consolas, monospace)" }}
                />
                {editableSpec ? <div style={{ marginTop: 12 }}><CopyableCodeBlock code={editableSpec} /></div> : null}
              </>
            ) : parsedSpec ? (
              <Space direction="vertical" size={14} style={{ width: "100%" }}>
                <Row gutter={[12, 12]}>
                  <Col xs={24} md={8}>
                    <SignalGauge
                      label={validation?.is_valid ? "可回测" : "待校验"}
                      value={strategyReadiness}
                      tone={validation?.is_valid ? "positive" : "warning"}
                      caption="策略结构、时序和风险约束状态"
                    />
                  </Col>
                  <Col xs={24} md={16}>
                    <div style={{ display: "grid", gap: 10 }}>
                      <Typography.Title level={4} style={{ margin: 0 }}>{parsedSpec.name}</Typography.Title>
                      <Typography.Paragraph style={{ marginBottom: 0 }}>{parsedSpec.description}</Typography.Paragraph>
                      <Space wrap>
                        <Tag color="blue">{directionLabel(parsedSpec.direction)}</Tag>
                        <Tag>{parsedSpec.timeframe}</Tag>
                        <Tag>{parsedSpec.asset_class}</Tag>
                        <Tag>{parsedSpec.universe.slice(0, 4).join(", ")}{parsedSpec.universe.length > 4 ? " ..." : ""}</Tag>
                      </Space>
                    </div>
                  </Col>
                </Row>
                <Row gutter={[12, 12]}>
                  <Col xs={24} lg={8}>
                    <RiskMeter
                      label="单标的仓位上限"
                      value={(parsedSpec.risk.max_position_pct || 0) * 100}
                      status={`${Math.round((parsedSpec.risk.max_position_pct || 0) * 100)}%`}
                      tone={riskTone(riskProfile)}
                    />
                  </Col>
                  <Col xs={24} lg={8}>
                    <RiskMeter
                      label="最多持仓数量"
                      value={Math.min(100, (parsedSpec.risk.max_positions || 0) * 12)}
                      status={`${parsedSpec.risk.max_positions || "-"} 个`}
                      tone="positive"
                    />
                  </Col>
                  <Col xs={24} lg={8}>
                    <RiskMeter
                      label="止损纪律"
                      value={parsedSpec.risk.stop_loss ? 86 : 34}
                      status={parsedSpec.risk.stop_loss ? "已配置" : "需补充"}
                      tone={parsedSpec.risk.stop_loss ? "positive" : "warning"}
                    />
                  </Col>
                </Row>
                <Table
                  size="small"
                  rowKey="key"
                  dataSource={indicatorRows}
                  pagination={false}
                  columns={[
                    { title: "因子/指标", dataIndex: "name" },
                    { title: "类型", dataIndex: "type", width: 140 },
                    { title: "窗口", dataIndex: "window", width: 90 },
                  ]}
                />
                <Row gutter={[12, 12]}>
                  <Col xs={24} lg={12}>
                    <Alert
                      type="success"
                      showIcon
                      message="入场条件"
                      description={(parsedSpec.entry_rules || []).slice(0, 3).join("；") || "等待策略生成"}
                    />
                  </Col>
                  <Col xs={24} lg={12}>
                    <Alert
                      type="warning"
                      showIcon
                      message="退出与风险"
                      description={[...(parsedSpec.exit_rules || []).slice(0, 2), ...(parsedSpec.risk.notes || []).slice(0, 1)].join("；") || "等待策略生成"}
                    />
                  </Col>
                </Row>
              </Space>
            ) : (
              <Alert
                type="info"
                showIcon
                message="等待生成策略方案"
                description="从左侧输入研究需求后，这里会展示策略摘要、因子逻辑、风险约束和回测入口。"
              />
            )}
          </SectionCard>

          <div style={{ marginTop: 16 }}>
            <SectionCard title="策略校验">
              {validation ? (
                <>
                  <Alert
                    type={validation.is_valid ? "success" : "error"}
                    showIcon
                    message={validation.is_valid ? "策略结构可进入受控回测。" : "策略结构存在阻断项。"}
                    description={validation.disclaimer}
                    style={{ marginBottom: 12 }}
                  />
                  <Table
                    size="small"
                    rowKey={(r, index) => `${r.code}-${r.field || "root"}-${index}`}
                    dataSource={validation.issues}
                    columns={issueColumns}
                    pagination={false}
                  />
                  <Typography.Paragraph style={{ marginTop: 12, marginBottom: 0 }} type="secondary">
                    时序假设：{validation.timing_assumptions.join(" ")}
                  </Typography.Paragraph>
                </>
              ) : (
                <Typography.Text type="secondary">生成或粘贴策略结构后，可先进行校验。</Typography.Text>
              )}
            </SectionCard>
          </div>

          {lastRun ? (
            <div style={{ marginTop: 16 }}>
              <SectionCard title="最近一次 AI 回测">
                {latestDataHealthWarning ? (
                  <Alert
                    type="warning"
                    showIcon
                    message="数据区间提示"
                    description={latestDataHealthWarning}
                    style={{ marginBottom: 12 }}
                  />
                ) : null}
                <Row gutter={[16, 16]}>
                  <Col xs={12} lg={6}>
                    <MetricCard title="总收益" value={formatPercent(metrics.total_return)} />
                  </Col>
                  <Col xs={12} lg={6}>
                    <MetricCard title="年化收益" value={formatPercent(metrics.annual_return)} />
                  </Col>
                  <Col xs={12} lg={6}>
                    <MetricCard title="Sharpe" value={typeof metrics.sharpe === "number" ? metrics.sharpe.toFixed(2) : "-"} />
                  </Col>
                  <Col xs={12} lg={6}>
                    <MetricCard title="最大回撤" value={formatPercent(metrics.max_drawdown)} />
                  </Col>
                </Row>
                <Space style={{ marginTop: 12 }}>
                  {advancedMode ? <Typography.Text code>{latestBacktestId}</Typography.Text> : null}
                  <Button size="small" disabled={!latestBacktestId} onClick={() => router.push(`/backtests/${encodeURIComponent(latestBacktestId)}`)}>
                    查看结果
                  </Button>
                  <Button size="small" type="primary" onClick={() => router.push("/dashboard")}>
                    返回看板
                  </Button>
                </Space>
              </SectionCard>
            </div>
          ) : null}
        </Col>
      </Row>
    </PageContainer>
  );
}
