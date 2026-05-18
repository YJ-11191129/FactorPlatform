"use client";

import React, { useEffect, useMemo, useRef } from "react";

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

export function TradingViewAdvancedChart(props: {
  symbol: string;
  theme: TVTheme;
  height?: number;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
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

    host.innerHTML = `<div id="${containerIdRef.current}" style="height:${props.height ?? 520}px"></div>`;

    let disposed = false;
    ensureTvScript()
      .then(() => {
        if (disposed) return;
        const tv = window.TradingView;
        if (!tv?.widget) throw new Error("TradingView.widget not available");
        new tv.widget({ container_id: containerIdRef.current, ...config });
      })
      .catch(() => {
        if (disposed) return;
        host.innerHTML = "";
      });

    return () => {
      disposed = true;
      host.innerHTML = "";
    };
  }, [config, props.height]);

  return <div ref={hostRef} style={{ width: "100%" }} />;
}

