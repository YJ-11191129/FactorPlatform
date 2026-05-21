"use client";

import { Alert, Button, Col, Form, Input, InputNumber, Row, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { CopyableCodeBlock } from "@/components/common/CopyableCodeBlock";
import { MetricCard } from "@/components/common/MetricCard";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
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
  if (!e || typeof e !== "object") return "Request failed";
  if ("message" in e && typeof (e as any).message === "string") return (e as any).message;
  return "Request failed";
}

export default function AiStrategyBuilderPage() {
  const router = useRouter();
  const [form] = Form.useForm();
  const [providerStatus, setProviderStatus] = useState<LLMProviderStatus | null>(null);
  const [generated, setGenerated] = useState<GenerateStrategyResult | null>(null);
  const [validation, setValidation] = useState<StrategyValidationResult | null>(null);
  const [editableSpec, setEditableSpec] = useState<string>("");
  const [generating, setGenerating] = useState(false);
  const [validating, setValidating] = useState(false);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    getStrategyAiProviders()
      .then(setProviderStatus)
      .catch(() => setProviderStatus(null));
  }, []);

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

  const issueColumns: ColumnsType<StrategyValidationIssue> = [
    {
      title: "Severity",
      dataIndex: "severity",
      key: "severity",
      width: 110,
      render: (v: string) => <Tag color={v === "error" ? "red" : "gold"}>{v}</Tag>,
    },
    { title: "Code", dataIndex: "code", key: "code", width: 180 },
    { title: "Field", dataIndex: "field", key: "field", width: 180, render: (v) => v || "-" },
    { title: "Message", dataIndex: "message", key: "message" },
  ];

  async function onGenerate(values: any) {
    setGenerating(true);
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
      message.success(res.used_fallback ? "Generated fallback StrategySpec" : "Generated StrategySpec");
    } catch (e) {
      message.error(extractErrorMessage(e));
    } finally {
      setGenerating(false);
    }
  }

  async function onValidate() {
    setValidating(true);
    try {
      const spec = JSON.parse(editableSpec) as StrategySpec;
      const res = await validateStrategySpec(spec);
      setValidation(res);
      setEditableSpec(JSON.stringify(res.normalized_spec, null, 2));
      message.success(res.is_valid ? "StrategySpec is valid" : "Validation found issues");
    } catch (e) {
      message.error(e instanceof SyntaxError ? "StrategySpec JSON is invalid" : extractErrorMessage(e));
    } finally {
      setValidating(false);
    }
  }

  async function onRunBacktest() {
    setRunning(true);
    try {
      const values = form.getFieldsValue();
      const spec = JSON.parse(editableSpec) as StrategySpec;
      const res = await runAiBacktest({
        spec,
        start_date: values.start_date || null,
        end_date: values.end_date || null,
        universe: splitUniverse(values.universe),
        initial_cash: Number(values.initial_cash || 1_000_000),
        fee_bps: Number(values.fee_bps ?? spec.execution?.fee_bps ?? 5),
        use_adj: true,
        run_validation: true,
      });
      setLastRun(res.summary);
      setValidation(res.validation);
      message.success({
        content: (
          <Space>
            <span>AI strategy backtest completed</span>
            <Button size="small" type="link" onClick={() => router.push(`/backtests/${encodeURIComponent(res.backtest_id)}`)}>
              Open result
            </Button>
          </Space>
        ),
      });
    } catch (e) {
      message.error(e instanceof SyntaxError ? "StrategySpec JSON is invalid" : extractErrorMessage(e));
    } finally {
      setRunning(false);
    }
  }

  const metrics = (lastRun?.metrics || {}) as Record<string, unknown>;

  return (
    <PageContainer
      title="AI Strategy Builder"
      subtitle="Generate a structured StrategySpec, validate timing assumptions, and run a controlled backtest."
    >
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <SectionCard title="Research Request">
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                provider: "deepseek",
                market: "equity",
                risk_profile: "balanced",
                initial_cash: 1_000_000,
                fee_bps: 5,
                prompt: "Create a volatility-aware trend strategy with explicit risk controls. Use daily bars and avoid look-ahead bias.",
              }}
              onFinish={onGenerate}
            >
              <Form.Item label="Model" name="provider">
                <Select options={providerOptions} />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Market" name="market">
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
                  <Form.Item label="Risk profile" name="risk_profile">
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
              <Form.Item label="Universe" name="universe">
                <Input placeholder="AAPL, MSFT or 000001.SZ, 000002.SZ" />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Start date" name="start_date">
                    <Input placeholder="2020-01-01" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="End date" name="end_date">
                    <Input placeholder="2024-12-31" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Initial cash" name="initial_cash">
                    <InputNumber min={1000} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Fee bps" name="fee_bps">
                    <InputNumber min={0} max={200} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="Strategy requirement" name="prompt" rules={[{ required: true, message: "Describe the strategy you want." }]}>
                <Input.TextArea rows={8} />
              </Form.Item>
              <Space wrap>
                <Button type="primary" htmlType="submit" loading={generating}>
                  Generate StrategySpec
                </Button>
                <Button onClick={() => router.push("/strategies")}>Backtest Lab</Button>
              </Space>
            </Form>
          </SectionCard>

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
        </Col>

        <Col xs={24} xl={14}>
          <SectionCard
            title="StrategySpec"
            extra={
              <Space>
                <Button disabled={!editableSpec} loading={validating} onClick={onValidate}>
                  Validate
                </Button>
                <Button type="primary" disabled={!editableSpec || validation?.is_valid === false} loading={running} onClick={onRunBacktest}>
                  Run Backtest
                </Button>
              </Space>
            }
          >
            {generated ? (
              <Space style={{ marginBottom: 12 }} wrap>
                <Tag color={generated.llm_ready ? "green" : "gold"}>{generated.llm_ready ? "LLM ready" : "Fallback"}</Tag>
                <Tag>{generated.provider}</Tag>
                <Tag color={validation?.is_valid ? "blue" : "red"}>{validation?.is_valid ? "valid" : "needs review"}</Tag>
              </Space>
            ) : null}
            <Input.TextArea
              value={editableSpec}
              onChange={(e) => setEditableSpec(e.target.value)}
              placeholder="Generate a StrategySpec to review and edit it here."
              rows={18}
              style={{ fontFamily: "var(--font-mono, Consolas, monospace)" }}
            />
            {editableSpec ? <div style={{ marginTop: 12 }}><CopyableCodeBlock code={editableSpec} /></div> : null}
          </SectionCard>

          <div style={{ marginTop: 16 }}>
            <SectionCard title="Validation">
              {validation ? (
                <>
                  <Alert
                    type={validation.is_valid ? "success" : "error"}
                    showIcon
                    message={validation.is_valid ? "StrategySpec is executable by the controlled backtest engine." : "StrategySpec has blocking issues."}
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
                    Timing: {validation.timing_assumptions.join(" ")}
                  </Typography.Paragraph>
                </>
              ) : (
                <Typography.Text type="secondary">Generate or paste a StrategySpec, then run validation.</Typography.Text>
              )}
            </SectionCard>
          </div>

          {lastRun ? (
            <div style={{ marginTop: 16 }}>
              <SectionCard title="Latest AI Backtest">
                <Row gutter={[16, 16]}>
                  <Col xs={12} lg={6}>
                    <MetricCard title="Total return" value={formatPercent(metrics.total_return)} />
                  </Col>
                  <Col xs={12} lg={6}>
                    <MetricCard title="Annual return" value={formatPercent(metrics.annual_return)} />
                  </Col>
                  <Col xs={12} lg={6}>
                    <MetricCard title="Sharpe" value={typeof metrics.sharpe === "number" ? metrics.sharpe.toFixed(2) : "-"} />
                  </Col>
                  <Col xs={12} lg={6}>
                    <MetricCard title="Max drawdown" value={formatPercent(metrics.max_drawdown)} />
                  </Col>
                </Row>
                <Space style={{ marginTop: 12 }}>
                  <Typography.Text code>{String(lastRun.backtest_id || "")}</Typography.Text>
                  <Button size="small" onClick={() => router.push(`/backtests/${encodeURIComponent(String(lastRun.backtest_id || ""))}`)}>
                    Open result
                  </Button>
                  <Button size="small" type="primary" onClick={() => router.push(`/backtests/${encodeURIComponent(String(lastRun.backtest_id || ""))}`)}>
                    Continue analysis
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
