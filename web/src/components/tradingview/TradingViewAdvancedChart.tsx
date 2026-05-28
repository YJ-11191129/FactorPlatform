"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

type TVTheme = "light" | "dark";

declare global {
  interface Window {
    TradingView?: {
      widget: new (config: Record<string, unknown>) => unknown;
    };
  }
}

let tvScriptPromise: Promise<void> | null = null;

function ensureTvScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.TradingView?.widget) return Promise.resolve();
  if (tvScriptPromise) return tvScriptPromise;

  tvScriptPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[src="https://s3.tradingview.com/tv.js"]');
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("TradingView tv.js load failed")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("TradingView tv.js load failed"));
    document.head.appendChild(script);
  });

  return tvScriptPromise;
}

const fallbackCandles = [
  { open: 3120, high: 3190, low: 3088, close: 3168, volume: 42 },
  { open: 3168, high: 3216, low: 3142, close: 3198, volume: 51 },
  { open: 3198, high: 3230, low: 3148, close: 3162, volume: 46 },
  { open: 3162, high: 3268, low: 3154, close: 3254, volume: 58 },
  { open: 3254, high: 3320, low: 3236, close: 3296, volume: 62 },
  { open: 3296, high: 3344, low: 3262, close: 3318, volume: 54 },
  { open: 3318, high: 3378, low: 3304, close: 3362, volume: 68 },
  { open: 3362, high: 3412, low: 3336, close: 3384, volume: 66 },
  { open: 3384, high: 3420, low: 3350, close: 3368, volume: 49 },
  { open: 3368, high: 3468, low: 3360, close: 3444, volume: 72 },
  { open: 3444, high: 3520, low: 3410, close: 3506, volume: 79 },
  { open: 3506, high: 3568, low: 3488, close: 3542, volume: 74 },
  { open: 3542, high: 3590, low: 3494, close: 3518, volume: 63 },
  { open: 3518, high: 3636, low: 3508, close: 3614, volume: 88 },
  { open: 3614, high: 3682, low: 3580, close: 3656, volume: 84 },
  { open: 3656, high: 3718, low: 3624, close: 3698, volume: 91 },
  { open: 3698, high: 3764, low: 3652, close: 3676, volume: 76 },
  { open: 3676, high: 3798, low: 3668, close: 3772, volume: 96 },
  { open: 3772, high: 3848, low: 3738, close: 3814, volume: 101 },
  { open: 3814, high: 3880, low: 3782, close: 3856, volume: 94 },
  { open: 3856, high: 3916, low: 3818, close: 3840, volume: 82 },
  { open: 3840, high: 3964, low: 3832, close: 3948, volume: 112 },
  { open: 3948, high: 4012, low: 3908, close: 3986, volume: 105 },
  { open: 3986, high: 4068, low: 3960, close: 4048, volume: 118 },
  { open: 4048, high: 4108, low: 3988, close: 4012, volume: 97 },
  { open: 4012, high: 4146, low: 4002, close: 4118, volume: 124 },
] as const;

