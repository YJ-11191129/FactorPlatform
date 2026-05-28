"use client";

import dynamic from "next/dynamic";
import { Button, Card, Descriptions, Divider, Skeleton, Space, Tabs, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { CopyableCodeBlock } from "@/components/common/CopyableCodeBlock";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { FactorRunModal, type RunMode } from "@/components/factor/FactorRunModal";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { getFactorDetail, runDemo, runQlib } from "@/lib/api/factors";
import { listRuns } from "@/lib/api/runs";
import { formatDateTime } from "@/lib/utils/date";
import type { FactorDetail } from "@/types/factor";
import type { RunItem } from "@/types/run";

type LoadState = "loading" | "error" | "empty" | "ready";

const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });

function pct(value?: number) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
}

export default function FactorDetailPage() {
  const router = useRouter();
  const [advancedMode] = useAdvancedMode();
  const params = useParams<{ factorName: string }>();
  const factorName = decodeURIComponent(params.factorName);

  const [state, setState] = useState<LoadState>("loading");
  const [detail, setDetail] = useState<FactorDetail | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [runOpen, setRunOpen] = useState(false);
  const [runMode, setRunMode] = useState<RunMode>("demo");
  const [runLoading, setRunLoading] = useState(false);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const [d, r] = await Promise.all([getFactorDetail(factorName), listRuns(80)]);
      if (!d) {
        setState("empty");
        return;
      }
      setDetail(d);
      setRuns(r);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [factorName]);

  useEffect(() => {
    load();
  }, [load]);

  const relatedRuns = useMemo(() => runs.filter((x) => x.task_name === factorName).slice(0, 20), [runs, factorName]);
  const diagSeries = useMemo(
    () =>
      Array.from({ length: 60 }).map((_, i) => {
        const d = new Date();
        d.setDate(d.getDate() - (59 - i));
        return { date: d.toISOString().slice(0, 10), value: 0.02 * Math.sin(i / 8) + 0.005 * (i % 5) };
      }),
    [],
  );

  async function submitRun(values: { n: number; universe: string; instrument_limit: number; save: boolean }) {
    setRunLoading(true);
    try {
      if (runMode === "demo") {
        const res = await runDemo({ factor_name: factorName, params: { n: values.n }, save: values.save });
        message.success(res.calc_batch_id ? (advancedMode ? `Saved: ${res.calc_batch_id}` : "Result artifact saved") : "Run submitted");
      } else {
        const res = await runQlib({
          factor_name: factorName,
          params: { n: values.n },
          provider_uri: "D:\\mcQlib\\data\\qlib_bin\\cn_data",
          universe: values.universe,
          instrument_limit: values.instrument_limit,
          save: values.save,
        });
        message.success(res.calc_batch_id ? (advancedMode ? `Saved: ${res.calc_batch_id}` : "Result artifact saved") : "Run submitted");
      }
      setRunOpen(false);
    } catch (e: any) {
      message.error(e?.message || "Run failed");
    } finally {
      setRunLoading(false);
    }
  }

  return (
    <PageContainer
      title="Factor Detail"
      breadcrumb={["Factors", advancedMode ? factorName : "Selected factor"]}
      extra={
        <Space>
          <Button
            onClick={() => {
              setRunMode("demo");
              setRunOpen(true);
            }}
          >
            Run Demo
          </Button>
          <Button
            type="primary"
            onClick={() => {
              setRunMode("qlib");
              setRunOpen(true);
            }}
          >
            Run Market Factor
          </Button>
          <Button onClick={() => router.push("/factors")}>Back to Factors</Button>
        </Space>
      }
    >
      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 12 }} />
      ) : state === "error" ? (
        <ErrorState title="Factor detail failed to load" onRetry={load} />
      ) : state === "empty" || !detail ? (
        <EmptyState title="Factor not found" actionText="Back to Factors" onAction={() => router.push("/factors")} />
      ) : (
        <>
          <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {detail.display_name || detail.factor_name}
                </Typography.Title>
                <Tag>{detail.category}</Tag>
                <Tag color={detail.status === "online" ? "green" : "blue"}>{detail.status}</Tag>
                {advancedMode && detail.version ? <Tag>v{detail.version}</Tag> : null}
              </div>
              {advancedMode ? <Typography.Text type="secondary">{detail.factor_name}</Typography.Text> : null}
            </Space>
          </Card>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 16, marginTop: 16 }}>
            <Tabs
              items={[
                {
                  key: "overview",
                  label: "Overview",
                  children: (
                    <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                      <Descriptions column={2} size="small" bordered>
                        {advancedMode ? <Descriptions.Item label="Factor">{detail.factor_name}</Descriptions.Item> : null}
                        <Descriptions.Item label="Display name">{detail.display_name}</Descriptions.Item>
                        <Descriptions.Item label="Category">{detail.category}</Descriptions.Item>
                        <Descriptions.Item label="Frequency">{detail.frequency}</Descriptions.Item>
                        <Descriptions.Item label="Markets">{detail.market_scope.join(", ")}</Descriptions.Item>
                        <Descriptions.Item label="Direction">{detail.direction}</Descriptions.Item>
                        <Descriptions.Item label="Coverage">{pct(detail.coverage)}</Descriptions.Item>
                        <Descriptions.Item label="Missing rate">{pct(detail.missing_rate)}</Descriptions.Item>
                        <Descriptions.Item label="Latest run">{detail.latest_run_at ? formatDateTime(detail.latest_run_at) : "-"}</Descriptions.Item>
                        <Descriptions.Item label="Owner">{detail.owner || "-"}</Descriptions.Item>
                      </Descriptions>
                      <Divider />
                      <Typography.Title level={5} style={{ marginTop: 0 }}>Definition</Typography.Title>
                      <Typography.Paragraph style={{ marginBottom: 0 }}>{detail.description || "-"}</Typography.Paragraph>
                    </Card>
                  ),
                },
                {
                  key: "logic",
                  label: "Logic",
                  children: (
                    <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                      <Typography.Title level={5} style={{ marginTop: 0 }}>Formula</Typography.Title>
                      <Typography.Paragraph>{detail.formula || "-"}</Typography.Paragraph>
                      <Divider />
                      <Typography.Title level={5} style={{ marginTop: 0 }}>Dependencies</Typography.Title>
                      <Typography.Paragraph>{(detail.dependencies || []).join(", ") || "-"}</Typography.Paragraph>
                      {advancedMode ? (
                        <>
                          <Divider />
                          <Typography.Title level={5} style={{ marginTop: 0 }}>Code</Typography.Title>
                          <CopyableCodeBlock code={detail.code_snippet || ""} />
                        </>
                      ) : null}
                    </Card>
                  ),
                },
                {
                  key: "diagnostics",
                  label: "Diagnostics",
                  children: (
                    <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                      <Typography.Text type="secondary">Illustrative diagnostics for research review.</Typography.Text>
                      <Divider />
                      <Line data={diagSeries} xField="date" yField="value" height={260} />
                    </Card>
                  ),
                },
                {
                  key: "runs",
                  label: "Runs",
                  children: (
                    <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                      {relatedRuns.length === 0 ? (
                        <EmptyState title="No run records" />
                      ) : (
                        <ul style={{ margin: 0, paddingLeft: 18 }}>
                          {relatedRuns.map((r, index) => (
                            <li key={r.calc_batch_id}>
                              {advancedMode ? <Typography.Text code>{r.calc_batch_id}</Typography.Text> : <Typography.Text>Research run {index + 1}</Typography.Text>} - {r.task_type} - {r.status}
                            </li>
                          ))}
                        </ul>
                      )}
                    </Card>
                  ),
                },
              ]}
            />

            <Card title="Summary" styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                <Typography.Text type="secondary">Recent research runs</Typography.Text>
                {relatedRuns.slice(0, 5).length === 0 ? (
                  <Typography.Text type="secondary">-</Typography.Text>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {relatedRuns.slice(0, 5).map((r, index) => (
                      <li key={r.calc_batch_id}>{advancedMode ? <Typography.Text code>{r.calc_batch_id}</Typography.Text> : `Run ${index + 1}`}</li>
                    ))}
                  </ul>
                )}
                <Button block onClick={() => router.push("/runs")}>Open Runs</Button>
              </Space>
            </Card>
          </div>

          <FactorRunModal open={runOpen} mode={runMode} factorName={factorName} loading={runLoading} onCancel={() => setRunOpen(false)} onSubmit={submitRun} />
        </>
      )}
    </PageContainer>
  );
}
