"use client";

import { Card } from "antd";
import type { ReactNode } from "react";

export function SectionCard(props: { title: ReactNode; extra?: ReactNode; children: ReactNode; bodyStyle?: React.CSSProperties }) {
  return (
    <Card
      title={props.title}
      extra={props.extra}
      styles={{ body: { padding: 16, ...(props.bodyStyle || {}) } }}
      style={{
        borderRadius: "var(--fp-radius)",
        border: "1px solid var(--fp-border)",
        boxShadow: "var(--fp-shadow)",
        background:
          "linear-gradient(180deg, rgba(22, 36, 58, 0.9), rgba(15, 27, 46, 0.96))",
      }}
    >
      {props.children}
    </Card>
  );
}

