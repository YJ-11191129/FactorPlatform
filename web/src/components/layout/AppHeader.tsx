"use client";

import { BellOutlined, SearchOutlined } from "@ant-design/icons";
import { DatePicker, Input, Layout, Select, Space, Tag, Typography } from "antd";
import { useEffect, useState } from "react";

import { mockModeLabel } from "@/lib/api/mockPolicy";
import { listLiveSignals } from "@/lib/api/signal-center";
import styles from "@/components/layout/layout.module.css";

const { Header } = Layout;

export function AppHeader() {
  const [apiState, setApiState] = useState<"checking" | "ok" | "error">("checking");
  const [snapshotStatus, setSnapshotStatus] = useState<string>("NO_SNAPSHOT");
  const [signalDate, setSignalDate] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    listLiveSignals({ page: 1, page_size: 1 })
      .then((res) => {
        if (!alive) return;
        setApiState("ok");
        setSnapshotStatus(res.status || "UNKNOWN");
        setSignalDate(res.signal_date || null);
      })
      .catch(() => {
        if (!alive) return;
        setApiState("error");
        setSnapshotStatus("UNAVAILABLE");
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <Header className={styles.header}>
      <div className={styles.headerInner}>
        <div className={styles.searchCluster}>
          <Input
            prefix={<SearchOutlined />}
            placeholder="Search instrument / signal id / template"
            allowClear
            className={styles.searchInput}
          />
          <Space size={8} className={styles.toolbarFilters} wrap>
            <Select
              className={styles.compactSelect}
              defaultValue="CN"
              options={[
                { value: "CN", label: "CN" },
                { value: "US", label: "US" },
                { value: "Mixed", label: "Mixed" },
              ]}
            />
            <Select
              className={styles.compactSelect}
              defaultValue="30m"
              options={[
                { value: "5m", label: "5m" },
                { value: "15m", label: "15m" },
                { value: "30m", label: "30m" },
                { value: "1D", label: "1D" },
              ]}
            />
            <Tag color={apiState === "ok" ? "green" : apiState === "checking" ? "blue" : "red"}>
              API {apiState.toUpperCase()}
            </Tag>
            <Tag color={mockModeLabel() === "demo" ? "gold" : "default"}>{mockModeLabel().toUpperCase()}</Tag>
            <Tag color={snapshotStatus === "OK" ? "green" : snapshotStatus === "WARN" ? "gold" : "default"}>
              Snapshot {snapshotStatus}{signalDate ? ` ${signalDate}` : ""}
            </Tag>
            <DatePicker.RangePicker className={styles.rangePicker} />
          </Space>
        </div>
        <Space size={10} className={styles.headerActions}>
          <span className={styles.iconButton}>
            <BellOutlined />
          </span>
          <Typography.Text className={styles.researchLabel}>Research</Typography.Text>
        </Space>
      </div>
    </Header>
  );
}
