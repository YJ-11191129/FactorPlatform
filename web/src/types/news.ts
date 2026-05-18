export type NewsItem = {
  title: string;
  link: string;
  published_at?: string;
  source?: string;
  provider?: string | null;
  openbb_endpoint?: string | null;
  extra?: Record<string, unknown>;
};

export type NewsSearchResponse = {
  topic: string;
  source: string;
  request_url: string;
  fetched_at: string;
  items: NewsItem[];
  count: number;
  latency_ms: number;
  endpoint?: string | null;
  provider?: string | null;
  warnings?: unknown[];
  artifact_path?: string | null;
  research_ops_object_id?: string | null;
};

export type NewsSummary = {
  highlights: string[];
  sources: Record<string, number>;
};

export type NewsSummaryResponse = {
  topic: string;
  fetched_at: string;
  count: number;
  summary: NewsSummary;
  items: NewsItem[];
  source?: string;
  endpoint?: string | null;
  provider?: string | null;
  warnings?: unknown[];
  artifact_path?: string | null;
  research_ops_object_id?: string | null;
};
