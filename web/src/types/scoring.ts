export type ScoreRow = {
  symbol: string;
  name: string;
  industry?: string;
  market_cap?: number;
  total_score: number;
  rank: number;
  group?: string;
  factor_scores?: Record<string, number>;
  risk_tag?: string[];
};

