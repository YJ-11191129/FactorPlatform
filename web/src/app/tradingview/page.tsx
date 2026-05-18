"use client";

import { Card, Col, Divider, Input, Row, Segmented, Select, Space, Typography } from "antd";
import React, { useEffect, useMemo, useState } from "react";

import { TradingViewAdvancedChart } from "@/components/tradingview/TradingViewAdvancedChart";
import { TradingViewExternalWidget } from "@/components/tradingview/TradingViewExternalWidget";

type WidgetTheme = "light" | "dark";

const SYMBOL_PRESETS = [
  { value: "SSE:000001", label: "SSE:000001 上证指数" },
  { value: "SZSE:399001", label: "SZSE:399001 深证成指" },
  { value: "SSE:600519", label: "SSE:600519 贵州茅台" },
  { value: "NASDAQ:AAPL", label: "NASDAQ:AAPL Apple" },
  { value: "NASDAQ:NVDA", label: "NASDAQ:NVDA NVIDIA" },
  { value: "BINANCE:BTCUSDT", label: "BINANCE:BTCUSDT" },
  { value: "BINANCE:ETHUSDT", label: "BINANCE:ETHUSDT" },
];

function usePersistedState<T>(key: string, init: T) {
  const [v, setV] = useState<T>(init);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      setV(JSON.parse(raw));
    } catch {
      return;
    }
  }, [key]);
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(v));
    } catch {
      return;
    }
  }, [key, v]);
  return [v, setV] as const;
}

export default function TradingViewDashboardPage() {
  const [theme, setTheme] = usePersistedState<WidgetTheme>("tv_theme", "light");
  const [symbol, setSymbol] = usePersistedState<string>("tv_symbol", "SSE:000001");
  const [customSymbol, setCustomSymbol] = useState("");

  const resolvedSymbol = useMemo(() => {
    const s = (customSymbol || symbol).trim();
    return s.length > 0 ? s : "SSE:000001";
  }, [customSymbol, symbol]);

  const technicalAnalysisConfig = useMemo(() => {
    return {
      interval: "1D",
      width: "100%",
      isTransparent: false,
      height: "520",
      symbol: resolvedSymbol,
      showIntervalTabs: true,
      displayMode: "single",
      locale: "zh_CN",
      colorTheme: theme,
    };
  }, [resolvedSymbol, theme]);

  const marketOverviewConfig = useMemo(() => {
    return {
      colorTheme: theme,
      dateRange: "12M",
      showChart: true,
      locale: "zh_CN",
      width: "100%",
      height: "420",
      largeChartUrl: "",
      isTransparent: false,
      showSymbolLogo: true,
      showFloatingTooltip: true,
      plotLineColorGrowing: "rgba(41, 98, 255, 1)",
      plotLineColorFalling: "rgba(255, 0, 0, 1)",
      gridLineColor: "rgba(42, 46, 57, 0)",
      scaleFontColor: "rgba(106, 109, 120, 1)",
      belowLineFillColorGrowing: "rgba(41, 98, 255, 0.12)",
      belowLineFillColorFalling: "rgba(255, 0, 0, 0.12)",
      belowLineFillColorGrowingBottom: "rgba(41, 98, 255, 0)",
      belowLineFillColorFallingBottom: "rgba(255, 0, 0, 0)",
      symbolActiveColor: "rgba(41, 98, 255, 0.12)",
      tabs: [
        {
          title: "指数",
          symbols: [
            { s: "SSE:000001", d: "上证" },
            { s: "SZSE:399001", d: "深证" },
            { s: "NASDAQ:NDX", d: "纳指100" },
            { s: "SP:SPX", d: "标普500" },
          ],
          originalTitle: "Indices",
        },
        {
          title: "FX",
          symbols: [
            { s: "FX:USDCNH", d: "USDCNH" },
            { s: "FX:EURUSD", d: "EURUSD" },
            { s: "FX:USDJPY", d: "USDJPY" },
          ],
          originalTitle: "Forex",
        },
        {
          title: "Crypto",
          symbols: [
            { s: "BINANCE:BTCUSDT", d: "BTC" },
            { s: "BINANCE:ETHUSDT", d: "ETH" },
            { s: "BINANCE:SOLUSDT", d: "SOL" },
          ],
          originalTitle: "Crypto",
        },
      ],
    };
  }, [theme]);

  const screenerConfig = useMemo(() => {
    return {
      width: "100%",
      height: "640",
      defaultColumn: "overview",
      defaultScreen: "most_capitalized",
      market: "china",
      showToolbar: true,
      colorTheme: theme,
      locale: "zh_CN",
      isTransparent: false,
    };
  }, [theme]);

  return (
    <div style={{ padding: 20 }}>
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div>
            <Typography.Title level={3} style={{ margin: 0 }}>
              TradingView 综合看板
            </Typography.Title>
            <Typography.Text type="secondary">高级图表、技术分析、市场概览与股票筛选器</Typography.Text>
          </div>

          <Space wrap>
            <Segmented
              value={theme}
              options={[
                { label: "浅色", value: "light" },
                { label: "深色", value: "dark" },
              ]}
              onChange={(v) => setTheme(v as WidgetTheme)}
            />
            <Select
              value={symbol}
              style={{ width: 220 }}
              options={SYMBOL_PRESETS}
              onChange={(v) => {
                setSymbol(v);
                setCustomSymbol("");
              }}
            />
            <Input
              placeholder="自定义 symbol，例如 SSE:600000"
              value={customSymbol}
              onChange={(e) => setCustomSymbol(e.target.value)}
              style={{ width: 260 }}
              allowClear
            />
          </Space>
        </div>

        <Divider style={{ margin: "8px 0" }} />

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={16}>
            <Card size="small" title="高级图表" styles={{ body: { padding: 8 } }}>
              <TradingViewAdvancedChart symbol={resolvedSymbol} theme={theme} height={520} />
            </Card>
          </Col>
          <Col xs={24} xl={8}>
            <Card size="small" title="技术分析" styles={{ body: { padding: 8 } }}>
              <TradingViewExternalWidget
                scriptSrc="https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js"
                config={technicalAnalysisConfig}
              />
            </Card>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={14}>
            <Card size="small" title="市场概览" styles={{ body: { padding: 8 } }}>
              <TradingViewExternalWidget
                scriptSrc="https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js"
                config={marketOverviewConfig}
              />
            </Card>
          </Col>
          <Col xs={24} xl={10}>
            <Card size="small" title="股票筛选器" styles={{ body: { padding: 8 } }}>
              <TradingViewExternalWidget
                scriptSrc="https://s3.tradingview.com/external-embedding/embed-widget-screener.js"
                config={screenerConfig}
              />
            </Card>
          </Col>
        </Row>
      </Space>
    </div>
  );
}

