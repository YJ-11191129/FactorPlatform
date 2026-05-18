import type { FactorDetail, FactorItem } from "@/types/factor";

export const mockFactors: FactorItem[] = [
  {
    factor_id: "MOM_RET_20_D_V1",
    factor_name: "MOM_RET_20_D_V1",
    display_name: "20日动量收益",
    category: "MOM",
    tags: ["momentum"],
    frequency: "daily",
    market_scope: ["CN-A"],
    direction: "positive",
    coverage: 0.92,
    missing_rate: 0.03,
    ic_mean: 0.031,
    rank_ic: 0.028,
    latest_run_at: "2026-03-20T10:12:26Z",
    status: "research",
    owner: "research",
    version: "V1",
  },
  {
    factor_id: "TREND_MA_BIAS_20_D_V1",
    factor_name: "TREND_MA_BIAS_20_D_V1",
    display_name: "均线乖离率",
    category: "TREND",
    tags: ["trend"],
    frequency: "daily",
    market_scope: ["CN-A"],
    direction: "unknown",
    coverage: 0.95,
    missing_rate: 0.02,
    ic_mean: 0.012,
    rank_ic: 0.010,
    latest_run_at: "2026-03-20T10:12:26Z",
    status: "research",
    owner: "research",
    version: "V1",
  },
];

export const mockFactorDetail: Record<string, FactorDetail> = {
  MOM_RET_20_D_V1: {
    ...mockFactors[0],
    description: "过去 N 日收益率，用于动量/反转研究。",
    formula: "close / close.shift(N) - 1",
    data_source: ["qlib_bin"],
    neutralization: ["industry", "mktcap"],
    winsorize: "MAD 5x",
    standardize: "CS z-score",
    dependencies: ["daily_bar.trade_date", "daily_bar.asset_code", "daily_bar.close"],
    code_snippet: "MOM = close / close.shift(N) - 1",
    diagnostics: { skew: 0.2, kurtosis: 2.1, turnover: 0.35 },
  },
};

