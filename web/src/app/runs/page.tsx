"use client";

import { Drawer, Skeleton, Space, Table, Tag, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { RunDetailDrawer } from "@/components/run/RunDetailDrawer";
import { RunFilterBar, type RunFilters } from "@/components/run/RunFilterBar";
import { RunTable } from "@/components/run/RunTable";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { getResearchOpsLineage } from "@/lib/api/research-ops";
import { getRunMeta, listRuns, runDownloadUrl } from "@/lib/api/runs";
import type { ResearchOpsLineage, ResearchOpsObject } from "@/types/research-ops";
import type { RunItem, RunMeta } from "@/types/run";

type LoadState = "loading" | "error" | "ready";

function statusColor(status: string): string {
  if (status === "OK" || status === "SUCCESS" || status === "SHADOW_EVALUATED") return "green";
  if (status === "BLOCKED" || status === "FAILED") return "red";
  return "gold";
}

export default function RunsPage() {
  const [advancedMode] = useAdvancedMode();
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<RunItem[]>([]);
  const [filters, setFilters] = useState<RunFilters>({ autoRefresh: false });

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [current, setCurrent] = useState<RunItem | null>(null);
  const [meta, setMeta] = useState<RunMeta | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);

  const [lineageOpen, setLineageOpen] = useState(false);
  const [lineageLoading, setLineageLoading] = useState(false);
  const [lineageTarget, setLineageTarget] = useState("");
  const [lineage, setLineage] = useState<ResearchOpsLineage | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const res = await listRuns(100);
      setData(res);
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!filters.autoRefresh) return;
    const t = setInterval(() => load(), 15000);
    return () => clearInterval(t);
  }, [filters.autoRefresh, load]);

  const filtered = useMemo(() => {
    return data.filter((d) => {
      const q = (filters.q || "").trim().toLowerCase();
      if (q) {
        const hit = d.calc_batch_id.toLowerCase().includes(q) || d.task_name.toLowerCase().includes(q);
        if (!hit) return false;
      }
      if (filters.type && d.task_type !== filters.type) return false;
      if (filters.status && d.status !== filters.status) return false;
      return true;
    });
  }, [data, filters]);

  async function openDrawer(item: RunItem) {
    setDrawerOpen(true);
    setCurrent(item);
    setDrawerLoading(true);
    try {
      const m = await getRunMeta(item.calc_batch_id);
      setMeta(m);
    } finally {
      setDrawerLoading(false);
    }
  }

  async function openLineage(id: string) {
    setLineageTarget(id);
    setLineageOpen(true);
    setLineage(null);
    setLineageLoading(true);
    try {
      setLineage(await getResearchOpsLineage(id));
    } catch {
      setLineage(null);
    } finally {
      setLineageLoading(false);
    }
  }

  return (
    <PageContainer title="Runs" subtitle={advancedMode ? "Review task status, artifacts, and ResearchOps lineage" : "Review research jobs, outputs, and quality status"}>
      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : state === "error" ? (
        <ErrorState title="Run records failed to load" onRetry={load} />
      ) : filtered.length === 0 ? (
        <EmptyState title="No run records" description="Run a demo or qlib factor job from Factors first." actionText="Open Factors" onAction={() => (window.location.href = "/factors")} />
      ) : (
        <>
          <div style={{ marginBottom: 12 }}>
            <RunFilterBar value={filters} onChange={setFilters} onRefresh={load} />
          </div>
          <RunTable
            data={filtered}
            onOpen={openDrawer}
            onLineage={openLineage}
            onDownload={(id) => {
              window.open(runDownloadUrl(id), "_blank", "noreferrer");
            }}
          />
          <RunDetailDrawer open={drawerOpen} loading={drawerLoading} item={current} meta={meta} onClose={() => setDrawerOpen(false)} />
          <Drawer
            open={lineageOpen}
            width={760}
            onClose={() => setLineageOpen(false)}
            title={advancedMode ? `ResearchOps Lineage - ${lineageTarget}` : "Research Lineage"}
            destroyOnClose
          >
            {lineageLoading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : lineage ? (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Typography.Text type="secondary">
                  {lineage.nodes.length} objects, {lineage.edges.length} edges
                </Typography.Text>
                <Table<ResearchOpsObject>
                  size="small"
                  rowKey="object_id"
                  pagination={false}
                  dataSource={lineage.nodes}
                  columns={[
                    {
                      title: "Object",
                      dataIndex: "object_id",
                      key: "object_id",
                      render: (v: string, _record, index) => (advancedMode ? <Typography.Text code>{v}</Typography.Text> : <Typography.Text>Object {index + 1}</Typography.Text>),
                    },
                    {
                      title: "Type",
                      dataIndex: "object_type",
                      key: "object_type",
                      width: 160,
                      render: (v: string) => <Tag>{v}</Tag>,
                    },
                    {
                      title: "Status",
                      dataIndex: "status",
                      key: "status",
                      width: 130,
                      render: (v: string) => <Tag color={statusColor(v)}>{v}</Tag>,
                    },
                  ]}
                />
                {lineage.missing_references.length ? (
                  <div>
                    <Typography.Text type="secondary">Missing references</Typography.Text>
                    <Table
                      size="small"
                      rowKey={(r) => `${r.object_id || r.artifact_path}-${r.reason}`}
                      pagination={false}
                      dataSource={lineage.missing_references}
                      columns={[
                        { title: advancedMode ? "Object / Artifact" : "Reference", render: (_, r) => (advancedMode ? r.object_id || r.artifact_path : r.object_id ? "Registered object" : "Artifact reference") },
                        { title: "Reason", dataIndex: "reason", width: 180 },
                      ]}
                    />
                  </div>
                ) : null}
              </Space>
            ) : (
              <EmptyState title="No lineage registered" description="Rebuild the ResearchOps index after producing artifacts." />
            )}
          </Drawer>
        </>
      )}
    </PageContainer>
  );
}
