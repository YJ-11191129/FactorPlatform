"use client";

import dynamic from "next/dynamic";
import { Col, Row, Skeleton, Space, Table, Tag } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { MetricCard } from "@/components/common/MetricCard";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { listFactors } from "@/lib/api/factors";
import { getResearchOpsDailyBrief } from "@/lib/api/research-ops";
import { listRuns } from "@/lib/api/runs";
import { formatDate } from "@/lib/utils/date";
import type { FactorItem } from "@/types/factor";
import type { ResearchOpsDailyBrief } from "@/types/research-ops";
import type { RunItem } from "@/types/run";

type LoadState = "idle" | "loading" | "error" | "ready";

const Pie = dynamic(() => import("@ant-design/charts").then((m) => m.Pie), { ssr: false });
const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });

function startOfDay(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function daysAgo(days: number): Date {
  const date = startOfDay(new Date());
  date.setDate(date.getDate() - days);
  return date;
}

export default function DashboardPage() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>("loading");
  const [factors, setFactors] = useState<FactorItem[]>([]);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [brief, setBrief] = useState<ResearchOpsDailyBrief | null>(null);

  async function load() {
    setState("loading");
    try {
      const [fs, rs, rb] = await Promise.all([listFactors(), listRuns(100), getResearchOpsDailyBrief().catch(() => null)]);
      setFactors(fs);
      setRuns(rs);
      setBrief(rb);
      setState("ready");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const metrics = useMemo(() => {
    const online = factors.filter((f) => f.status === "online").length;
    const research = factors.filter((f) => f.status === "research").length;
    const since = daysAgo(7);
    const recentRuns = runs.filter((run) => new Date(run.submitted_at) >= since);
    const latestScoring = runs
      .filter((run) => run.task_type === "scoring")
      .sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime())[0];
    return {
      factor_total: factors.length,
      factor_online: online,
      factor_research: research,
      run_7d: recentRuns.length,
      run_success_rate_7d: recentRuns.length
        ? Math.round((recentRuns.filter((run) => run.status === "success").length / recentRuns.length) * 100)
        : 0,
      latest_scoring_date: latestScoring?.submitted_at || null,
    };
  }, [factors, runs]);

  const donutData = useMemo(() => {
    const byCategory = new Map<string, number>();
    for (const f of factors) byCategory.set(f.category || "uncategorized", (byCategory.get(f.category || "uncategorized") || 0) + 1);
    return Array.from(byCategory.entries()).map(([category, count]) => ({ category, count }));
  }, [factors]);

  const runTrend = useMemo(() => {
    const days = Array.from({ length: 30 }, (_, index) => {
      const day = daysAgo(29 - index);
      return {
        date: day.toISOString().slice(0, 10),
        run_count: 0,
        success_count: 0,
      };
    });
    const byDate = new Map(days.map((item) => [item.date, item]));
    for (const run of runs) {
      const key = new Date(run.submitted_at).toISOString().slice(0, 10);
      const bucket = byDate.get(key);
      if (!bucket) continue;
      bucket.run_count += 1;
      if (run.status === "success") bucket.success_count += 1;
    }
    return days;
  }, [runs]);

  const signalSummary = (brief?.latest_signal_snapshot?.summary || {}) as Record<string, any>;

  return (
    <PageContainer title="Dashboard" subtitle="Operational overview sourced from backend factors and run records">
      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : state === "error" ? (
        <ErrorState title="Dashboard data load failed" onRetry={load} />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={12} md={8} xl={4}>
              <MetricCard title="Factors" value={metrics.factor_total} onClick={() => router.push("/factors")} />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <MetricCard title="Online Factors" value={metrics.factor_online} />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <MetricCard title="Research Factors" value={metrics.factor_research} />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <MetricCard title="Runs 7D" value={metrics.run_7d} onClick={() => router.push("/runs")} />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <MetricCard title="Success 7D" value={metrics.run_success_rate_7d} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <MetricCard
                title="Latest Scoring"
                value={metrics.latest_scoring_date ? formatDate(metrics.latest_scoring_date) : "-"}
                onClick={() => router.push("/scoring")}
              />
            </Col>
          </Row>

          <SectionCard title="ResearchOps Daily Brief">
            {brief ? (
              <Row gutter={[12, 12]}>
                <Col xs={24} md={8} xl={4}>
                  <MetricCard
                    title="Data Health"
                    value={brief.data_health.blocking_status || brief.data_health.status || "PENDING"}
                    onClick={() => router.push("/data-maintenance")}
                  />
                </Col>
                <Col xs={12} md={8} xl={4}>
                  <MetricCard title="Signals" value={Number(signalSummary.generated_count || 0)} onClick={() => router.push("/signal-center")} />
                </Col>
                <Col xs={12} md={8} xl={4}>
                  <MetricCard title="Blocked" value={Number(signalSummary.blocked_count || brief.router_summary.blocked_count || 0)} />
                </Col>
                <Col xs={12} md={8} xl={4}>
                  <MetricCard title="Shadow" value={Number(brief.shadow_summary.shadow_count || 0)} onClick={() => router.push("/signal-center?mode=shadow")} />
                </Col>
                <Col xs={12} md={8} xl={4}>
                  <MetricCard title="Outcomes" value={brief.latest_outcome ? brief.latest_outcome.status : "PENDING"} onClick={() => router.push("/performance")} />
                </Col>
                <Col xs={12} md={8} xl={4}>
                  <MetricCard title="Reports" value={brief.latest_reports.length} />
                </Col>
                <Col span={24}>
                  <Space wrap>
                    <Tag color={brief.open_gaps.length ? "gold" : "green"}>{brief.open_gaps.length ? "Open gaps" : "Audit chain ready"}</Tag>
                    {brief.open_gaps.slice(0, 4).map((gap) => (
                      <Tag key={gap.code}>{gap.code}</Tag>
                    ))}
                    {brief.router_summary.block_reason ? <Tag color="red">{brief.router_summary.block_reason}</Tag> : null}
                  </Space>
                </Col>
              </Row>
            ) : (
              <EmptyState title="No ResearchOps brief" description="Generate artifacts or rebuild the ResearchOps index to populate the audit chain." />
            )}
          </SectionCard>

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <SectionCard title="Factor Categories">
                {donutData.length > 0 ? (
                  <Pie
                    data={donutData}
                    angleField="count"
                    colorField="category"
                    innerRadius={0.6}
                    legend={{ position: "bottom" }}
                    height={280}
                  />
                ) : (
                  <EmptyState title="No factor registry data" actionText="Open Factors" onAction={() => router.push("/factors")} />
                )}
              </SectionCard>
            </Col>
            <Col xs={24} xl={12}>
              <SectionCard title="Run Trend 30D">
                {runs.length > 0 ? (
                  <Line
                    data={runTrend.flatMap((d) => [
                      { date: d.date, type: "run_count", value: d.run_count },
                      { date: d.date, type: "success_count", value: d.success_count },
                    ])}
                    xField="date"
                    yField="value"
                    seriesField="type"
                    height={280}
                    legend={{ position: "bottom" }}
                  />
                ) : (
                  <EmptyState title="No run records" actionText="Open Runs" onAction={() => router.push("/runs")} />
                )}
              </SectionCard>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <SectionCard title="Recently Updated Factors">
                {factors.length === 0 ? (
                  <EmptyState title="No factor data" actionText="Open Factors" onAction={() => router.push("/factors")} />
                ) : (
                  <Table
                    size="small"
                    rowKey={(r) => r.factor_id}
                    dataSource={factors.slice(0, 8)}
                    pagination={false}
                    columns={[
                      { title: "Factor", dataIndex: "factor_name", key: "factor_name" },
                      { title: "Category", dataIndex: "category", key: "category", width: 120 },
                      {
                        title: "Status",
                        dataIndex: "status",
                        key: "status",
                        width: 110,
                        render: (v: string) => <Tag color={v === "online" ? "green" : v === "research" ? "blue" : "default"}>{v}</Tag>,
                      },
                      { title: "Owner", dataIndex: "owner", key: "owner", width: 120 },
                    ]}
                  />
                )}
              </SectionCard>
            </Col>
            <Col xs={24} xl={12}>
              <SectionCard title="Recent Runs">
                {runs.length === 0 ? (
                  <EmptyState title="No run records" actionText="Open Runs" onAction={() => router.push("/runs")} />
                ) : (
                  <Table
                    size="small"
                    rowKey={(r) => r.calc_batch_id}
                    dataSource={runs.slice(0, 8)}
                    pagination={false}
                    columns={[
                      { title: "Batch ID", dataIndex: "calc_batch_id", key: "calc_batch_id" },
                      { title: "Task", dataIndex: "task_name", key: "task_name" },
                      { title: "Type", dataIndex: "task_type", key: "task_type", width: 110 },
                      {
                        title: "Status",
                        dataIndex: "status",
                        key: "status",
                        width: 110,
                        render: (v: string) => <Tag color={v === "success" ? "green" : v === "failed" ? "red" : "gold"}>{v}</Tag>,
                      },
                    ]}
                  />
                )}
              </SectionCard>
            </Col>
          </Row>
        </>
      )}
    </PageContainer>
  );
}
