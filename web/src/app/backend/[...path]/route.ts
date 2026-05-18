import fs from "node:fs";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

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

function mockResponse(pathname: string, search: URLSearchParams): NextResponse | null {
  const baseNow = nowIso();
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

  if (pathname === "/api/v1/signals/live" || pathname === "/api/v1/signals/history") {
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

function detectWslHostOrigin(): string | null {
  try {
    const isWsl = process.platform === "linux" && Boolean(process.env.WSL_DISTRO_NAME);
    if (!isWsl) return null;

    try {
      const hosts = fs.readFileSync("/etc/hosts", "utf8");
      if (hosts.includes("host.docker.internal")) return "http://host.docker.internal:8002";
    } catch {}

    const resolv = fs.readFileSync("/etc/resolv.conf", "utf8");
    const m = resolv.match(/^nameserver\s+([0-9.]+)\s*$/m);
    if (!m?.[1]) return null;
    return `http://${m[1]}:8002`;
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
  return detectWslHostOrigin() || "http://127.0.0.1:8002";
}

function apiKey(): string {
  return process.env.FACTOR_PLATFORM_VIEW_KEY || process.env.NEXT_PUBLIC_API_KEY || "";
}

function requestTimeoutMs(method: string, pathname: string): number {
  const m = method.toUpperCase();
  if (m === "GET" || m === "HEAD") return 8000;
  if (pathname.startsWith("/api/backtests/run")) return 120000;
  if (pathname.startsWith("/api/v1/macro/")) return 120000;
  return 30000;
}

async function proxy(req: Request, ctx: { params: { path: string[] } }) {
  try {
    const { path } = ctx.params;
    const url = new URL(req.url);
    const pathname = `/${path.join("/")}`;

    if (shouldForceMock()) {
      const mock = mockResponse(pathname, url.searchParams);
      if (mock) return mock;
      return json({ error: "MOCK_NOT_AVAILABLE", pathname }, 404);
    }
    const origin = backendOrigin();
    const target = new URL(pathname, origin);
    target.search = url.search;

    const headers = new Headers(req.headers);
    headers.delete("host");

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
      init.body = await req.arrayBuffer();
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
    } catch {
      if (shouldFallbackToMock()) {
        const mock = mockResponse(pathname, url.searchParams);
        if (mock) return mock;
      }

      return json(
        {
          error: "BACKEND_TIMEOUT_OR_UNREACHABLE",
          backend_origin: origin,
          target: target.toString(),
        },
        504,
      );
    }

    const body = await upstream.arrayBuffer();

    const resHeaders = new Headers(upstream.headers);
    resHeaders.delete("content-encoding");
    resHeaders.delete("content-length");

    return new NextResponse(body, {
      status: upstream.status,
      headers: resHeaders,
    });
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
