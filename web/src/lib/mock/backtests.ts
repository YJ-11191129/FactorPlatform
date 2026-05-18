import type { BacktestSummary, EquityCurve } from "@/types/backtest";
import type { StrategyInfo } from "@/types/strategy";

export const mockStrategies: StrategyInfo[] = [
  {
    strategy_id: "stg_mom_ma_v1",
    strategy_name: "Momentum + MA Bias (Demo)",
    description: "Demo strategy: equal-weight top momentum by last return.",
    version: "v1",
    owner: "research",
    parameter_schema: {
      topk: { type: "int", default: 10, min: 1 },
    },
    python_entry: "app.strategies.builtins.mom_ma_v1:MomMaV1Strategy",
  },
];

export const mockBacktests: BacktestSummary[] = [];

export const mockEquityCurve: EquityCurve = {
  row_count: 30,
  items: Array.from({ length: 30 }).map((_, i) => {
    const d = new Date(Date.now() - (29 - i) * 24 * 3600 * 1000);
    const trade_date = d.toISOString().slice(0, 10);
    const equity = 1_000_000 * (1 + 0.002 * Math.sin(i / 5) - 0.001 * Math.cos(i / 7)) * (1 + i * 0.0005);
    return {
      trade_date,
      equity: Math.round(equity * 100) / 100,
      net_ret: i === 0 ? 0 : Math.round(((equity / (1_000_000 * (1 + (i - 1) * 0.0005))) - 1) * 1e6) / 1e6,
    };
  }),
};

