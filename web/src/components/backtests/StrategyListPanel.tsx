"use client";

import { Card, Input, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState } from "react";

import type { StrategyInfo } from "@/types/strategy";

export function StrategyListPanel(props: {
  loading?: boolean;
  strategies: StrategyInfo[];
  selectedId?: string | null;
  onSelect: (strategy: StrategyInfo) => void;
}) {
  const [q, setQ] = useState("");
  const [owner, setOwner] = useState<string | undefined>(undefined);

  const owners = useMemo(() => {
    const set = new Set(props.strategies.map((s) => s.owner).filter(Boolean));
    return Array.from(set).sort();
  }, [props.strategies]);

  const data = useMemo(() => {
    const kw = q.trim().toLowerCase();
    return props.strategies.filter((s) => {
      if (owner && s.owner !== owner) return false;
      if (!kw) return true;
      const hay = `${s.strategy_id} ${s.strategy_name} ${s.description}`.toLowerCase();
      return hay.includes(kw);
    });
  }, [props.strategies, q, owner]);

  const columns: ColumnsType<StrategyInfo> = [
    { title: "ID", dataIndex: "strategy_id", key: "strategy_id", width: 160 },
    {
      title: "策略",
      dataIndex: "strategy_name",
      key: "strategy_name",
      render: (v: string, r) => (
        <div>
          <Typography.Text strong>{v}</Typography.Text>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {r.description || "-"}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    { title: "版本", dataIndex: "version", key: "version", width: 90 },
    { title: "Owner", dataIndex: "owner", key: "owner", width: 120 },
  ];

  return (
    <Card
      title={
        <Space>
          <span>策略列表</span>
          <Tag color="blue">{data.length}</Tag>
        </Space>
      }
      extra={
        <Space>
          <Select
            allowClear
            placeholder="Owner"
            value={owner}
            onChange={(v) => setOwner(v)}
            options={owners.map((o) => ({ label: o, value: o }))}
            style={{ width: 140 }}
          />
          <Input placeholder="搜索" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 220 }} />
        </Space>
      }
    >
      <Table
        size="middle"
        rowKey={(r) => r.strategy_id}
        loading={props.loading}
        dataSource={data}
        columns={columns}
        pagination={{ pageSize: 8 }}
        rowSelection={{
          type: "radio",
          selectedRowKeys: props.selectedId ? [props.selectedId] : [],
          onSelect: (record) => props.onSelect(record),
        }}
        onRow={(record) => ({
          onClick: () => props.onSelect(record),
        })}
      />
    </Card>
  );
}
