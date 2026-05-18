export type OpenBBStatus = {
  status: "READY" | "OPENBB_NOT_READY" | "WARN" | string;
  package_version?: string | null;
  available?: {
    news_world?: boolean;
    news_company?: boolean;
    economy_calendar?: boolean;
  };
  notes?: string[];
  install_hint?: string | null;
  config_path?: string | null;
};

export type OpenBBQueryResponse = {
  query_id: string;
  source: "openbb";
  endpoint: string;
  provider?: string | null;
  fetched_at: string;
  query: Record<string, unknown>;
  items: Array<Record<string, unknown>>;
  count: number;
  warnings: unknown[];
  artifact_path?: string | null;
  research_ops_object_id?: string | null;
};
