import fs from "node:fs";
import { NextResponse } from "next/server";

import roadshowFixtures from "@/lib/demo/roadshow-fixtures.json";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RoadshowStrategySpec = typeof roadshowFixtures.strategy_ai.spec;

function json(data: unknown, status = 200) {
  return new NextResponse(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function nowIso() {
  return new Date().toISOString();
}

function paginated<T>(items: T[], page = 1, pageSize = items.length) {
  return {
    items,
    page,
    page_size: pageSize,
    total: items.length,
    has_more: false,
  };
}

function roadshowValidation(spec: RoadshowStrategySpec = roadshowFixtures.strategy_ai.spec) {
  return {
    ...roadshowFixtures.strategy_ai.validation,
    normalized_spec: spec,
  };
}

function roadshowGeneratedStrategy() {
  const spec = roadshowFixtures.strategy_ai.spec;
  return {
    spec,
    validation: roadshowValidation(spec),
    provider: "roadshow",
    llm_ready: false,
    used_fallback: true,
    raw_model_output: null,
  };
}

function roadshowBacktestResult() {
  return {
    backtest_id: "roadshow_ai_bt_001",
    created_at: nowIso(),
    summary: {
      ...roadshowFixtures.strategy_ai.backtest_summary,
      strategy_id: "roadshow_ai_strategy",
      strategy_name: roadshowFixtures.strategy_ai.spec.name,
      initial_cash: 1000000,
      fee_bps: roadshowFixtures.strategy_ai.spec.execution.fee_bps,
      use_adj: true,
      universe_size: 300,
      data_health: {
        blocking_status: "WARN",
        message: "Roadshow mode uses checked-in synthetic fixture data. Validate with production data before research use.",
        source_id: "roadshow_fixture",
      },
    },
    validation: roadshowValidation(),
    data_health: {
      blocking_status: "WARN",
      message: "Roadshow mode uses checked-in synthetic fixture data. Validate with production data before research use.",
      source_id: "roadshow_fixture",
    },
  };
}

function roadshowMacroContext(topic: string | null, event: string | null, region: string | null, horizon: string | null) {
  return {
    topic: topic || "market regime",
    event: event || undefined,
    region: region || "CN",
    horizon: horizon || "weeks",
    generated_at: nowIso(),
    data_sources: { fixture: roadshowFixtures.meta.data_source },
    notes: [roadshowFixtures.meta.disclaimer],
  };
}

function roadshowTopic(search: URLSearchParams) {
  return search.get("topic") || "market regime";
}

function mockResponse(pathname: string, search: URLSearchParams): NextResponse | null {
  const baseNow = nowIso();
  if (pathname === "/health") {
    return json({
      status: "ok",
      version: "demo-fallback",
      mode: "DEMO_FALLBACK",
      data_source: "mock",
    });
  }

  if (pathname === "/api/v1/strategy-ai/providers") {
    return json({
      default_provider: "roadshow",
      providers: [
        {
          name: "roadshow",
          model: "checked-in-fixture",
          endpoint: "demo://roadshow",
          ready: true,
          reason: "Read-only roadshow fixture; live LLM providers are not required.",
        },
      ],
    });
  }

  if (pathname === "/api/v1/strategy-ai/generate") {
    return json(roadshowGeneratedStrategy());
  }

  if (pathname === "/api/v1/strategy-ai/validate") {
    return json(roadshowValidation());
  }

  if (pathname === "/api/v1/strategy-ai/backtest") {
    return json(roadshowBacktestResult());
  }

  if (pathname === "/api/v1/macro/chain-of-impact") {
    const topic = roadshowTopic(search);
    return json({
      inputs: { topic, event: search.get("event"), region: search.get("region") || "CN", horizon: search.get("horizon") || "weeks" },
      context: roadshowMacroContext(topic, search.get("event"), search.get("region"), search.get("horizon")),
      llm_ready: false,
      llm_provider: { provider: "roadshow", model: "checked-in-fixture", endpoint: "demo://roadshow", ready: true },
      result: roadshowFixtures.macro.chain,
    });
  }

  if (pathname === "/api/v1/macro/topic-report") {
    const topic = roadshowTopic(search);
    return json({
      inputs: { topic, event: search.get("event"), region: search.get("region") || "CN", horizon: search.get("horizon") || "weeks" },
      context: roadshowMacroContext(topic, search.get("event"), search.get("region"), search.get("horizon")),
      llm_ready: false,
      llm_provider: { provider: "roadshow", model: "checked-in-fixture", endpoint: "demo://roadshow", ready: true },
      result: roadshowFixtures.macro.report,
    });
  }

  if (pathname === "/api/v1/news/search" || pathname === "/api/v1/news/summary") {
    const topic = roadshowTopic(search);
    return json({
      topic,
      source: "roadshow_fixture",
      request_url: "",
      fetched_at: baseNow,
      items: roadshowFixtures.macro.news.items,
      count: roadshowFixtures.macro.news.items.length,
      latency_ms: 0,
      warnings: [roadshowFixtures.meta.disclaimer],
      summary: {
        highlights: roadshowFixtures.macro.news.highlights,
        sources: { "Roadshow public-news fixture": roadshowFixtures.macro.news.items.length },
      },
    });
  }

  if (pathname === "/api/factors/run-demo") {
    return json({
      factor_name: "ROADSHOW_FACTOR_SCREEN",
      row_count: roadshowFixtures.factors.run_preview.length,
      columns: ["trade_date", "asset_code", "factor_value", "rank"],
      preview: roadshowFixtures.factors.run_preview,
      message: "Roadshow fixture data; read-only synthetic sample.",
      calc_batch_id: "roadshow_factor_run_001",
      download_url: null,
    });
  }

  if (pathname === "/api/data-maintenance/latest") {
    return json({
      generated_at: baseNow,
      overall_status: "DEMO_FALLBACK",
      audit: {
        blocking_status: "WARN",
        blockers: [],
        recommendations: [],
        sources: [
          {
            source_id: "qlib_cn_daily",
            label: "Qlib CN daily provider",
            status: "DEMO",
            end_date: "demo",
            notes: ["Demo fallback is read-only and does not inspect local qlib files."],
          },
          {
            source_id: "qlib_us_daily",
            label: "Qlib US daily provider",
            status: "DEMO",
            end_date: "demo",
            notes: ["Demo fallback is read-only and does not inspect local qlib files."],
          },
        ],
      },
    });
  }

  if (pathname === "/api/data-maintenance/paths") {
    return json({
      sources: [
        { source_id: "qlib_cn_daily", label: "Qlib CN daily provider", status: "DEMO", path: "demo://qlib-cn" },
        { source_id: "qlib_us_daily", label: "Qlib US daily provider", status: "DEMO", path: "demo://qlib-us" },
      ],
    });
  }

  if (pathname === "/api/qlib/status") {
    return json({
      status: "DEMO_FALLBACK",
      provider_uri: "demo://qlib",
      universe: "csi300",
      notes: ["Native qlib mining is disabled in read-only demo fallback."],
    });
  }

  if (pathname === "/api/strategies") {
    return json([
      {
        strategy_id: "demo_momentum_v1",
        strategy_name: "Demo Momentum Rotation",
        description: "Read-only demo strategy using delayed daily momentum signals.",
        version: "v1",
        owner: "demo",
        parameter_schema: {
          topk: { type: "int", default: 10, min: 1, max: 50 },
          lookback: { type: "int", default: 20, min: 2, max: 120 },
        },
        python_entry: "demo://readonly",
      },
    ]);
  }

  if (pathname === "/api/backtests/data-status") {
    return json({
      source: "demo://qlib",
      columns: ["trade_date", "asset_code", "open", "high", "low", "close", "volume"],
      start_date: "2020-01-01",
      end_date: "demo",
      asset_count: 300,
      row_count: 120000,
      data_health: {
        blocking_status: "WARN",
        message: "Demo fallback uses mock read-only backtest data.",
        source_id: "demo_qlib",
      },
    });
  }

  if (pathname === "/api/backtests") {
    return json([
      {
        backtest_id: "demo_bt_001",
        created_at: baseNow,
        strategy_id: "demo_momentum_v1",
        strategy_name: "Demo Momentum Rotation",
        portfolio_id: null,
        params: { topk: 10, lookback: 20 },
        initial_cash: 1000000,
        fee_bps: 5,
        use_adj: true,
        universe_size: 300,
        metrics: {
          total_return: 0.084,
          annual_return: 0.112,
          annual_vol: 0.176,
          sharpe: 0.88,
          max_drawdown: -0.061,
          avg_daily_turnover: 0.18,
          total_transaction_cost: 4200,
        },
        price_data_source: { kind: "qlib", source_id: "demo_qlib", region: "cn", provider_uri: "demo://qlib" },
        timing_note: "Demo signals use one-bar delayed execution.",
        execution_model: {
          signal_timestamp: "close_t",
          execution_delay: "one_bar",
          return_alignment: "positions from t-1 are applied to close-to-close returns on t",
          cost_model: "5 bps applied to one-way turnover",
        },
        diagnostics: {
          price_start_date: "2026-04-01",
          price_end_date: "2026-05-21",
          simulated_asset_count: 300,
          normalized_position_rows: 3000,
        },
        data_health: {
          blocking_status: "WARN",
          message: "Demo fallback uses mock read-only backtest data.",
          source_id: "demo_qlib",
        },
      },
    ]);
  }

  if (pathname.startsWith("/api/backtests/") && pathname.endsWith("/equity")) {
    const items = Array.from({ length: 40 }).map((_, i) => {
      const d = new Date(Date.UTC(2026, 3, 1 + i));
      const equity = 1000000 * (1 + i * 0.002 + Math.sin(i / 4) * 0.006);
      return {
        trade_date: d.toISOString().slice(0, 10),
        equity: Math.round(equity * 100) / 100,
        gross_ret: i === 0 ? 0 : 0.002 + Math.cos(i / 4) * 0.0015,
        turnover: i % 5 === 0 ? 0.22 : 0.04,
        cost: i % 5 === 0 ? 0.00011 : 0.00002,
        net_ret: i === 0 ? 0 : 0.0019 + Math.cos(i / 4) * 0.0015,
      };
    });
    return json({ items, row_count: items.length });
  }

  if (pathname === "/api/v1/metadata/enums") {
    return json({
      side: ["LONG", "SHORT", "NEUTRAL"],
      risk_level: ["LOW", "MEDIUM", "HIGH", "BLOCKED"],
      status: ["DRAFT", "FILTERED", "ACTIVE", "NOTIFIED", "MONITORED", "CLOSED", "BLOCKED", "INVALIDATED"],
      market: ["CN"],
      asset_type: ["ETF", "INDEX", "STOCK"],
      timeframe: ["5m", "30m", "1D"],
      volatility_state: ["NORMAL_VOL", "HIGH_VOL", "EXTREME_VOL", "UNKNOWN"],
      tail_risk_state: ["NORMAL", "ELEVATED", "STRESSED", "EXTREME", "UNKNOWN"],
    });
  }

  if (pathname === "/api/v1/signals/live" || pathname === "/api/v1/signals/shadow" || pathname === "/api/v1/signals/history") {
    const items = [
      {
        signal_id: "sig_20260329_0001",
        instrument: "510300.SH",
        market: "CN",
        asset_type: "ETF",
        timeframe: "30m",
        side: "LONG",
        signal_time: "2026-03-29T10:00:00+08:00",
        entry_type: "MARKET_ON_BAR_OPEN",
        entry_price: 4.182,
        stop_loss: 4.12,
        take_profit: 4.315,
        confidence: 0.81,
        risk_level: "MEDIUM",
        regime_label: "POST_SHOCK_REBOUND",
        volatility_state: "HIGH_VOL",
        tail_risk_state: "ELEVATED",
        position_scale: 0.65,
        reason_tags: ["post_shock_rebound", "liquidity_recovery_confirmed", "vrp_normalizing"],
        status: "ACTIVE",
        signal_template: "POST_SHOCK_REBOUND_LONG_V1",
        expected_holding_bars: 8,
        created_at: "2026-03-29T10:00:01+08:00",
        updated_at: "2026-03-29T10:00:01+08:00",
      },
      {
        signal_id: "sig_20260329_0002",
        instrument: "510500.SH",
        market: "CN",
        asset_type: "ETF",
        timeframe: "30m",
        side: "SHORT",
        signal_time: "2026-03-29T10:30:00+08:00",
        entry_type: "LIMIT_NEAR_VWAP",
        entry_price: 5.031,
        stop_loss: 5.115,
        take_profit: 4.902,
        confidence: 0.74,
        risk_level: "HIGH",
        regime_label: "FRAGILE_HIGH_VOL",
        volatility_state: "HIGH_VOL",
        tail_risk_state: "STRESSED",
        position_scale: 0.4,
        reason_tags: ["dispersion_rising", "downside_semivol_spike", "breadth_deterioration"],
        status: "ACTIVE",
        signal_template: "FRAGILE_SHORT_DEFENSIVE_V1",
        expected_holding_bars: 6,
        created_at: "2026-03-29T10:30:01+08:00",
        updated_at: "2026-03-29T10:30:01+08:00",
      },
      {
        signal_id: "sig_20260329_0003",
        instrument: "159915.SZ",
        market: "CN",
        asset_type: "ETF",
        timeframe: "1D",
        side: "LONG",
        signal_time: "2026-03-29T11:00:00+08:00",
        entry_type: "MARKET_ON_CLOSE",
        entry_price: 1.876,
        stop_loss: 1.821,
        take_profit: 1.972,
        confidence: 0.67,
        risk_level: "MEDIUM",
        regime_label: "TREND_RISK_ON",
        volatility_state: "NORMAL_VOL",
        tail_risk_state: "NORMAL",
        position_scale: 0.72,
        reason_tags: ["trend_strength_confirmed", "volume_expansion", "vrp_compressing"],
        status: "MONITORED",
        signal_template: "TREND_CONTINUATION_LONG_V2",
        expected_holding_bars: 12,
        created_at: "2026-03-29T11:00:01+08:00",
        updated_at: "2026-03-29T11:00:01+08:00",
      },
      {
        signal_id: "sig_20260329_0004",
        instrument: "000300.SH",
        market: "CN",
        asset_type: "INDEX",
        timeframe: "5m",
        side: "NEUTRAL",
        signal_time: "2026-03-29T11:15:00+08:00",
        entry_type: "NO_TRADE",
        entry_price: 0,
        stop_loss: 0,
        take_profit: 0,
        confidence: 0.58,
        risk_level: "BLOCKED",
        regime_label: "LIQUIDITY_SHOCK",
        volatility_state: "EXTREME_VOL",
        tail_risk_state: "EXTREME",
        position_scale: 0.0,
        reason_tags: ["shock_window_active", "liquidity_too_tight", "router_blocked_template"],
        status: "BLOCKED",
        signal_template: "OBSERVE_ONLY_CRISIS_V1",
        expected_holding_bars: 0,
        created_at: "2026-03-29T11:15:01+08:00",
        updated_at: "2026-03-29T11:15:01+08:00",
      },
    ];

    const pageSize = Number(search.get("page_size") || "50");
    return json(paginated(items.slice(0, pageSize), 1, pageSize));
  }

  if (pathname === "/api/v1/signals/performance/summary") {
    return json({
      summary: {
        total_signals: 60,
        win_rate: 0.57,
        avg_pnl: 0.0082,
        profit_factor: 1.43,
        max_drawdown: -0.062,
        avg_holding_bars: 6.8,
      },
      breakdowns: {
        by_regime: [
          { regime_label: "CALM_LOW_VOL", win_rate: 0.61, avg_pnl: 0.0091 },
          { regime_label: "FRAGILE_HIGH_VOL", win_rate: 0.43, avg_pnl: -0.0024 },
          { regime_label: "POST_SHOCK_REBOUND", win_rate: 0.65, avg_pnl: 0.0112 },
        ],
        by_confidence_bucket: [
          { bucket: "0.8-1.0", win_rate: 0.66, avg_pnl: 0.013 },
          { bucket: "0.6-0.8", win_rate: 0.54, avg_pnl: 0.0068 },
          { bucket: "0.4-0.6", win_rate: 0.41, avg_pnl: -0.0013 },
        ],
        by_template: [
          { template: "POST_SHOCK_REBOUND_LONG_V1", win_rate: 0.62, avg_pnl: 0.0101 },
          { template: "FRAGILE_SHORT_DEFENSIVE_V1", win_rate: 0.49, avg_pnl: 0.0023 },
        ],
        by_shock_window: [
          { window: "pre", win_rate: 0.58, avg_pnl: 0.0051 },
          { window: "impact", win_rate: 0.39, avg_pnl: -0.0062 },
          { window: "recovery", win_rate: 0.63, avg_pnl: 0.0124 },
        ],
      },
    });
  }

  if (pathname === "/api/v1/regime/current") {
    return json({
      snapshot_time: baseNow,
      regime_label: "POST_SHOCK_REBOUND",
      cpd_score: 0.72,
      cluster_id: 3,
      severity_score: 0.41,
      volatility_state: "HIGH_VOL",
      liquidity_state: "TIGHT",
      tail_risk_state: "ELEVATED",
      market_risk_level: "MEDIUM",
      data_source: "mock",
    });
  }

  if (pathname === "/api/v1/regime/history") {
    const items = Array.from({ length: 60 }).map((_, i) => {
      const t = new Date(Date.now() - (59 - i) * 24 * 3600 * 1000).toISOString();
      return {
        time: t,
        cpd_score: 0.4 + 0.2 * Math.sin(i / 7),
        severity_score: 0.35 + 0.15 * Math.cos(i / 9),
        vix: 18 + 6 * Math.sin(i / 11),
        vrp: 2.3 + 0.4 * Math.cos(i / 13),
        illiq: 0.9 + 0.2 * Math.sin(i / 17),
      };
    });
    return json(paginated(items, 1, items.length));
  }

  if (pathname === "/api/v1/regime/timeline") {
    return json(
      paginated([
        { start: "2026-03-01", end: "2026-03-10", regime_label: "FRAGILE_HIGH_VOL" },
        { start: "2026-03-11", end: "2026-03-20", regime_label: "LIQUIDITY_SHOCK" },
        { start: "2026-03-21", end: "2026-03-29", regime_label: "POST_SHOCK_REBOUND" },
      ]),
    );
  }

  if (pathname === "/api/v1/shocks") {
    return json(
      paginated([
        { event_id: "shock_001", event_date: "2026-03-12", event_type: "LIQUIDITY", severity: 0.86, detected_regime: "LIQUIDITY_SHOCK", status: "ACTIVE" },
        { event_id: "shock_002", event_date: "2026-03-22", event_type: "VOLATILITY", severity: 0.64, detected_regime: "FRAGILE_HIGH_VOL", status: "RESOLVED" },
      ]),
    );
  }

  if (pathname === "/api/v1/notifications/logs") {
    return json(
      paginated([
        { time: baseNow, channel: "slack", title: "Signal update", signal_id: "sig_20260329_0001" },
        { time: baseNow, channel: "email", title: "Risk regime changed", signal_id: null },
      ]),
    );
  }

  if (pathname === "/api/v1/regime/similar-periods") {
    const topk = Number(search.get("topk") || "20");
    const items = Array.from({ length: topk }).map((_, i) => ({
      asof_date: "2026-03-29",
      current_cluster_label: 3,
      current_is_noise: false,
      match_rank: i + 1,
      matched_date: `2024-0${(i % 9) + 1}-15`,
      distance_total: 0.12 + i * 0.01,
      distance_level1: 0.05 + i * 0.003,
      distance_level2: 0.04 + i * 0.003,
      distance_sequence: 0.03 + i * 0.004,
      matched_risk_regime: i % 2 === 0 ? "RISK_ON" : "RISK_OFF",
      matched_market_state: i % 2 === 0 ? "TREND" : "RANGE",
      matched_event_context: i % 3 === 0 ? "EARNINGS" : "MACRO",
      matched_fwd5_return: i % 4 === 0 ? null : 0.01 * Math.sin(i / 4),
      matched_fwd10_return: i % 5 === 0 ? null : 0.015 * Math.cos(i / 5),
      matched_fwd10_es05: -0.02 - 0.001 * i,
      model_version: "mock_v1",
    }));
    return json(paginated(items, 1, items.length));
  }

  if (pathname === "/api/v1/regime/current-state-profile") {
    return json({
      asof_date: "2026-03-29",
      risk_regime: "RISK_ON",
      market_state: "TREND",
      event_context: "MACRO",
      trend_strength: "STRONG",
      market_risk_level: "MEDIUM",
      dbscan_label: 3,
      is_noise: false,
      nearest_cluster_label: "3",
      similar_period_count: 20,
      similarity_confidence: 0.78,
      model_version: "mock_v1",
      computed_at: baseNow,
    });
  }

  return null;
}

function envEnabled(raw: string | undefined): boolean {
  if (!raw) return false;
  return !["0", "false", "no", "off"].includes(raw.toLowerCase());
}

function demoModeEnabled(): boolean {
  return envEnabled(process.env.NEXT_PUBLIC_ALLOW_MOCK_FALLBACK) || envEnabled(process.env.FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK);
}

function shouldForceMock(): boolean {
  const raw = process.env.FACTOR_PLATFORM_MOCK_BACKEND || process.env.NEXT_PUBLIC_MOCK_BACKEND;
  return demoModeEnabled() && envEnabled(raw);
}

function shouldFallbackToMock(): boolean {
  return demoModeEnabled();
}

function demoReadOnlyEnabled(): boolean {
  return demoModeEnabled() && envEnabled(process.env.NEXT_PUBLIC_DEMO_READONLY || process.env.FACTOR_PLATFORM_DEMO_READONLY);
}

function detectWslHostOrigin(): string | null {
  try {
    const isWsl = process.platform === "linux" && Boolean(process.env.WSL_DISTRO_NAME);
    if (!isWsl) return null;

    try {
      const hosts = fs.readFileSync("/etc/hosts", "utf8");
      if (hosts.includes("host.docker.internal")) return "http://host.docker.internal:8003";
    } catch {}

    const resolv = fs.readFileSync("/etc/resolv.conf", "utf8");
    const m = resolv.match(/^nameserver\s+([0-9.]+)\s*$/m);
    if (!m?.[1]) return null;
    return `http://${m[1]}:8003`;
  } catch {
    return null;
  }
}

function backendOrigin(): string {
  const raw = process.env.BACKEND_ORIGIN;
  if (raw) {
    const normalized = raw.startsWith("http://") || raw.startsWith("https://") ? raw : `http://${raw}`;
    try {
      const u = new URL(normalized);
      if (u.protocol === "http:" || u.protocol === "https:") return u.origin;
    } catch {}
  }
  return detectWslHostOrigin() || "http://127.0.0.1:8003";
}

function fallbackBackendOrigins(primary: string): string[] {
  const candidates = (process.env.BACKEND_FALLBACK_ORIGINS || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => (item.startsWith("http://") || item.startsWith("https://") ? item : `http://${item}`));

  try {
    const u = new URL(primary);
    if (["127.0.0.1", "localhost"].includes(u.hostname)) {
      if (u.port === "8003") candidates.push(`${u.protocol}//${u.hostname}:8002`);
      if (u.port === "8002") candidates.push(`${u.protocol}//${u.hostname}:8003`);
    }
  } catch {}

  return Array.from(new Set(candidates)).filter((item) => item !== primary);
}

function apiKey(): string {
  return process.env.FACTOR_PLATFORM_VIEW_KEY || process.env.NEXT_PUBLIC_API_KEY || "";
}

function requestTimeoutMs(method: string, pathname: string): number {
  const m = method.toUpperCase();
  if (pathname.startsWith("/api/backtests/data-status")) return 60000;
  if (pathname.startsWith("/api/data-maintenance/paths")) return 120000;
  if (m === "GET" || m === "HEAD") return 8000;
  if (pathname.startsWith("/api/backtests/run")) return 120000;
  if (pathname.startsWith("/api/data-maintenance/daily-update")) return 600000;
  if (pathname.startsWith("/api/v1/signals/refresh")) return 180000;
  if (pathname.startsWith("/api/v1/macro/")) return 120000;
  if (pathname.startsWith("/api/v1/strategy-ai/")) return 120000;
  return 30000;
}

async function toProxyResponse(upstream: Response) {
  const body = await upstream.arrayBuffer();
  const resHeaders = new Headers(upstream.headers);
  resHeaders.delete("content-encoding");
  resHeaders.delete("content-length");

  return new NextResponse(body, {
    status: upstream.status,
    headers: resHeaders,
  });
}

async function proxy(req: Request, ctx: { params: { path: string[] } }) {
  try {
    const { path } = ctx.params;
    const url = new URL(req.url);
    const pathname = `/${path.join("/")}`;
    const method = req.method.toUpperCase();

    if (shouldForceMock()) {
      const mock = mockResponse(pathname, url.searchParams);
      if (mock) return mock;
      if (demoReadOnlyEnabled() && !["GET", "HEAD", "OPTIONS"].includes(method)) {
        return json(
          {
            error: "DEMO_READ_ONLY",
            detail: "Roadshow demo is read-only and this mutation has no fixture response.",
            mode: "DEMO_FALLBACK",
          },
          423,
        );
      }
      return json({ error: "MOCK_NOT_AVAILABLE", pathname }, 404);
    }

    if (demoReadOnlyEnabled() && !["GET", "HEAD", "OPTIONS"].includes(method)) {
      return json(
        {
          error: "DEMO_READ_ONLY",
          detail: "Demo fallback is read-only. Restart the roadshow stack in REAL mode to run mutations.",
          mode: "DEMO_FALLBACK",
        },
        423,
      );
    }
    const origin = backendOrigin();
    const target = new URL(pathname, origin);
    target.search = url.search;

    const headers = new Headers(req.headers);
    headers.delete("host");
    headers.delete("connection");
    headers.delete("content-length");
    headers.delete("expect");
    headers.delete("keep-alive");
    headers.delete("proxy-authenticate");
    headers.delete("proxy-authorization");
    headers.delete("te");
    headers.delete("trailer");
    headers.delete("transfer-encoding");
    headers.delete("upgrade");

    if (!headers.has("X-API-Key")) {
      const key = apiKey();
      if (key) headers.set("X-API-Key", key);
    }

    const init: RequestInit = {
      method: req.method,
      headers,
      redirect: "manual",
    };

    if (req.method !== "GET" && req.method !== "HEAD") {
      const contentType = req.headers.get("content-type") || "";
      if (contentType.includes("application/json") || contentType.startsWith("text/") || contentType.includes("application/x-www-form-urlencoded")) {
        init.body = await req.text();
      } else {
        init.body = Buffer.from(await req.arrayBuffer()) as BodyInit;
      }
    }

    let upstream: Response;
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), requestTimeoutMs(req.method, pathname));
      try {
        upstream = await fetch(target, { ...init, signal: controller.signal });
      } finally {
        clearTimeout(timeout);
      }
    } catch (e) {
      for (const fallbackOrigin of fallbackBackendOrigins(origin)) {
        try {
          const retryTarget = new URL(pathname, fallbackOrigin);
          retryTarget.search = url.search;
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), requestTimeoutMs(req.method, pathname));
          try {
            const retry = await fetch(retryTarget, { ...init, signal: controller.signal });
            return toProxyResponse(retry);
          } finally {
            clearTimeout(timeout);
          }
        } catch {}
      }

      if (shouldFallbackToMock()) {
        const mock = mockResponse(pathname, url.searchParams);
        if (mock) return mock;
      }

      return json(
        {
          error: "BACKEND_TIMEOUT_OR_UNREACHABLE",
          backend_origin: origin,
          target: target.toString(),
          message: e instanceof Error ? e.message : String(e),
          cause: e instanceof Error && (e as any).cause ? String((e as any).cause.message || (e as any).cause) : undefined,
        },
        504,
      );
    }

    if (["GET", "HEAD"].includes(method) && [502, 503, 504].includes(upstream.status)) {
      const mock = mockResponse(pathname, url.searchParams);
      if (mock) return mock;
    }

    return toProxyResponse(upstream);
  } catch (e) {
    const debug = process.env.NODE_ENV !== "production";
    return NextResponse.json(
      {
        error: "PROXY_INTERNAL_ERROR",
        message: e instanceof Error ? e.message : String(e),
        stack: debug && e instanceof Error ? e.stack : undefined,
      },
      { status: 500 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
