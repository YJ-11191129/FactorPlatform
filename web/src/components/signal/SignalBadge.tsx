"use client";

import { Tag } from "antd";
import type { RiskLevel, Side, SignalStatus } from "@/types/signal-center";

const sideColor: Record<Side, string> = {
  LONG: "green",
  SHORT: "red",
  NEUTRAL: "default",
};

const riskColor: Record<RiskLevel, string> = {
  LOW: "blue",
  MEDIUM: "gold",
  HIGH: "orange",
  BLOCKED: "default",
};

const statusColor: Record<SignalStatus, string> = {
  DRAFT: "default",
  FILTERED: "cyan",
  ACTIVE: "green",
  NOTIFIED: "blue",
  MONITORED: "processing",
  CLOSED: "default",
  BLOCKED: "red",
  INVALIDATED: "magenta",
};

export function SideBadge(props: { value: Side }) {
  return <Tag color={sideColor[props.value]}>{props.value}</Tag>;
}

export function RiskBadge(props: { value: RiskLevel }) {
  return <Tag color={riskColor[props.value]}>{props.value}</Tag>;
}

export function StatusBadge(props: { value: SignalStatus }) {
  return <Tag color={statusColor[props.value]}>{props.value}</Tag>;
}

export function RegimeBadge(props: { value: string }) {
  return <Tag color="purple">{props.value}</Tag>;
}
