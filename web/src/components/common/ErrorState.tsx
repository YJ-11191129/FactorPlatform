"use client";

import { Button, Result } from "antd";
import type { ReactNode } from "react";

export function ErrorState(props: { title: string; subtitle?: string; extra?: ReactNode; onRetry?: () => void }) {
  return (
    <Result
      status="error"
      title={props.title}
      subTitle={props.subtitle}
      extra={
        props.extra ? (
          props.extra
        ) : props.onRetry ? (
          <Button type="primary" onClick={props.onRetry}>
            Retry
          </Button>
        ) : null
      }
    />
  );
}
