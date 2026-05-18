"use client";

import { Alert, Button, DatePicker, Drawer, Form, Input, InputNumber, Modal, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { FactorFilterBar, type FactorFilters } from "@/components/factor/FactorFilterBar";
import { FactorRunModal, type RunMode } from "@/components/factor/FactorRunModal";
import { FactorTable } from "@/components/factor/FactorTable";
import { listFactors, runDemo, runQlib } from "@/lib/api/factors";
import { generateQlibReport, getQlibStatus, listQlibFactorMiningRuns, runQlibFactorMining } from "@/lib/api/qlib-research";
import { evaluateResearchQuality, getResearchQualityRun } from "@/lib/api/research-quality";
import type { FactorItem } from "@/types/factor";
import type { QlibFactorMiningRun, QlibStatus, ResearchQualityCheck, ResearchQualityReport } from "@/types/qlib-research";

type LoadState = "loading" | "error" | "ready";

function qualityColor(status?: string | null): string {
  if (status === "PASS") return "green";
  if (status === "FAIL") return "red";
  if (status === "WARN") return "gold";
  return "default";
}

function explainApiError(e: any): string {
  const detail = e?.detail?.detail;
  if (detail && typeof detail === "object") {
    return detail.message || detail.status || e?.message || "Request failed";
  }
  return e?.message || "Request failed";
}

export default function FactorsPage() {
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<FactorItem[]>([]);
  const [filters, setFilters] = useState<FactorFilters>({});
  const [runOpen, setRunOpen] = useState(false);
  const [runMode, setRunMode] = useState<RunMode>("demo");
  const [runFactor, setRunFactor] = useState("");
  const [runLoading, setRunLoading] = useState(false);
  const [qlibStatus, setQlibStatus] = useState<QlibStatus | null>(null);
  const [miningRuns, setMiningRuns] = useState<QlibFactorMiningRun[]>([]);
  const [miningOpen, setMiningOpen] = useState(false);
  const [miningLoading, setMiningLoading] = useState(false);
  const [reportLoadingId, setReportLoadingId] = useState<string | null>(null);
  const [qualityOpen, setQualityOpen] = useState(false);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [qualityRunId, setQualityRunId] = useState("");
  const [qualityReport, setQualityReport] = useState<ResearchQualityReport | null>(null);
  const [qualityError, setQualityError] = useState("");

  async function load() {
    setState("loading");
    try {
      const [res, status, runs] = await Promise.all([
        listFactors(),
        getQlibStatus().catch(() => null),
        listQlibFactorMiningRuns(20).catch(() => []),
      ]);
      setData(res);
      setQlibStatus(status);
      setMiningRuns(runs);
      setState("ready");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const categories = useMemo(() => Array.from(new Set(data.map((d) => d.category))).sort(), [data]);

  const filtered = useMemo(() => {
    return data.filter((d) => {
      const q = (filters.q || "").trim().toLowerCase();
      if (q) {
        const hit = d.factor_name.toLowerCase().includes(q) || (d.display_name || "").toLowerCase().includes(q);
        if (!hit) return false;
      }
      if (filters.category && d.category !== filters.category) return false;
      if (filters.status && d.status !== filters.status) return false;
      return true;
    });
  }, [data, filters]);

  async function submitRun(values: { n: number; universe: string; instrument_limit: number; save: boolean }) {
    setRunLoading(true);
    try {
      if (runMode === "demo") {
        const res = await runDemo({ factor_name: runFactor, params: { n: values.n }, save: values.save });
        message.success(res.calc_batch_id ? `Saved: ${res.calc_batch_id}` : "Run submitted");
      } else {
        const res = await runQlib({
          factor_name: runFactor,
          params: { n: values.n },
          provider_uri: "D:\\mcQlib\\data\\qlib_bin\\cn_data",
          universe: values.universe,
          instrument_limit: values.instrument_limit,
          save: values.save,
        });
        message.success(res.calc_batch_id ? `Saved: ${res.calc_batch_id}` : "Run submitted");
      }
      setRunOpen(false);
    } catch (e: any) {
      message.error(explainApiError(e));
    } finally {
      setRunLoading(false);
    }
  }

  async function submitMining(values: any) {
    setMiningLoading(true);
    try {
      const res = await runQlibFactorMining({
        provider_uri: values.provider_uri || null,
        universe: values.universe || "csi300",
        start_date: values.start_date ? dayjs(values.start_date).format("YYYY-MM-DD") : null,
        end_date: values.end_date ? dayjs(values.end_date).format("YYYY-MM-DD") : null,
        horizon: Number(values.horizon || 1),
        quantiles: Number(values.quantiles || 5),
        top_k: Number(values.top_k || 20),
        freq: "day",
        factor_limit: values.factor_limit ? Number(values.factor_limit) : null,
      });
      message.success(`Mining run created: ${res.run_id}`);
      setMiningOpen(false);
      setMiningRuns(await listQlibFactorMiningRuns(20));
    } catch (e: any) {
      message.error(explainApiError(e));
    } finally {
      setMiningLoading(false);
    }
  }

  async function generateMiningReport(runId: string) {
    setReportLoadingId(runId);
    try {
      const res = await generateQlibReport({ report_type: "qlib_factor_mining", run_id: runId });
      message.success(`Report generated: ${String(res.html_path || "")}`);
    } catch (e: any) {
      message.error(explainApiError(e));
    } finally {
      setReportLoadingId(null);
    }
  }

  async function openQuality(runId: string) {
    setQualityRunId(runId);
    setQualityOpen(true);
    setQualityReport(null);
    setQualityError("");
    setQualityLoading(true);
    try {
      setQualityReport(await getResearchQualityRun(runId));
    } catch (e: any) {
      setQualityError(explainApiError(e));
    } finally {
      setQualityLoading(false);
    }
  }

  async function runQualityEvaluation(runId: string) {
    setQualityLoading(true);
    setQualityError("");
    try {
      const report = await evaluateResearchQuality({ source_run_id: runId });
      setQualityReport(report);
      setMiningRuns(await listQlibFactorMiningRuns(20));
      message.success(`Quality ${report.quality_status}: ${runId}`);
    } catch (e: any) {
      setQualityError(explainApiError(e));
      message.error(explainApiError(e));
    } finally {
      setQualityLoading(false);
    }
  }

  const miningColumns: ColumnsType<QlibFactorMiningRun> = [
    {
      title: "Run",
      dataIndex: "run_id",
      key: "run_id",
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (v: string) => <Tag color={v === "SUCCESS" ? "green" : "orange"}>{v}</Tag>,
    },
    {
      title: "Quality",
      key: "quality",
      width: 120,
      render: (_, r) => <Tag color={qualityColor(r.quality_gate?.quality_status)}>{r.quality_gate?.quality_status || "NO_REPORT"}</Tag>,
    },
    {
      title: "Promotion",
      key: "promotion_status",
      width: 150,
      render: (_, r) => <Tag color={r.promotion_status === "PRODUCTION_CANDIDATE" ? "green" : "blue"}>{r.promotion_status || "NOT_EVALUATED"}</Tag>,
    },
    {
      title: "Reason codes",
      key: "reason_codes",
      render: (_, r) => (
        <Space wrap size={4}>
          {(r.quality_reason_codes || r.quality_gate?.reason_codes || []).slice(0, 3).map((code) => (
            <Tag key={code}>{code}</Tag>
          ))}
          {(r.quality_reason_codes || r.quality_gate?.reason_codes || []).length > 3 ? <Tag>more</Tag> : null}
        </Space>
      ),
    },
    {
      title: "Top factor",
      key: "top_factor",
      width: 180,
      render: (_, r) => {
        const top = r.top_factors?.[0];
        return top ? <Typography.Text>{String(top.factor_name || "-")}</Typography.Text> : "-";
      },
    },
    {
      title: "Actions",
      key: "actions",
      width: 190,
      render: (_, r) => (
        <Space>
          <Button size="small" onClick={() => openQuality(r.run_id)}>
            Quality
          </Button>
          <Button size="small" loading={reportLoadingId === r.run_id} onClick={() => generateMiningReport(r.run_id)}>
            HTML
          </Button>
        </Space>
      ),
    },
  ];

  const qualityColumns: ColumnsType<ResearchQualityCheck> = [
    { title: "Check", dataIndex: "check_id", key: "check_id", width: 180 },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (v: string) => <Tag color={qualityColor(v)}>{v}</Tag>,
    },
    { title: "Reason", dataIndex: "reason_code", key: "reason_code", width: 220 },
    { title: "Message", dataIndex: "message", key: "message" },
  ];

  return (
    <PageContainer
      title="Factors"
      subtitle="Manage factors, native qlib mining, and research quality gates"
      extra={
        <Space>
          <Button disabled>New Factor</Button>
          <Button type="primary" onClick={() => setMiningOpen(true)}>
            Batch Mine qlib Factors
          </Button>
        </Space>
      }
    >
      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : state === "error" ? (
        <ErrorState title="Factor list failed to load" onRetry={load} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No factors match the current filters"
          actionText="Clear filters"
          onAction={() => setFilters({})}
          extra={
            <div style={{ marginTop: 8 }}>
              <Button onClick={load}>Refresh</Button>
            </div>
          }
        />
      ) : (
        <>
          <SectionCard
            title="Native qlib readiness"
            extra={<Tag color={qlibStatus?.status === "READY" ? "green" : qlibStatus?.status === "DATA_NOT_READY" ? "gold" : "red"}>{qlibStatus?.status || "UNKNOWN"}</Tag>}
          >
            <Alert
              showIcon
              type={qlibStatus?.status === "READY" ? "success" : qlibStatus?.status === "DATA_NOT_READY" ? "warning" : "error"}
              message="Batch mining uses native qlib only"
              description={
                <div>
                  <div>Provider: {qlibStatus?.provider_uri || "D:\\mcQlib\\data\\qlib_bin\\cn_data"}</div>
                  <div>{qlibStatus?.notes?.[0] || "Native qlib readiness gate is checked before batch mining."}</div>
                </div>
              }
            />
          </SectionCard>

          <SectionCard title="Factor registry" extra={<Tag>{filtered.length} visible</Tag>}>
            <div style={{ marginBottom: 12 }}>
              <FactorFilterBar loading={false} categories={categories} value={filters} onChange={setFilters} onRefresh={load} />
            </div>
            <FactorTable
              loading={false}
              data={filtered}
              onRunDemo={(name) => {
                setRunFactor(name);
                setRunMode("demo");
                setRunOpen(true);
              }}
              onRunQlib={(name) => {
                setRunFactor(name);
                setRunMode("qlib");
                setRunOpen(true);
              }}
            />
          </SectionCard>

          <SectionCard title="Native qlib factor mining runs" extra={<Tag color="blue">{miningRuns.length}</Tag>}>
            <Table size="small" rowKey={(r) => r.run_id} dataSource={miningRuns} columns={miningColumns} pagination={{ pageSize: 5 }} />
          </SectionCard>

          <FactorRunModal open={runOpen} mode={runMode} factorName={runFactor} loading={runLoading} onCancel={() => setRunOpen(false)} onSubmit={submitRun} />

          <Modal title="Batch Mine qlib Factors" open={miningOpen} onCancel={() => setMiningOpen(false)} footer={null} destroyOnClose>
            <Form
              layout="vertical"
              initialValues={{
                provider_uri: qlibStatus?.provider_uri || "D:\\mcQlib\\data\\qlib_bin\\cn_data",
                universe: "csi300",
                horizon: 1,
                quantiles: 5,
                top_k: 20,
                factor_limit: 20,
                start_date: dayjs().add(-180, "day"),
                end_date: dayjs(),
              }}
              onFinish={submitMining}
            >
              <Form.Item label="Provider URI" name="provider_uri">
                <Input />
              </Form.Item>
              <Space style={{ width: "100%" }} align="start">
                <Form.Item label="Universe" name="universe" rules={[{ required: true }]} style={{ flex: 1 }}>
                  <Input />
                </Form.Item>
                <Form.Item label="Factor limit" name="factor_limit" style={{ flex: 1 }}>
                  <InputNumber min={1} max={500} style={{ width: "100%" }} />
                </Form.Item>
              </Space>
              <Space style={{ width: "100%" }} align="start">
                <Form.Item label="Start" name="start_date" style={{ flex: 1 }}>
                  <DatePicker style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item label="End" name="end_date" style={{ flex: 1 }}>
                  <DatePicker style={{ width: "100%" }} />
                </Form.Item>
              </Space>
              <Space style={{ width: "100%" }} align="start">
                <Form.Item label="Horizon" name="horizon" style={{ flex: 1 }}>
                  <InputNumber min={1} max={60} style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item label="Quantiles" name="quantiles" style={{ flex: 1 }}>
                  <InputNumber min={2} max={20} style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item label="Top K" name="top_k" style={{ flex: 1 }}>
                  <InputNumber min={1} max={200} style={{ width: "100%" }} />
                </Form.Item>
              </Space>
              <Form.Item style={{ marginBottom: 0 }}>
                <Button type="primary" htmlType="submit" loading={miningLoading}>
                  Run mining
                </Button>
              </Form.Item>
            </Form>
          </Modal>

          <Drawer
            open={qualityOpen}
            width={860}
            title={`Research Quality - ${qualityRunId}`}
            onClose={() => setQualityOpen(false)}
            extra={
              <Button loading={qualityLoading} onClick={() => runQualityEvaluation(qualityRunId)}>
                Evaluate
              </Button>
            }
            destroyOnClose
          >
            {qualityLoading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : qualityReport ? (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Space wrap>
                  <Tag color={qualityColor(qualityReport.quality_status)}>{qualityReport.quality_status}</Tag>
                  <Tag>{qualityReport.promotion_status}</Tag>
                  <Tag>Score {qualityReport.quality_score}</Tag>
                  {qualityReport.not_executable ? <Tag color="red">Not executable</Tag> : null}
                </Space>
                <Typography.Text type="secondary">{qualityReport.timing_note}</Typography.Text>
                <Space wrap>
                  {(qualityReport.reason_codes || []).map((code) => (
                    <Tag key={code}>{code}</Tag>
                  ))}
                </Space>
                <Table size="small" rowKey={(r, i) => `${r.check_id}-${r.reason_code}-${i}`} dataSource={qualityReport.checks || []} columns={qualityColumns} pagination={{ pageSize: 8 }} />
                <Typography.Text type="secondary">ResearchOps object: {qualityReport.research_ops_object_id || "-"}</Typography.Text>
              </Space>
            ) : (
              <EmptyState
                title="No quality report"
                description={qualityError || "This mining run has not been evaluated by Research Quality Guard yet."}
                actionText="Evaluate quality"
                onAction={() => runQualityEvaluation(qualityRunId)}
              />
            )}
          </Drawer>
        </>
      )}
    </PageContainer>
  );
}

