"use client";

import { Progress, Space, Typography } from "antd";

export function ConfidenceBar(props: { value: number }) {
  const percent = Math.round(props.value * 100);
  const status = percent >= 80 ? "success" : percent >= 60 ? "normal" : "exception";
  return (
    <Space direction="vertical" size={2} style={{ width: "100%" }}>
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          Confidence
        </Typography.Text>
        <Typography.Text style={{ fontSize: 12 }}>{percent}%</Typography.Text>
      </Space>
      <Progress percent={percent} size="small" status={status as any} showInfo={false} />
    </Space>
  );
}
