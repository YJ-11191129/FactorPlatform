import { fetchJson } from "@/lib/api/client";
import type { MacroChainResponse, MacroInputs, MacroTopicReportResponse } from "@/types/macro";

export function generateChainOfImpact(payload: MacroInputs) {
  return fetchJson<MacroChainResponse>("/api/v1/macro/chain-of-impact", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generateTopicReport(payload: MacroInputs) {
  return fetchJson<MacroTopicReportResponse>("/api/v1/macro/topic-report", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

