export type NewsItem = {
  title: string;
  link: string;
  published_at?: string;
  source?: string;
};

export type NewsSearchResponse = {
  topic: string;
  source: string;
  request_url: string;
  fetched_at: string;
  items: NewsItem[];
  count: number;
  latency_ms: number;
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
};
