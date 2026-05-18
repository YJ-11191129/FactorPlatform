"use client";

import { Alert, Button, Card, Checkbox, Descriptions, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PageContainer } from "@/components/layout/PageContainer";
import {
  getDataPathAudit,
  getLatestDataMaintenanceReport,
  runDailyDataMaintenance,
  type DataMaintenanceRun,
  type DataPathAudit,
  type DataSourceStatus,
  type RunDailyMaintenancePayload,
} from "@/lib/api/data-maintenance";
import { useLanguage } from "@/lib/i18n";

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

export default function DataMaintenancePage() {
  const { language } = useLanguage();
  const zh = language === "zh";
  const t = useCallback((cn: string, en: string) => (zh ? cn : en), [zh]);
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
      setError(errorText(e, t("数据路径审计失败", "Data path audit failed")));
    } finally {
      setLoading(false);
    }
  }, [t]);

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
      message.success(t("每日维护已完成", "Daily maintenance completed"));
    } catch (e) {
      const text = errorText(e, t("每日维护执行失败", "Daily maintenance failed"));
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
        title: t("状态", "Status"),
        dataIndex: "status",
        width: 92,
        render: (value) => <Tag color={statusColor(String(value))}>{String(value)}</Tag>,
      },
      {
        title: t("门禁", "Gate"),
        dataIndex: "is_blocking",
        width: 94,
        render: (value, record) => (value ? <Tag color="red">BLOCKING</Tag> : <Tag>{record.source_id === "openbb_sdk" ? "EVIDENCE" : "INFO"}</Tag>),
      },
      {
        title: t("数据源", "Source"),
        dataIndex: "label",
        width: 210,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{record.label}</Typography.Text>
            <Typography.Text type="secondary">{record.source_id}</Typography.Text>
          </Space>
        ),
      },
      {
        title: t("路径", "Path"),
        dataIndex: "path",
        ellipsis: true,
        render: (value) => <Typography.Text copyable>{String(value)}</Typography.Text>,
      },
      { title: t("最新日期", "Latest"), dataIndex: "end_date", width: 112, render: (value) => value || "-" },
      { title: t("滞后天数", "Lag"), dataIndex: "days_since_latest", width: 90, render: formatNumber },
      { title: t("行数", "Rows"), dataIndex: "row_count", width: 110, render: formatNumber },
      { title: t("标的数", "Assets"), dataIndex: "asset_count", width: 90, render: formatNumber },
      { title: t("大小", "Size"), dataIndex: "file_size_bytes", width: 100, render: formatBytes },
    ],
    [t],
  );

  const sourceCount = audit?.sources.length || 0;
  const okCount = audit?.status_counts.OK || 0;
  const staleCount = audit?.status_counts.STALE || 0;
  const missingCount = audit?.status_counts.MISSING || 0;
  const blockers = audit?.blockers || [];
  const recommendations = audit?.recommendations || [];
  const visibleRun = run || latestReport;

  return (
    <PageContainer
      title={t("数据维护", "Data Maintenance")}
      subtitle={t(
        "统一检查 qlib、Wind 日线、宏观状态和财报数据地址，并执行每日派生产物刷新。",
        "Audit qlib, Wind daily, macro, and financial data paths, then run daily derived refresh tasks.",
      )}
      extra={
        <Space>
          <Button onClick={load} loading={loading}>
            {t("刷新审计", "Refresh Audit")}
          </Button>
          <Button type="primary" onClick={() => runMaintenance()} loading={running}>
            {t("运行每日维护", "Run Daily Maintenance")}
          </Button>
        </Space>
      }
    >
      <div className={styles.shell}>
        {error ? <Alert type="error" showIcon message={error} /> : null}
        <section className={styles.hero}>
          <div>
            <Typography.Title level={1} className={styles.heroTitle}>
              {t("数据地址体检与每日刷新", "Data Path Health & Daily Refresh")}
            </Typography.Title>
            <Typography.Paragraph className={styles.heroText}>
              {t(
                "默认不改写原始数据，只刷新 factor registry、股票筛选产物，并跑一次 Stock Radar smoke test。外部下载脚本需要通过环境变量显式配置。",
                "By default this does not mutate raw data. It refreshes factor registry, stock-screen artifacts, and runs a Stock Radar smoke test. External downloaders must be explicitly configured by environment variable.",
              )}
            </Typography.Paragraph>
          </div>
          <div className={styles.metricGrid}>
            <div><span>{t("数据源", "Sources")}</span><strong>{sourceCount}</strong></div>
            <div><span>OK</span><strong>{okCount}</strong></div>
            <div><span>{t("过期", "Stale")}</span><strong>{staleCount}</strong></div>
            <div><span>{t("缺失", "Missing")}</span><strong>{missingCount}</strong></div>
          </div>
        </section>

        <Card title={t("维护选项", "Maintenance Options")}>
          <Space wrap>
            <Checkbox checked={options.dry_run} onChange={(e) => setOptions((v) => ({ ...v, dry_run: e.target.checked }))}>
              {t("仅演练", "Dry run")}
            </Checkbox>
            <Checkbox checked={options.refresh_factor_registry} onChange={(e) => setOptions((v) => ({ ...v, refresh_factor_registry: e.target.checked }))}>
              {t("刷新因子注册表", "Refresh factor registry")}
            </Checkbox>
            <Checkbox checked={options.refresh_stock_screen} onChange={(e) => setOptions((v) => ({ ...v, refresh_stock_screen: e.target.checked }))}>
              {t("刷新股票筛选", "Refresh stock screen")}
            </Checkbox>
            <Checkbox checked={options.run_radar_smoke} onChange={(e) => setOptions((v) => ({ ...v, run_radar_smoke: e.target.checked }))}>
              {t("运行雷达 smoke test", "Run radar smoke test")}
            </Checkbox>
            <Checkbox checked={options.run_external_updater} onChange={(e) => setOptions((v) => ({ ...v, run_external_updater: e.target.checked }))}>
              {t("运行外部更新脚本", "Run external updater")}
            </Checkbox>
          </Space>
        </Card>

        <Card
          title={t("运行门禁", "Run Gate")}
          extra={
            <Tag color={audit?.blocking_status === "BLOCKED" ? "red" : audit?.blocking_status === "WARN" ? "gold" : "green"}>
              {audit?.blocking_status || "UNKNOWN"}
            </Tag>
          }
        >
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            {blockers.length ? (
              <Alert
                type="error"
                showIcon
                message={t("关键数据源会阻断实时运行", "Critical data sources block live runs")}
                description={blockers.map((item) => `${item.source_id}: ${item.reason || item.status}`).join("; ")}
              />
            ) : (
              <Alert
                type={audit?.blocking_status === "WARN" ? "warning" : "success"}
                showIcon
                message={t("没有关键阻断项", "No critical blockers")}
              />
            )}
            {recommendations.length ? (
              <Space wrap>
                {recommendations.map((item) => (
                  <Button
                    key={`${item.source_id}-${item.updater_id}`}
                    size="small"
                    onClick={() => runUpdater(item.updater_id)}
                    loading={runningUpdater === item.updater_id}
                  >
                    {t("运行刷新", "Run updater")}: {item.updater_id}
                  </Button>
                ))}
              </Space>
            ) : null}
            <Typography.Text type="secondary">
              {t("最近报告", "Latest report")}: {visibleRun?.artifacts?.markdown_path || visibleRun?.artifacts?.json_path || "-"}
            </Typography.Text>
          </Space>
        </Card>

        <Card
          title={t("数据地址审计", "Data Path Audit")}
          extra={audit ? <Tag color={statusColor(audit.overall_status)}>{audit.overall_status}</Tag> : null}
        >
          <Table
            rowKey="source_id"
            loading={loading}
            columns={columns}
            dataSource={audit?.sources || []}
            scroll={{ x: 1060 }}
            expandable={{
              expandedRowRender: (record) => (
                <Descriptions size="small" column={2}>
                  <Descriptions.Item label="mtime">{record.mtime || "-"}</Descriptions.Item>
                  <Descriptions.Item label="freshness_days">{record.freshness_days ?? "-"}</Descriptions.Item>
                  <Descriptions.Item label="calendar_count">{record.calendar_count ?? "-"}</Descriptions.Item>
                  <Descriptions.Item label="feature_dir_count">{record.feature_dir_count ?? "-"}</Descriptions.Item>
                  <Descriptions.Item label="package_version">{record.package_version ?? "-"}</Descriptions.Item>
                  <Descriptions.Item label="latest_query">{record.latest_query ? JSON.stringify(record.latest_query) : "-"}</Descriptions.Item>
                  <Descriptions.Item label="freshness_reason" span={2}>
                    {record.freshness_reason || "-"}
                  </Descriptions.Item>
                  <Descriptions.Item label="instrument_counts" span={2}>
                    <Typography.Text>{record.instrument_counts ? JSON.stringify(record.instrument_counts) : "-"}</Typography.Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="available" span={2}>
                    <Typography.Text>{record.available ? JSON.stringify(record.available) : "-"}</Typography.Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="notes" span={2}>
                    {(record.notes || []).join("; ") || "-"}
                  </Descriptions.Item>
                </Descriptions>
              ),
            }}
          />
        </Card>

        {visibleRun ? (
          <Card title={t("最近一次维护结果", "Latest Maintenance Run")} extra={<Tag color={statusColor(visibleRun.overall_status)}>{visibleRun.overall_status}</Tag>}>
            <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
              <Descriptions.Item label="run_id">{visibleRun.run_id}</Descriptions.Item>
              <Descriptions.Item label="generated_at">{visibleRun.generated_at}</Descriptions.Item>
              <Descriptions.Item label="dry_run">{String(visibleRun.dry_run)}</Descriptions.Item>
              <Descriptions.Item label="artifacts">{visibleRun.artifacts?.json_path || "-"}</Descriptions.Item>
            </Descriptions>
            <Table
              size="small"
              rowKey={(record, index) => `${record.name}-${index}`}
              pagination={false}
              dataSource={visibleRun.steps}
              columns={[
                { title: t("步骤", "Step"), dataIndex: "name" },
                { title: t("状态", "Status"), dataIndex: "status", render: (value) => <Tag color={statusColor(String(value))}>{String(value)}</Tag> },
                { title: t("结果", "Result"), render: (_, record) => <Typography.Text>{record.message ? String(record.message) : JSON.stringify(record.result || {})}</Typography.Text> },
              ]}
            />
          </Card>
        ) : null}
      </div>
    </PageContainer>
  );
}
