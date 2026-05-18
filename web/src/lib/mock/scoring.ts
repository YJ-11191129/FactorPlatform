import type { ScoreRow } from "@/types/scoring";

export const mockScoreRows: ScoreRow[] = Array.from({ length: 50 }).map((_, i) => {
  const rank = i + 1;
  const total = 100 - i * 0.6 + (i % 7) * 0.1;
  return {
    symbol: i % 2 === 0 ? `SH60${String(1000 + i).slice(-4)}` : `SZ00${String(1000 + i).slice(-4)}`,
    name: `股票${rank}`,
    industry: ["银行", "电子", "医药", "消费", "周期"][i % 5],
    market_cap: 2e10 + i * 3e8,
    total_score: Math.round(total * 100) / 100,
    rank,
    group: rank <= 10 ? "Top" : rank >= 41 ? "Bottom" : "Mid",
    factor_scores: {
      MOM: Math.round((60 - i) * 100) / 100,
      VALUE: Math.round((40 + (i % 10)) * 100) / 100,
      QUALITY: Math.round((55 - (i % 8)) * 100) / 100,
    },
    risk_tag: rank <= 5 ? ["crowded"] : [],
  };
});

