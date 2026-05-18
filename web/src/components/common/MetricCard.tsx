"use client";

import { Card, Statistic, Typography } from "antd";
import type { ReactNode } from "react";

export function MetricCard(props: {
  title: ReactNode;
  value?: number | string;
  suffix?: ReactNode;
  hint?: ReactNode;
  onClick?: () => void;
}) {
  return (
    <Card
      hoverable={!!props.onClick}
      onClick={props.onClick}
      styles={{ body: { padding: 16 } }}
      style={{
        borderRadius: "var(--fp-radius)",
        cursor: props.onClick ? "pointer" : "default",
        border: "1px solid var(--fp-border)",
        background:
          "linear-gradient(180deg, rgba(22, 36, 58, 0.88), rgba(15, 27, 46, 0.94))",
        boxShadow: "var(--fp-shadow)",
      }}
    >
      <Statistic title={props.title} value={props.value ?? "-"} suffix={props.suffix} />
      {props.hint ? (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {props.hint}
        </Typography.Text>
      ) : null}
    </Card>
  );
}

