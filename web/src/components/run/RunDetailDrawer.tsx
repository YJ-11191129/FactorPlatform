"use client";

import { Drawer, Space, Spin, Typography } from "antd";

import { JsonViewer } from "@/components/common/JsonViewer";
import { StatusTag } from "@/components/common/StatusTag";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { formatDateTime } from "@/lib/utils/date";
import type { RunItem, RunMeta } from "@/types/run";

export function RunDetailDrawer(props: {
  open: boolean;
  loading?: boolean;
  item?: RunItem | null;
  meta?: RunMeta | null;
  onClose: () => void;
}) {
  const [advancedMode] = useAdvancedMode();

  return (
    <Drawer open={props.open} width={520} onClose={props.onClose} title={advancedMode ? "Run Detail" : "Research Job Detail"} destroyOnClose>
      {props.loading ? (
        <div style={{ paddingTop: 40, textAlign: "center" }}>
          <Spin />
        </div>
      ) : props.item ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {advancedMode ? (
            <div>
              <Typography.Text type="secondary">calc_batch_id</Typography.Text>
              <div>
                <Typography.Text code>{props.item.calc_batch_id}</Typography.Text>
              </div>
            </div>
          ) : null}
          <div>
            <Typography.Text type="secondary">task</Typography.Text>
            <div>{props.item.task_name}</div>
          </div>
          <div>
            <Typography.Text type="secondary">type / status</Typography.Text>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <Typography.Text>{props.item.task_type}</Typography.Text>
              <StatusTag status={props.item.status} />
            </div>
          </div>
          <div style={{ display: "flex", gap: 16 }}>
            <div>
              <Typography.Text type="secondary">submitted_at</Typography.Text>
              <div>{formatDateTime(props.item.submitted_at)}</div>
            </div>
            <div>
              <Typography.Text type="secondary">finished_at</Typography.Text>
              <div>{formatDateTime(props.item.finished_at)}</div>
            </div>
          </div>
          {advancedMode ? (
            <div>
              <Typography.Text type="secondary">meta</Typography.Text>
              <div style={{ border: "1px solid #eef0f4", borderRadius: 12, padding: 12, background: "#fbfcff" }}>
                <JsonViewer value={props.meta || {}} />
              </div>
            </div>
          ) : (
            <Typography.Text type="secondary">Result artifacts are managed by the backend registry.</Typography.Text>
          )}
        </Space>
      ) : (
        <Typography.Text type="secondary">No task selected</Typography.Text>
      )}
    </Drawer>
  );
}
