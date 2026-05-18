"use client";

import { Button, Space, Typography } from "antd";
import { useMemo } from "react";

export function CopyableCodeBlock(props: { code: string }) {
  const text = useMemo(() => props.code || "", [props.code]);

  return (
    <div style={{ border: "1px solid #eef0f4", borderRadius: 12, padding: 12, background: "#fbfcff" }}>
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          code
        </Typography.Text>
        <Button
          size="small"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(text);
            } catch {}
          }}
        >
          Copy
        </Button>
      </Space>
      <pre style={{ margin: "10px 0 0", fontSize: 12, lineHeight: 1.5, overflow: "auto" }}>{text}</pre>
    </div>
  );
}

