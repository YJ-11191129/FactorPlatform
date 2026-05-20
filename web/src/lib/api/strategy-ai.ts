import { fetchJson } from "@/lib/api/client";
import type {
  GenerateStrategyPayload,
  GenerateStrategyResult,
  LLMProviderStatus,
  RunAiBacktestPayload,
  RunAiBacktestResult,
  StrategySpec,
  StrategyValidationResult,
} from "@/types/strategy-ai";

export async function getStrategyAiProviders(): Promise<LLMProviderStatus> {
  return fetchJson<LLMProviderStatus>("/api/v1/strategy-ai/providers");
}

export async function generateStrategySpec(payload: GenerateStrategyPayload): Promise<GenerateStrategyResult> {
  return fetchJson<GenerateStrategyResult>("/api/v1/strategy-ai/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function validateStrategySpec(spec: StrategySpec): Promise<StrategyValidationResult> {
  return fetchJson<StrategyValidationResult>("/api/v1/strategy-ai/validate", {
    method: "POST",
    body: JSON.stringify({ spec }),
  });
}

export async function runAiBacktest(payload: RunAiBacktestPayload): Promise<RunAiBacktestResult> {
  return fetchJson<RunAiBacktestResult>("/api/v1/strategy-ai/backtest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
