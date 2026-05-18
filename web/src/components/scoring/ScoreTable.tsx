"use client";

import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { ScoreRow } from "@/types/scoring";

export function ScoreTable(props: { loading?: boolean; data: ScoreRow[] }) {
  const columns: ColumnsType<ScoreRow> = [
    { title: "Symbol", dataIndex: "symbol", key: "symbol", width: 120, fixed: "left" },
    { title: "Name", dataIndex: "name", key: "name", width: 140 },
    { title: "Industry", dataIndex: "industry", key: "industry", width: 140 },
    {
      title: "Market Cap",
      dataIndex: "market_cap",
      key: "market_cap",
      width: 130,
      render: (value?: number) => (typeof value === "number" ? `${Math.round(value / 1e8)}e8` : "-"),
    },
    { title: "Score", dataIndex: "total_score", key: "total_score", width: 90 },
    { title: "Rank", dataIndex: "rank", key: "rank", width: 90, sorter: (a, b) => a.rank - b.rank },
    { title: "Group", dataIndex: "group", key: "group", width: 90 },
    {
      title: "Risk Tags",
      dataIndex: "risk_tag",
      key: "risk_tag",
      width: 180,
      render: (tags?: string[]) => (tags || []).map((tag) => <Tag key={tag}>{tag}</Tag>),
    },
  ];

  return (
    <Table
      size="middle"
      rowKey={(row) => row.symbol}
      loading={props.loading}
      dataSource={props.data}
      columns={columns}
      scroll={{ x: 1000 }}
      pagination={{ pageSize: 20 }}
      expandable={{
        expandedRowRender: (row) => (
          <pre style={{ margin: 0, fontSize: 12, lineHeight: 1.5 }}>{JSON.stringify(row.factor_scores || {}, null, 2)}</pre>
        ),
      }}
    />
  );
}