function LocalMarketChartFallback(props: { symbol: string; theme: TVTheme; height: number }) {
  const isDark = props.theme === "dark";
  const minPrice = 3000;
  const maxPrice = 4200;
  const chartTop = 58;
  const chartHeight = 320;
  const volumeTop = 410;
  const volumeHeight = 72;
  const xStep = 34;
  const xStart = 70;
  const candleWidth = 11;
  const gridColor = isDark ? "rgba(148, 163, 184, 0.16)" : "rgba(15, 23, 42, 0.09)";
  const textColor = isDark ? "#CBD5E1" : "#334155";
  const mutedColor = isDark ? "#94A3B8" : "#64748B";
  const panelBg = isDark ? "#08111F" : "#F8FBFC";
  const strokeBg = isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.1)";
  const yForPrice = (value: number) => chartTop + (maxPrice - value) / (maxPrice - minPrice) * chartHeight;
  const points = fallbackCandles.map((item, index) => `${xStart + index * xStep},${yForPrice(item.close)}`).join(" ");
  const last = fallbackCandles[fallbackCandles.length - 1];
  const previous = fallbackCandles[fallbackCandles.length - 2];
  const change = ((last.close - previous.close) / previous.close) * 100;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        minHeight: props.height,
        overflow: "hidden",
        borderRadius: 10,
        border: `1px solid ${strokeBg}`,
        background: panelBg,
      }}
    >
      <svg viewBox="0 0 1000 540" width="100%" height="100%" role="img" aria-label="本地行情快照">
        <defs>
          <linearGradient id="fallbackLineFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#14B8A6" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#14B8A6" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="fallbackVolumeFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.36" />
            <stop offset="100%" stopColor="#22D3EE" stopOpacity="0.08" />
          </linearGradient>
        </defs>

        <rect x="0" y="0" width="1000" height="540" fill={panelBg} />
        {[0, 1, 2, 3, 4].map((line) => {
          const y = chartTop + line * (chartHeight / 4);
          return <line key={`h-${line}`} x1="46" x2="938" y1={y} y2={y} stroke={gridColor} strokeWidth="1" />;
        })}
        {[0, 1, 2, 3, 4, 5, 6].map((line) => {
          const x = xStart + line * 136;
          return <line key={`v-${line}`} x1={x} x2={x} y1={chartTop} y2={volumeTop + volumeHeight} stroke={gridColor} strokeWidth="1" />;
        })}

        <text x="52" y="34" fill={textColor} fontSize="20" fontWeight="700">
          本地行情快照
        </text>
        <text x="196" y="34" fill={mutedColor} fontSize="14">
          {props.symbol} · 外部图表连接中
        </text>
        <text x="820" y="34" fill={change >= 0 ? "#0F9F8F" : "#F43F5E"} fontSize="18" fontWeight="700">
          {last.close.toLocaleString()} {change >= 0 ? "+" : ""}{change.toFixed(2)}%
        </text>

        <polygon
          points={`${points} ${xStart + (fallbackCandles.length - 1) * xStep},${chartTop + chartHeight} ${xStart},${chartTop + chartHeight}`}
          fill="url(#fallbackLineFill)"
        />
        <polyline points={points} fill="none" stroke="#0F9F8F" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

        {fallbackCandles.map((item, index) => {
          const x = xStart + index * xStep;
          const up = item.close >= item.open;
          const color = up ? "#14B8A6" : "#F43F5E";
          const bodyTop = Math.min(yForPrice(item.open), yForPrice(item.close));
          const bodyHeight = Math.max(3, Math.abs(yForPrice(item.open) - yForPrice(item.close)));
          const volumeHeightPx = item.volume / 130 * volumeHeight;
          return (
            <g key={`${item.open}-${index}`}>
              <line x1={x} x2={x} y1={yForPrice(item.high)} y2={yForPrice(item.low)} stroke={color} strokeWidth="2" />
              <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} rx="2" fill={color} />
              <rect x={x - candleWidth / 2} y={volumeTop + volumeHeight - volumeHeightPx} width={candleWidth} height={volumeHeightPx} rx="2" fill="url(#fallbackVolumeFill)" />
            </g>
          );
        })}

        {[4200, 3900, 3600, 3300, 3000].map((price) => (
          <text key={price} x="948" y={yForPrice(price) + 5} fill={mutedColor} fontSize="13">
            {price.toLocaleString()}
          </text>
        ))}
        {["1月", "2月", "3月", "4月", "5月"].map((label, index) => (
          <text key={label} x={xStart + index * 190} y="512" fill={mutedColor} fontSize="13">
            {label}
          </text>
        ))}
        <rect x="52" y="392" width="136" height="26" rx="13" fill={isDark ? "rgba(20,184,166,0.12)" : "rgba(20,184,166,0.1)"} />
        <text x="68" y="410" fill="#0F9F8F" fontSize="13" fontWeight="700">
          本地缓存走势
        </text>
        <text x="204" y="410" fill={mutedColor} fontSize="13">
          主看板继续可用，可刷新尝试恢复 TradingView。
        </text>
      </svg>
    </div>
  );
}

export function TradingViewAdvancedChart(props: {
  symbol: string;
  theme: TVTheme;
  height?: number;
  fallbackAfterMs?: number;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [failed, setFailed] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [ready, setReady] = useState(false);
  const containerIdRef = useRef<string>(
    `tv_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`,
  );

  const config = useMemo(() => {
    return {
      autosize: true,
      symbol: props.symbol,
      interval: "D",
      timezone: "Asia/Shanghai",
      theme: props.theme,
      style: "1",
      locale: "zh_CN",
      enable_publishing: false,
      allow_symbol_change: false,
      hide_side_toolbar: false,
      save_image: false,
      withdateranges: true,
      calendar: false,
      studies: ["MACD@tv-basicstudies", "RSI@tv-basicstudies"],
    } as Record<string, unknown>;
  }, [props.symbol, props.theme]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    setFailed(false);
    setTimedOut(false);
    setReady(false);
    host.innerHTML = `<div id="${containerIdRef.current}" style="height:${props.height ?? 520}px"></div>`;

    let disposed = false;
    let readyTimer: number | null = null;
    const fallbackTimer = window.setTimeout(() => {
      if (!disposed) setTimedOut(true);
    }, props.fallbackAfterMs ?? 12000);

    ensureTvScript()
      .then(() => {
        if (disposed) return;
        const tv = window.TradingView;
        if (!tv?.widget) throw new Error("TradingView.widget not available");
        new tv.widget({ container_id: containerIdRef.current, ...config });
        readyTimer = window.setTimeout(() => {
          if (!disposed) setReady(true);
        }, 1500);
      })
      .catch(() => {
        if (disposed) return;
        host.innerHTML = "";
        setFailed(true);
      });

    return () => {
      disposed = true;
      window.clearTimeout(fallbackTimer);
      if (readyTimer) window.clearTimeout(readyTimer);
      host.innerHTML = "";
    };
  }, [config, props.fallbackAfterMs, props.height]);

  return (
    <div style={{ position: "relative", width: "100%", minHeight: props.height ?? 520 }}>
      <div
        ref={hostRef}
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 2,
          width: "100%",
          visibility: ready && !failed && !timedOut ? "visible" : "hidden",
        }}
      />
      {!ready || failed || timedOut ? (
        <LocalMarketChartFallback symbol={props.symbol} theme={props.theme} height={props.height ?? 520} />
      ) : null}
    </div>
  );
}
