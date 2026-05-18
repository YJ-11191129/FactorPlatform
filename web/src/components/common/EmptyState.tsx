"use client";

import { Button, Empty } from "antd";
import type { ReactNode } from "react";

export function EmptyState(props: { title: string; description?: string; actionText?: string; onAction?: () => void; extra?: ReactNode }) {
  return (
    <Empty
      description={
        <div>
          <div style={{ fontWeight: 600 }}>{props.title}</div>
          {props.description ? <div style={{ color: "var(--fp-muted)" }}>{props.description}</div> : null}
        </div>
      }
    >
      {props.actionText && props.onAction ? (
        <Button type="primary" onClick={props.onAction}>
          {props.actionText}
        </Button>
      ) : null}
      {props.extra}
    </Empty>
  );
}

