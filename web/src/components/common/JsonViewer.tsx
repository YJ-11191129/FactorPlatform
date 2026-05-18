"use client";

import { Typography } from "antd";

export function JsonViewer(props: { value: unknown }) {
  return (
    <Typography.Paragraph style={{ margin: 0 }}>
      <pre style={{ margin: 0, fontSize: 12, lineHeight: 1.5, overflow: "auto" }}>{JSON.stringify(props.value, null, 2)}</pre>
    </Typography.Paragraph>
  );
}

