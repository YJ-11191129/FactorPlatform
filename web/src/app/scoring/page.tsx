"use client";

import dynamic from "next/dynamic";
import { Alert, Col, Row, Skeleton } from "antd";
import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { MetricCard } from "@/components/common/MetricCard";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { ScoringControlPanel } from "@/components/scoring/ScoringControlPanel";
import { ScoreTable } from "@/components/scoring/ScoreTable";
import { getScoreRows } from "@/lib/api/scoring";
import { allowMockFallback } from "@/lib/api/mockPolicy";
import type { ScoreRow } from "@/types/scoring";

type LoadState = "loading" | "error" | "ready";

const Column = dynamic(() => import("@ant-design/charts").then((m) => m.Column), { ssr: false });
const Bar = dynamic(() => import("@ant-design/charts").then((m) => m.Bar), { ssr: false });

export default function ScoringPage() {
  const [state, setState] = useState<LoadState>("loading");
  const [rows, setRows] = useState<ScoreRow[]>([]);

  async function load() {
    setState("loading");
    try {
      const data = await getScoreRows();
      setRows(data);
      setState("ready");
    } catch {
      setRows([]);
      setState("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const metrics = useMemo(() => {
    if (rows.length === 0) return null;
    const avg = rows.reduce((sum, row) => sum + row.total_score, 0) / rows.length;
    const top10 = rows.slice(0, 10).reduce((sum, row) => sum + row.total_score, 0) / Math.min(10, rows.length);
    const bottom10 = rows.slice(-10).reduce((sum, row) => sum + row.total_score, 0) / Math.min(10, rows.length);
    return {
      count: rows.length,
      avg: Math.round(avg * 100) / 100,
      top10: Math.round(top10 * 100) / 100,
      bottom10: Math.round(bottom10 * 100) / 100,
    };
  }, [rows]);

  const distribution = useMemo(() => {
    const buckets = new Map<string, number>();
    for (const row of rows) {
      const bucket = Math.floor(row.total_score / 5) * 5;
      const key = `${bucket}-${bucket + 5}`;
      buckets.set(key, (buckets.get(key) || 0) + 1);
    }
    return Array.from(buckets.entries())
      .map(([range, count]) => ({ range, count }))
      .sort((a, b) => Number(a.range.split("-")[0]) - Number(b.range.split("-")[0]));
  }, [rows]);

  const industry = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of rows) counts.set(row.industry || "unknown", (counts.get(row.industry || "unknown") || 0) + 1);
    return Array.from(counts.entries()).map(([name, count]) => ({ name, count }));
  }, [rows]);

  const contribution = useMemo(() => {
    const totals = new Map<string, number>();
    for (const row of rows) {
      for (const [factor, value] of Object.entries(row.factor_scores || {})) {
        totals.set(factor, (totals.get(factor) || 0) + Math.abs(value));
      }
    }
    return Array.from(totals.entries())
      .map(([factor, score]) => ({ factor, score: Math.round(score * 100) / 100 }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 12);
  }, [rows]);

  const exportCsv = () => {
    if (rows.length === 0) return;
    const csv = ["symbol,name,total_score,rank"].concat(rows.map((row) => `${row.symbol},${row.name},${row.total_score},${row.rank}`)).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "scoring.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <PageContainer title="Scoring" subtitle="Score rows are loaded from the backend or explicit demo mode only">
      {allowMockFallback() ? (
        <Alert type="warning" showIcon message="Demo mode is enabled" description="Scoring rows may come from web/src/lib/mock/scoring.ts." style={{ marginBottom: 16 }} />
      ) : null}

      {state === "loading" ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : state === "error" ? (
        <ErrorState title="Scoring data unavailable" onRetry={load} />
      ) : rows.length === 0 ? (
        <EmptyState title="No scoring rows" description="The backend did not return a scoring snapshot." actionText="Refresh" onAction={load} />
      ) : (
        <>
          <ScoringControlPanel onGenerate={() => load()} onExport={exportCsv} />

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col span={6}>
              <MetricCard title="Coverage" value={metrics?.count} />
            </Col>
            <Col span={6}>
              <MetricCard title="Average Score" value={metrics?.avg} />
            </Col>
            <Col span={6}>
              <MetricCard title="Top10 Average" value={metrics?.top10} />
            </Col>
            <Col span={6}>
              <MetricCard title="Bottom10 Average" value={metrics?.bottom10} />
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col span={12}>
              <SectionCard title="Score Distribution">
                <Column data={distribution} xField="range" yField="count" height={260} />
              </SectionCard>
            </Col>
            <Col span={12}>
              <SectionCard title="Industry Distribution">
                <Column data={industry} xField="name" yField="count" height={260} />
              </SectionCard>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col span={24}>
              <SectionCard title="Factor Contribution">
                <Bar data={contribution} xField="score" yField="factor" height={300} />
              </SectionCard>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col span={24}>
              <SectionCard title="Scores">
                <ScoreTable data={rows} />
              </SectionCard>
            </Col>
          </Row>
        </>
      )}
    </PageContainer>
  );
}
