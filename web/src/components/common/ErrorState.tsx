"use client";

import { Button, Result } from "antd";

export function ErrorState(props: { title: string; subtitle?: string; onRetry?: () => void }) {
  return (
    <Result
      status="error"
      title={props.title}
      subTitle={props.subtitle}
      extra={
        props.onRetry ? (
          <Button type="primary" onClick={props.onRetry}>
            Retry
          </Button>
        ) : null
      }
    />
  );
}
