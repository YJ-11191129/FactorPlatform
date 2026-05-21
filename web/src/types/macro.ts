export type MacroInputs = {
  topic: string;
  event?: string | null;
  region?: string | null;
  horizon?: string | null;
};

export type MacroSeriesSummary = {
  points?: number;
  start?: string;
  end?: string;
  first?: number;
  last?: number;
  change?: number;
  change_pct?: number | null;
};

export type MacroContext = {
  topic?: string;
  event?: string | null;
  region?: string | null;
  horizon?: string | null;
  generated_at?: string;
  data_sources?: Record<string, unknown>;
  topic_registry?: {
    topic?: string;
    related_assets?: Array<{ asset_name: string; wind_code: string }>;
  };
  signals?: Record<string, MacroSeriesSummary>;
  notes?: string[];
};

export type MacroChainResult = {
  regime_hypothesis?: string;
  cause?: string[];
  transmission?: Array<{ step?: string; channel?: string; who?: string; timeframe?: string }>;
  impact?: {
    assets?: Array<{ name?: string; direction?: "up" | "down" | "mixed" | string; confidence?: number }>;
    sectors?: Array<{ name?: string; direction?: "up" | "down" | "mixed" | string; confidence?: number }>;
    signals_to_watch?: string[];
  };
  risks?: string[];
  assumptions?: string[];
  confidence?: number;
  error?: string;
  text?: string;
};

export type MacroTopicReportResult = {
  executive_summary?: string;
  drivers?: string[];
  supply_chain?: Array<{ node?: string; notes?: string }>;
  regional_supply_demand?: Array<{ region?: string; balance?: string; notes?: string }>;
  geopolitics?: string[];
  logistics_storage?: string[];
  market_dashboard?: Array<{ metric?: string; value?: string; interpretation?: string }>;
  watchlist?: string[];
  disclaimer?: string;
  error?: string;
  text?: string;
};

export type MacroLLMProvider = {
  provider?: string;
  model?: string;
  endpoint?: string;
  ready?: boolean;
  reason?: string | null;
};

export type MacroChainResponse = {
  inputs: MacroInputs;
  context: MacroContext;
  result: MacroChainResult | Record<string, unknown>;
  llm_ready: boolean;
  llm_provider?: MacroLLMProvider;
};

export type MacroTopicReportResponse = {
  inputs: MacroInputs;
  context: MacroContext;
  result: MacroTopicReportResult | Record<string, unknown>;
  llm_ready: boolean;
  llm_provider?: MacroLLMProvider;
};
