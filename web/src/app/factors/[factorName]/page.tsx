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
import { listRuns } from "@/lib/api/runs";
import { getFactorDetail, runDemo, runQlib } from "@/lib/api/factors";
import { formatDateTime } from "@/lib/utils/date";
import type { FactorDetail } from "@/types/factor";
import type { RunItem } from "@/types/run";

type LoadState = "loading" | "error" | "empty" | "ready";

const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });
const Area = dynamic(() => import("@ant-design/charts").then((m) => m.Area), { ssr: false });

export default function FactorDetailPage() {
  const router = useRouter();
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

  const diagSeries = useMemo(() => {
    const base = Array.from({ length: 60 }).map((_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - (59 - i));
      const t = d.toISOString().slice(0, 10);
      const v = 0.02 * Math.sin(i / 8) + 0.005 * (i % 5);
      return { date: t, value: v };
    });
    return base;
  }, []);

  async function submitRun(values: { n: number; universe: string; instrument_limit: number; save: boolean }) {
    setRunLoading(true);
    try {
      if (runMode === "demo") {
        const res = await runDemo({ factor_name: factorName, params: { n: values.n }, save: values.save });
        message.success(res.calc_batch_id ? `已保存：${res.calc_batch_id}` : "已提交运行");
      } else {
        const res = await runQlib({
          factor_name: factorName,
          params: { n: values.n },
          provider_uri: "D:\\mcQlib\\data\\qlib_bin",
          universe: values.universe,
          instrument_limit: values.instrument_limit,
          save: values.save,
        });
        message.success(res.calc_batch_id ? `已保存：${res.calc_batch_id}` : "已提交运行");
      }
      setRunOpen(false);
    } catch (e: any) {
      message.error(e?.message || "运行失败");
    } finally {
      setRunLoading(false);
    }
  }

  return (
    <PageContainer
      title="因子详情"
      breadcrumb={["Factors", factorName]}
      extra={
        <Space>
          <Button
            onClick={() => {
              setRunMode("demo");
              setRunOpen(true);
            }}
          >
            运行 Demo
          </Button>
          <Button
            type="primary"
            onClick={() => {
              setRunMode("qlib");
              setRunOpen(true);
            }}
          >
            运行 Qlib
          </Button>
          <Button onClick={() => router.push("/factors")}>返回列表</Button>
        </Space>
      }
    >
      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 12 }} />
      ) : state === "error" ? (
        <ErrorState title="因子详情加载失败" onRetry={load} />
      ) : state === "empty" || !detail ? (
        <EmptyState title="因子不存在" description="请检查 factorName 是否正确" actionText="返回因子列表" onAction={() => router.push("/factors")} />
      ) : (
        <>
          <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {detail.factor_name}
                </Typography.Title>
                <Tag>{detail.category}</Tag>
                <Tag color={detail.status === "online" ? "green" : "blue"}>{detail.status}</Tag>
                {detail.version ? <Tag>v{detail.version}</Tag> : null}
              </div>
              <Typography.Text type="secondary">{detail.display_name}</Typography.Text>
            </Space>
          </Card>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16, marginTop: 16 }}>
            <div>
              <Tabs
                items={[
                  {
                    key: "overview",
                    label: "Overview",
                    children: (
                      <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                        <Descriptions column={2} size="small" bordered>
                          <Descriptions.Item label="因子名">{detail.factor_name}</Descriptions.Item>
                          <Descriptions.Item label="中文名">{detail.display_name}</Descriptions.Item>
                          <Descriptions.Item label="分类">{detail.category}</Descriptions.Item>
                          <Descriptions.Item label="频率">{detail.frequency}</Descriptions.Item>
                          <Descriptions.Item label="适用市场">{detail.market_scope.join(", ")}</Descriptions.Item>
                          <Descriptions.Item label="方向">{detail.direction}</Descriptions.Item>
                          <Descriptions.Item label="覆盖率">{typeof detail.coverage === "number" ? `${Math.round(detail.coverage * 100)}%` : "-"}</Descriptions.Item>
                          <Descriptions.Item label="缺失率">{typeof detail.missing_rate === "number" ? `${Math.round(detail.missing_rate * 100)}%` : "-"}</Descriptions.Item>
                          <Descriptions.Item label="最近运行">{detail.latest_run_at ? formatDateTime(detail.latest_run_at) : "-"}</Descriptions.Item>
                          <Descriptions.Item label="负责人">{detail.owner || "-"}</Descriptions.Item>
                        </Descriptions>
                        <Divider />
                        <Typography.Title level={5} style={{ marginTop: 0 }}>
                          定义说明
                        </Typography.Title>
                        <Typography.Paragraph style={{ marginBottom: 0 }}>{detail.description || "-"}</Typography.Paragraph>
                      </Card>
                    ),
                  },
                  {
                    key: "logic",
                    label: "Logic",
                    children: (
                      <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                        <Typography.Title level={5} style={{ marginTop: 0 }}>
                          公式
                        </Typography.Title>
                        <Typography.Paragraph>{detail.formula || "-"}</Typography.Paragraph>
                        <Divider />
                        <Typography.Title level={5} style={{ marginTop: 0 }}>
                          依赖关系
                        </Typography.Title>
                        <Typography.Paragraph>{(detail.dependencies || []).join(", ") || "-"}</Typography.Paragraph>
                        <Divider />
                        <Typography.Title level={5} style={{ marginTop: 0 }}>
                          代码片段
                        </Typography.Title>
                        <CopyableCodeBlock code={detail.code_snippet || ""} />
                      </Card>
                    ),
                  },
                  {
                    key: "diagnostics",
                    label: "Diagnostics",
                    children: (
                      <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          当前为示意数据（后端暂无诊断接口时使用 mock）
                        </Typography.Text>
                        <Divider />
                        <Line data={diagSeries} xField="date" yField="value" height={240} />
                        <Divider />
                        <Area data={diagSeries.map((x) => ({ ...x, value: Math.abs(x.value) }))} xField="date" yField="value" height={240} />
                      </Card>
                    ),
                  },
                  {
                    key: "runs",
                    label: "Runs",
                    children: (
                      <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                        {relatedRuns.length === 0 ? (
                          <EmptyState title="暂无运行记录" description="可先发起一次 Demo 或 Qlib 运行" />
                        ) : (
                          <ul style={{ margin: 0, paddingLeft: 18 }}>
                            {relatedRuns.map((r) => (
                              <li key={r.calc_batch_id}>
                                <Typography.Text code>{r.calc_batch_id}</Typography.Text> · {r.task_type} · {r.status}
                              </li>
                            ))}
                          </ul>
                        )}
                      </Card>
                    ),
                  },
                  {
                    key: "related",
                    label: "Related",
                    children: (
                      <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                        <Typography.Text type="secondary">预留：相关因子 / 相似标签 / 推荐查看</Typography.Text>
                      </Card>
                    ),
                  },
                ]}
              />
            </div>

            <div>
              <Card title="快捷侧栏" styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
                <Space direction="vertical" size={10} style={{ width: "100%" }}>
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      最近 5 次运行摘要
                    </Typography.Text>
                    <div style={{ marginTop: 6 }}>
                      {(relatedRuns.slice(0, 5) || []).length === 0 ? (
                        <Typography.Text type="secondary">-</Typography.Text>
                      ) : (
                        <ul style={{ margin: 0, paddingLeft: 18 }}>
                          {relatedRuns.slice(0, 5).map((r) => (
                            <li key={r.calc_batch_id}>
                              <Typography.Text code>{r.calc_batch_id}</Typography.Text>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                  <Button block onClick={() => router.push("/runs")}>
                    去运行中心
                  </Button>
                </Space>
              </Card>
            </div>
          </div>

          <FactorRunModal open={runOpen} mode={runMode} factorName={factorName} loading={runLoading} onCancel={() => setRunOpen(false)} onSubmit={submitRun} />
        </>
      )}
    </PageContainer>
  );
}

