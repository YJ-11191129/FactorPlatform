"use client";

import { Button, Dropdown, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";

import type { FactorItem } from "@/types/factor";

export function FactorTable(props: {
  loading?: boolean;
  data: FactorItem[];
  onRunDemo: (factorName: string) => void;
  onRunQlib: (factorName: string) => void;
}) {
  const columns: ColumnsType<FactorItem> = [
    {
      title: "因子名",
      dataIndex: "factor_name",
      key: "factor_name",
      render: (v: string) => (
        <Link href={`/factors/${encodeURIComponent(v)}`}>
          <Typography.Text code>{v}</Typography.Text>
        </Link>
      ),
      width: 260,
      fixed: "left",
    },
    { title: "中文名", dataIndex: "display_name", key: "display_name", width: 180 },
    { title: "分类", dataIndex: "category", key: "category", width: 110 },
    {
      title: "标签",
      dataIndex: "tags",
      key: "tags",
      render: (tags: string[]) => (tags || []).slice(0, 3).map((t) => <Tag key={t}>{t}</Tag>),
      width: 160,
    },
    { title: "频率", dataIndex: "frequency", key: "frequency", width: 90 },
    {
      title: "覆盖率",
      dataIndex: "coverage",
      key: "coverage",
      width: 90,
      render: (v?: number) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "-"),
    },
    {
      title: "IC 均值",
      dataIndex: "ic_mean",
      key: "ic_mean",
      width: 90,
      render: (v?: number) => (typeof v === "number" ? v.toFixed(3) : "-"),
    },
    {
      title: "RankIC",
      dataIndex: "rank_ic",
      key: "rank_ic",
      width: 90,
      render: (v?: number) => (typeof v === "number" ? v.toFixed(3) : "-"),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 90,
      render: (v: string) => <Tag color={v === "online" ? "green" : v === "research" ? "blue" : "default"}>{v}</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 220,
      render: (_, r) => (
        <Space>
          <Button size="small" onClick={() => props.onRunDemo(r.factor_name)}>
            运行 Demo
          </Button>
          <Button size="small" onClick={() => props.onRunQlib(r.factor_name)}>
            运行 Qlib
          </Button>
          <Dropdown
            menu={{
              items: [
                { key: "copy", label: "复制因子名" },
                { key: "runs", label: "查看运行记录（预留）" },
              ],
              onClick: async ({ key }) => {
                if (key === "copy") {
                  try {
                    await navigator.clipboard.writeText(r.factor_name);
                  } catch {}
                }
              },
            }}
          >
            <Button size="small">更多</Button>
          </Dropdown>
        </Space>
      ),
    },
  ];

  return (
    <Table
      size="middle"
      rowKey={(r) => r.factor_id}
      loading={props.loading}
      dataSource={props.data}
      columns={columns}
      scroll={{ x: 1200 }}
      pagination={{ pageSize: 20 }}
    />
  );
}

