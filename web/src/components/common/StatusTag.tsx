"use client";

import { Tag } from "antd";
import type { RunStatus } from "@/types/run";

const colorMap: Record<RunStatus, string> = {
  queued: "blue",
  running: "processing",
  success: "green",
  failed: "red",
  cancelled: "default",
};

export function StatusTag(props: { status: RunStatus }) {
  return <Tag color={colorMap[props.status]}>{props.status}</Tag>;
}

