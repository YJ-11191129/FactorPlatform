"use client";

import { Progress, Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";

type Tone = "positive" | "negative" | "neutral" | "warning";

const toneColor: Record<Tone, string> = {
  positive: "#0f9f8f",
  negative: "#ef4444",
  neutral: "#64748b",
  warning: "#f59e0b",
};

export function SignalGauge(props: {
  label: ReactNode;
  value: number;
  tone?: Tone;
  caption?: ReactNode;
}) {
  const tone = props.tone || "neutral";
  return (
    <div
      style={{
        display: "grid",
        justifyItems: "center",
        gap: 8,
        minHeight: 148,
        padding: 16,
        border: "1px solid var(--fp-border)",
        borderRadius: "var(--fp-radius)",
        background: "linear-gradient(180deg, rgba(248,250,252,0.95), rgba(241,245,249,0.72))",
      }}
    >
      <Progress
        type="dashboard"
        percent={Math.max(0, Math.min(100, Math.round(props.value)))}
        strokeColor={toneColor[tone]}
        trailColor="rgba(100,116,139,0.16)"
        size={92}
      />
      <Typography.Text strong style={{ color: "#0f172a" }}>
        {props.label}
      </Typography.Text>
      {props.caption ? (
        <Typography.Text type="secondary" style={{ fontSize: 12, textAlign: "center" }}>
          {props.caption}
        </Typography.Text>
      ) : null}
    </div>
  );
}

export function RiskMeter(props: {
  label: ReactNode;
  value: number;
  status?: ReactNode;
  tone?: Tone;
}) {
  const tone = props.tone || "neutral";
  return (
    <div
      style={{
        display: "grid",
        gap: 8,
        padding: 14,
        border: "1px solid var(--fp-border)",
        borderRadius: "var(--fp-radius)",
        background: "rgba(248,250,252,0.78)",
      }}
    >
      <Space style={{ justifyContent: "space-between", width: "100%" }}>
        <Typography.Text strong>{props.label}</Typography.Text>
        {props.status ? <Tag color={tone === "negative" ? "red" : tone === "warning" ? "gold" : tone === "positive" ? "green" : "default"}>{props.status}</Tag> : null}
      </Space>
      <Progress percent={Math.max(0, Math.min(100, Math.round(props.value)))} showInfo={false} strokeColor={toneColor[tone]} trailColor="rgba(100,116,139,0.16)" />
    </div>
  );
}

export function MiniTrend(props: {
  points?: number[];
  tone?: Tone;
  height?: number;
}) {
  const values = props.points?.length ? props.points : [42, 46, 44, 51, 49, 55, 61, 58, 64, 68, 66, 72];
  const width = 180;
  const height = props.height || 54;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const scale = max === min ? 1 : max - min;
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * (width - 8) + 4;
      const y = height - 6 - ((value - min) / scale) * (height - 12);
      return `${x},${y}`;
    })
    .join(" ");
  const tone = props.tone || "positive";

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="趋势线">
      <polyline points={points} fill="none" stroke={toneColor[tone]} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <polygon points={`${points} ${width - 4},${height - 2} 4,${height - 2}`} fill={toneColor[tone]} opacity="0.1" />
    </svg>
  );
}

export function FactorContributionBars(props: {
  items: Array<{ label: ReactNode; value: number; tone?: Tone }>;
}) {
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {props.items.map((item, index) => {
        const tone = item.tone || (item.value >= 0 ? "positive" : "negative");
        return (
          <div key={index} style={{ display: "grid", gap: 5 }}>
            <Space style={{ justifyContent: "space-between", width: "100%" }}>
              <Typography.Text>{item.label}</Typography.Text>
              <Typography.Text strong style={{ color: toneColor[tone] }}>
                {item.value.toFixed(2)}
              </Typography.Text>
            </Space>
            <Progress percent={Math.min(100, Math.abs(item.value) * 100)} showInfo={false} strokeColor={toneColor[tone]} trailColor="rgba(100,116,139,0.14)" />
          </div>
        );
      })}
    </div>
  );
}
