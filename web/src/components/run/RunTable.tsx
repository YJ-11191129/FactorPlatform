"use client";

import { Button, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import { StatusTag } from "@/components/common/StatusTag";
import { formatDateTime } from "@/lib/utils/date";
import type { RunItem } from "@/types/run";

export function RunTable(props: {
  loading?: boolean;
  data: RunItem[];
  onOpen: (item: RunItem) => void;
  onDownload: (id: string) => void;
  onLineage?: (id: string) => void;
}) {
  const columns: ColumnsType<RunItem> = [
    {
      title: "Batch ID",
      dataIndex: "calc_batch_id",
      key: "calc_batch_id",
      width: 260,
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    { title: "Task", dataIndex: "task_name", key: "task_name", width: 200 },
    { title: "Type", dataIndex: "task_type", key: "task_type", width: 110 },
    {
      title: "Submitted",
      dataIndex: "submitted_at",
      key: "submitted_at",
      width: 170,
      render: (v: string) => formatDateTime(v),
    },
    {
      title: "Finished",
      dataIndex: "finished_at",
      key: "finished_at",
      width: 170,
      render: (v?: string) => formatDateTime(v),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (v: RunItem["status"]) => <StatusTag status={v} />,
    },
    {
      title: "Actions",
      key: "actions",
      width: 250,
      render: (_, r) => (
        <Space>
          <Button
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              props.onOpen(r);
            }}
          >
            Detail
          </Button>
          <Button
            size="small"
            disabled={r.status !== "success"}
            onClick={(event) => {
              event.stopPropagation();
              props.onDownload(r.calc_batch_id);
            }}
          >
            Download
          </Button>
          <Button
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              props.onLineage?.(r.calc_batch_id);
            }}
          >
            Lineage
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Table
      size="middle"
      rowKey={(r) => r.calc_batch_id}
      loading={props.loading}
      dataSource={props.data}
      columns={columns}
      onRow={(record) => ({
        onClick: () => props.onOpen(record),
      })}
      pagination={{ pageSize: 20 }}
      scroll={{ x: 1300 }}
    />
  );
}

