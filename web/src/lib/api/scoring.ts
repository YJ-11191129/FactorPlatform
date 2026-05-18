import { mockFallbackError, allowMockFallback } from "@/lib/api/mockPolicy";
import { mockScoreRows } from "@/lib/mock/scoring";
import type { ScoreRow } from "@/types/scoring";

export async function getScoreRows(): Promise<ScoreRow[]> {
  if (!allowMockFallback()) throw mockFallbackError("Scoring");
  return mockScoreRows;
}

