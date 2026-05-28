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
        boxShadow: "0 12px 30px rgba(15, 23, 42, 0.05)",
        background: "var(--fp-surface)",
      }}
    >
      {props.children}
    </Card>
  );
}

