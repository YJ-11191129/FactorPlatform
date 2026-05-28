"use client";

import { Alert, Button, Card, Checkbox, Descriptions, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PageContainer } from "@/components/layout/PageContainer";
import { useAdvancedMode } from "@/lib/advanced-mode";
import {
  getDataPathAudit,
  getLatestDataMaintenanceReport,
  runDailyDataMaintenance,
  type DataMaintenanceRun,
  type DataPathAudit,
  type DataSourceStatus,
  type RunDailyMaintenancePayload,
} from "@/lib/api/data-maintenance";

import styles from "./data-maintenance.module.css";

function statusColor(status: string) {
  if (status === "OK" || status === "SUCCESS" || status === "READY") return "green";
  if (status === "STALE" || status === "WARN" || status === "SKIPPED" || status === "OPENBB_NOT_READY") return "gold";
  return "red";
}

function formatBytes(value?: number | null) {
  if (!value) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let idx = 0;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  return `${size.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

function formatNumber(value?: number | null) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString();
}

function errorText(error: unknown, fallback: string) {
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message?: unknown }).message || fallback);
  }
  return fallback;
}

function artifactLabel(run?: DataMaintenanceRun | null, advancedMode?: boolean) {
  if (!run?.artifacts) return "-";
  if (advancedMode) return run.artifacts.markdown_path || run.artifacts.json_path || "registered";
  return "registered";
}

export default function DataMaintenancePage() {
  const [advancedMode] = useAdvancedMode();
  const [audit, setAudit] = useState<DataPathAudit | null>(null);
  const [run, setRun] = useState<DataMaintenanceRun | null>(null);
  const [latestReport, setLatestReport] = useState<DataMaintenanceRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [runningUpdater, setRunningUpdater] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<RunDailyMaintenancePayload>({
    dry_run: false,
    refresh_factor_registry: true,
    refresh_stock_screen: true,
    run_radar_smoke: true,
    run_external_updater: false,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAudit(await getDataPathAudit());
    } catch (e) {
      setError(errorText(e, "Data audit failed"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    getLatestDataMaintenanceReport().then(setLatestReport).catch(() => setLatestReport(null));
  }, [load]);

  async function runMaintenance(extra?: Partial<RunDailyMaintenancePayload>) {
    setRunning(true);
    setError(null);
    try {
      const out = await runDailyDataMaintenance({ ...options, ...extra });
      setRun(out);
      setLatestReport(out);
      setAudit(out.audit);
      message.success("Daily maintenance completed");
    } catch (e) {
      const text = errorText(e, "Daily maintenance failed");
      setError(text);
      message.error(text);
    } finally {
      setRunning(false);
    }
  }

  async function runUpdater(updaterId: string) {
    setRunningUpdater(updaterId);
    try {
      await runMaintenance({ dry_run: false, updater_id: updaterId, run_external_updater: false });
    } finally {
      setRunningUpdater(null);
    }
  }

  const columns: ColumnsType<DataSourceStatus> = useMemo(
    () => [
      {
        title: "Status",
        dataIndex: "status",
        width: 92,
        render: (value) => <Tag color={statusColor(String(value))}>{String(value)}</Tag>,
      },
      {
        title: "Gate",
        dataIndex: "is_blocking",
        width: 94,
        render: (value, record) => (value ? <Tag color="red">BLOCKING</Tag> : <Tag>{record.source_id === "openbb_sdk" ? "EVIDENCE" : "INFO"}</Tag>),
      },
      {
        title: "Source",
        dataIndex: "label",
        width: 230,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{record.label}</Typography.Text>
            {advancedMode ? <Typography.Text type="secondary">{record.source_id}</Typography.Text> : null}
          </Space>
        ),
      },
      {
        title: advancedMode ? "Path" : "Storage",
        dataIndex: "path",
        ellipsis: true,
        render: (value, record) =>
          advancedMode ? (
            <Typography.Text copyable>{String(value)}</Typography.Text>
          ) : (
            <Typography.Text>{(record as any).database_backed ? "PostgreSQL" : String(record.kind || "local storage")}</Typography.Text>
          ),
      },
      { title: "Latest", dataIndex: "end_date", width: 112, render: (value) => value || "-" },
      { title: "Lag", dataIndex: "days_since_latest", width: 90, render: formatNumber },
      { title: "Rows", dataIndex: "row_count", width: 120, render: formatNumber },
      { title: "Assets", dataIndex: "asset_count", width: 90, render: formatNumber },
      { title: "Size", dataIndex: "file_size_bytes", width: 100, render: formatBytes },
    ],
    [advancedMode],
  );

  const visibleRun = run || latestReport;
  const sourceCount = audit?.sources.length || 0;
  const okCount = audit?.status_counts.OK || 0;
  const staleCount = audit?.status_counts.STALE || 0;
  const missingCount = audit?.status_counts.MISSING || 0;
  const blockers = audit?.blockers || [];
  const recommendations = audit?.recommendations || [];

  return (
    <PageContainer
      title="Data Maintenance"
      subtitle="Audit database-backed market data, freshness, and derived research artifacts."
      extra={
        <Space>
          <Button onClick={load} loading={loading}>
            Refresh Audit
          </Button>
          <Button type="primary" onClick={() => runMaintenance()} loading={running}>
            Run Daily Maintenance
          </Button>
        </Space>
      }
    >
      <div className={styles.shell}>
        {error ? <Alert type="error" showIcon message={error} /> : null}
        <section className={styles.hero}>
          <div>
            <Typography.Title level={1} className={styles.heroTitle}>
              Data Health and Refresh
            </Typography.Title>
            <Typography.Paragraph className={styles.heroText}>
              Roadshow mode reads market data from PostgreSQL and keeps generated reports in the artifact registry. Warnings are surfaced without presenting stale data as live market truth.
            </Typography.Paragraph>
          </div>
          <div className={styles.metricGrid}>
            <div><span>Sources</span><strong>{sourceCount}</strong></div>
            <div><span>OK</span><strong>{okCount}</strong></div>
            <div><span>Stale</span><strong>{staleCount}</strong></div>
            <div><span>Missing</span><strong>{missingCount}</strong></div>
          </div>
        </section>

        <Card title="Maintenance Options">
          <Space wrap>
            <Checkbox checked={options.dry_run} onChange={(e) => setOptions((v) => ({ ...v, dry_run: e.target.checked }))}>Dry run</Checkbox>
            <Checkbox checked={options.refresh_factor_registry} onChange={(e) => setOptions((v) => ({ ...v, refresh_factor_registry: e.target.checked }))}>Refresh factor registry</Checkbox>
            <Checkbox checked={options.refresh_stock_screen} onChange={(e) => setOptions((v) => ({ ...v, refresh_stock_screen: e.target.checked }))}>Refresh stock screen</Checkbox>
            <Checkbox checked={options.run_radar_smoke} onChange={(e) => setOptions((v) => ({ ...v, run_radar_smoke: e.target.checked }))}>Run radar smoke test</Checkbox>
            <Checkbox checked={options.run_external_updater} onChange={(e) => setOptions((v) => ({ ...v, run_external_updater: e.target.checked }))}>Run external updater</Checkbox>
          </Space>
        </Card>

        <Card title="Run Gate" extra={<Tag color={audit?.blocking_status === "BLOCKED" ? "red" : audit?.blocking_status === "WARN" ? "gold" : "green"}>{audit?.blocking_status || "UNKNOWN"}</Tag>}>
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            {blockers.length ? (
              <Alert type="error" showIcon message="Critical data sources block live runs" description={blockers.map((item) => `${item.source_id}: ${item.reason || item.status}`).join("; ")} />
            ) : (
              <Alert type={audit?.blocking_status === "WARN" ? "warning" : "success"} showIcon message="No critical blockers" />
            )}
            {recommendations.length ? (
              <Space wrap>
                {recommendations.map((item) => (
                  <Button key={`${item.source_id}-${item.updater_id}`} size="small" onClick={() => runUpdater(item.updater_id)} loading={runningUpdater === item.updater_id}>
                    Run updater: {item.updater_id}
                  </Button>
                ))}
              </Space>
            ) : null}
            <Typography.Text type="secondary">Latest report: {artifactLabel(visibleRun, advancedMode)}</Typography.Text>
          </Space>
        </Card>

        <Card title="Data Audit" extra={audit ? <Tag color={statusColor(audit.overall_status)}>{audit.overall_status}</Tag> : null}>
          <Table
            rowKey="source_id"
            loading={loading}
            columns={columns}
            dataSource={audit?.sources || []}
            scroll={{ x: 1060 }}
            expandable={
              advancedMode
                ? {
                    expandedRowRender: (record) => (
                      <Descriptions size="small" column={2}>
                        <Descriptions.Item label="mtime">{record.mtime || "-"}</Descriptions.Item>
                        <Descriptions.Item label="freshness_days">{record.freshness_days ?? "-"}</Descriptions.Item>
                        <Descriptions.Item label="calendar_count">{record.calendar_count ?? "-"}</Descriptions.Item>
                        <Descriptions.Item label="feature_dir_count">{record.feature_dir_count ?? "-"}</Descriptions.Item>
                        <Descriptions.Item label="freshness_reason" span={2}>{record.freshness_reason || "-"}</Descriptions.Item>
                        <Descriptions.Item label="notes" span={2}>{(record.notes || []).join("; ") || "-"}</Descriptions.Item>
                      </Descriptions>
                    ),
                  }
                : undefined
            }
          />
        </Card>

        {visibleRun ? (
          <Card title="Latest Maintenance Run" extra={<Tag color={statusColor(visibleRun.overall_status)}>{visibleRun.overall_status}</Tag>}>
            <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
              {advancedMode ? <Descriptions.Item label="run_id">{visibleRun.run_id}</Descriptions.Item> : null}
              <Descriptions.Item label="generated_at">{visibleRun.generated_at}</Descriptions.Item>
              <Descriptions.Item label="dry_run">{String(visibleRun.dry_run)}</Descriptions.Item>
              <Descriptions.Item label={advancedMode ? "artifacts" : "Report"}>{artifactLabel(visibleRun, advancedMode)}</Descriptions.Item>
            </Descriptions>
            <Table
              size="small"
              rowKey={(record, index) => `${String(record.name || "step")}-${index}`}
              pagination={false}
              dataSource={visibleRun.steps}
              columns={[
                { title: "Step", dataIndex: "name" },
                { title: "Status", dataIndex: "status", render: (value) => <Tag color={statusColor(String(value))}>{String(value)}</Tag> },
                { title: "Result", render: (_, record) => <Typography.Text>{record.message ? String(record.message) : JSON.stringify(record.result || {})}</Typography.Text> },
              ]}
            />
          </Card>
        ) : null}
      </div>
    </PageContainer>
  );
}
