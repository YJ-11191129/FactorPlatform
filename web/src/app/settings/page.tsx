"use client";

import { Button, Card, Input, Space, Typography, message } from "antd";
import { useEffect, useState } from "react";

const KEY = "FP_API_KEY";

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    setApiKey(window.localStorage.getItem(KEY) || "");
  }, []);

  function save() {
    window.localStorage.setItem(KEY, apiKey.trim());
    message.success("Saved. Reload pages to take effect.");
  }

  function clear() {
    window.localStorage.removeItem(KEY);
    setApiKey("");
    message.success("Cleared.");
  }

  return (
    <Card style={{ maxWidth: 720 }}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        Settings
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        Configure API Key used for calling backend endpoints.
      </Typography.Paragraph>

      <Space direction="vertical" style={{ width: "100%" }} size={12}>
        <Input.Password
          placeholder="X-API-Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        <Space>
          <Button type="primary" onClick={save}>
            Save
          </Button>
          <Button onClick={clear}>Clear</Button>
        </Space>
      </Space>
    </Card>
  );
}

