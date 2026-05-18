"use client";

import { Button, Input, Select, Space, Switch } from "antd";

export type RunFilters = {
  q?: string;
  type?: string;
  status?: string;
  autoRefresh?: boolean;
};

export function RunFilterBar(props: { value: RunFilters; onChange: (v: RunFilters) => void; onRefresh: () => void; loading?: boolean }) {
  return (
    <Space wrap style={{ width: "100%", justifyContent: "space-between" }}>
      <Space wrap>
        <Input.Search
          placeholder="搜索批次 ID / 任务名"
          allowClear
          style={{ width: 280 }}
          value={props.value.q}
          onChange={(e) => props.onChange({ ...props.value, q: e.target.value })}
        />
        <Select
          placeholder="类型"
          allowClear
          style={{ width: 160 }}
          options={[
            { value: "run-demo", label: "run-demo" },
            { value: "run-qlib", label: "run-qlib" },
            { value: "scoring", label: "scoring" },
            { value: "analysis", label: "analysis" },
          ]}
          value={props.value.type}
          onChange={(v) => props.onChange({ ...props.value, type: v })}
        />
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 160 }}
          options={[
            { value: "queued", label: "queued" },
            { value: "running", label: "running" },
            { value: "success", label: "success" },
            { value: "failed", label: "failed" },
            { value: "cancelled", label: "cancelled" },
          ]}
          value={props.value.status}
          onChange={(v) => props.onChange({ ...props.value, status: v })}
        />
        <Space size={8}>
          <Switch checked={!!props.value.autoRefresh} onChange={(v) => props.onChange({ ...props.value, autoRefresh: v })} />
          <span style={{ fontSize: 12, color: "rgba(0,0,0,.65)" }}>自动刷新（15s）</span>
        </Space>
      </Space>
      <Button onClick={props.onRefresh} loading={props.loading}>
        刷新
      </Button>
    </Space>
  );
}

