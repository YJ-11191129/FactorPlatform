"use client";

import {
  ArrowRightOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  FundProjectionScreenOutlined,
  LineChartOutlined,
  RadarChartOutlined,
  ReloadOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  StarOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Select, Segmented, Space } from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { ComponentType } from "react";

import { TradingViewAdvancedChart } from "@/components/tradingview/TradingViewAdvancedChart";
import { TradingViewExternalWidget } from "@/components/tradingview/TradingViewExternalWidget";
import { MiniTrend } from "@/components/visual/ResearchVisuals";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { summarizeNews } from "@/lib/api/news";
import type { NewsSummaryResponse } from "@/types/news";

import styles from "./dashboard.module.css";

type ModuleCategory = "量化研究" | "AI 工具" | "数据产品" | "效率工具" | "高级工具";
type CategoryFilter = "全部" | ModuleCategory;
type MarketKey = "cn" | "hk" | "us";
type WidgetTheme = "light" | "dark";

type ModuleCardConfig = {
  title: string;
  description: string;
  href: string;
  category: ModuleCategory;
  tags: string[];
  icon: ComponentType;
  featured?: boolean;
  advanced?: boolean;
};

const marketOptions: Record<MarketKey, { label: string; symbols: { value: string; label: string }[] }> = {
  cn: {
    label: "A 股",
    symbols: [
      { value: "SSE:000001", label: "上证指数 SSE:000001" },
      { value: "SZSE:399001", label: "深证成指 SZSE:399001" },
      { value: "SZSE:399006", label: "创业板指 SZSE:399006" },
      { value: "SSE:600519", label: "贵州茅台 SSE:600519" },
    ],
  },
  hk: {
    label: "港股",
    symbols: [
      { value: "HSI:HSI", label: "恒生指数 HSI" },
      { value: "HKEX:0700", label: "腾讯控股 HKEX:0700" },
      { value: "HKEX:9988", label: "阿里巴巴 HKEX:9988" },
    ],
  },
  us: {
    label: "美股",
    symbols: [
      { value: "SP:SPX", label: "标普 500 SPX" },
      { value: "NASDAQ:NDX", label: "纳指 100 NDX" },
      { value: "NASDAQ:NVDA", label: "NVIDIA NVDA" },
      { value: "NASDAQ:AAPL", label: "Apple AAPL" },
    ],
  },
};

const focusIndexes = [
  { name: "上证指数", code: "000001.SH", value: "3,154.32", change: "+0.85%", trend: "up" },
  { name: "深证成指", code: "399001.SZ", value: "9,856.48", change: "-0.32%", trend: "down" },
  { name: "沪深300", code: "000300.SH", value: "3,678.91", change: "+0.67%", trend: "up" },
  { name: "创业板指", code: "399006.SZ", value: "1,901.24", change: "-0.78%", trend: "down" },
] as const;

const aiPicks = [
  { rank: "1", name: "宁德时代", code: "300750.SZ", sector: "电力设备", score: 92, rating: "89.3" },
  { rank: "2", name: "迈瑞医疗", code: "300760.SZ", sector: "医药生物", score: 88, rating: "86.7" },
  { rank: "3", name: "中际旭创", code: "300308.SZ", sector: "通信", score: 85, rating: "82.1" },
] as const;

const newsSignals = [
  { title: "工信部：加快推进人形机器人创新发展", sector: "机器人", tone: "利好", time: "10:08" },
  { title: "美联储官员：通胀回落仍需更多数据确认", sector: "宏观经济", tone: "中性", time: "09:45" },
  { title: "新能源车企宣布下调部分车型售价", sector: "新能源汽车", tone: "利空", time: "09:21" },
] as const;

type DashboardNewsRow = {
  title: string;
  sector: string;
  tone: string;
  time: string;
  href: string;
  toneKind?: "good" | "bad";
};

const stockRadarHref = withDashboardQuery("/stock-radar", {
  source: "dashboard",
  provider: "cn",
  universe: "csi300",
  preset: "momentum",
  autoRun: 1,
});

function withDashboardQuery(path: string, params: Record<string, string | number | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && String(value).trim()) query.set(key, String(value));
  }
  const raw = query.toString();
  return raw ? `${path}?${raw}` : path;
}

function stockPickingForSymbol(item: (typeof aiPicks)[number]) {
  return withDashboardQuery("/stock-radar", {
    source: "dashboard",
    provider: "cn",
    universe: "csi300",
    preset: "momentum",
    autoRun: 1,
    asset: item.code,
    name: item.name,
    sector: item.sector,
  });
}

function strategyBuilderForSymbol(item?: (typeof aiPicks)[number]) {
  return withDashboardQuery("/ai-strategy-builder", {
    source: "dashboard",
    intent: "stock-picking",
    market: "equity",
    symbol: item?.code,
    name: item?.name,
    sector: item?.sector,
  });
}

function macroIntelHref(topic = "机器人", event?: string) {
  return withDashboardQuery("/macro-intel", {
    source: "dashboard",
    tab: "news",
    topic,
    event,
    region: "CN",
    autoRun: 1,
  });
}

function sourceLabel(source?: string) {
  if (!source) return "公开新闻源";
  const normalized = source.toLowerCase();
  if (normalized.includes("google")) return "Google 新闻";
  if (normalized.includes("gdelt")) return "GDELT 新闻";
  if (normalized.includes("openbb")) return "OpenBB 新闻";
  return source;
}

function formatNewsTime(value?: string) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

const modules: ModuleCardConfig[] = [
  {
    title: "AI 策略生成",
    description: "基于大模型与历史数据，生成可验证的量化策略草案、参数说明与风险提示。",
    href: "/ai-strategy-builder",
    category: "AI 工具",
    tags: ["大模型", "策略生成", "回测衔接", "Python"],
    icon: RobotOutlined,
  },
  {
    title: "AI 选股雷达",
    description: "按 qlib 因子族群构建横截面排序，辅助发现候选标的与因子贡献。",
    href: "/stock-radar",
    category: "AI 工具",
    tags: ["多因子", "横截面", "候选标的"],
    icon: StarOutlined,
    featured: true,
  },
  {
    title: "信号中心",
    description: "集中查看市场状态、信号筛选、路由判断与跟踪结果，强调可解释的筛选流程。",
    href: "/signal-center",
    category: "量化研究",
    tags: ["信号筛选", "风险状态", "跟踪"],
    icon: ThunderboltOutlined,
  },
  {
    title: "策略回测",
    description: "从策略库或因子组合发起回测，查看收益、回撤、换手与风险指标。",
    href: "/strategies",
    category: "量化研究",
    tags: ["回测", "参数优化", "报告"],
    icon: FundProjectionScreenOutlined,
  },
  {
    title: "绩效归因",
    description: "从收益、风险、市场状态和来源维度拆解结果，辅助复盘策略表现。",
    href: "/performance",
    category: "量化研究",
    tags: ["归因", "风险", "复盘"],
    icon: LineChartOutlined,
  },
  {
    title: "市场状态",
    description: "跟踪波动、流动性、尾部风险与相似历史区间，辅助判断策略适用环境。",
    href: "/regime-monitor",
    category: "数据产品",
    tags: ["Regime", "风险监控", "相似区间"],
    icon: RadarChartOutlined,
  },
  {
    title: "因子分析平台",
    description: "提供因子挖掘、清洗、测试与监控的全流程工具，面向研究模式使用。",
    href: "/factors",
    category: "高级工具",
    tags: ["因子挖掘", "IC 分析", "qLib"],
    icon: LineChartOutlined,
    advanced: true,
  },
  {
    title: "数据维护",
    description: "统一管理数据刷新、质量校验和本地演示链路健康状态。",
    href: "/data-maintenance",
    category: "高级工具",
    tags: ["数据刷新", "质量校验", "运维"],
    icon: DatabaseOutlined,
    advanced: true,
  },
  {
    title: "系统设置",
    description: "管理语言、高级研究模式和本地开发所需的技术配置。",
    href: "/settings",
    category: "高级工具",
    tags: ["偏好", "高级模式", "配置"],
    icon: SettingOutlined,
    advanced: true,
  },
];

function formatUpdatedAt(date: Date | null) {
  if (!date) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export default function DashboardPage() {
  const [advancedMode] = useAdvancedMode();
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("全部");
  const [market, setMarket] = useState<MarketKey>("cn");
  const [symbol, setSymbol] = useState("SSE:000001");
  const [theme, setTheme] = useState<WidgetTheme>("light");
  const [chartKey, setChartKey] = useState(0);
  const [newsRefreshKey, setNewsRefreshKey] = useState(0);
  const [dashboardNews, setDashboardNews] = useState<NewsSummaryResponse | null>(null);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsIssue, setNewsIssue] = useState("");
  const [browserOnline, setBrowserOnline] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [heartbeatAt, setHeartbeatAt] = useState<Date | null>(null);

  useEffect(() => {
    const now = new Date();
    setUpdatedAt(now);
    setHeartbeatAt(now);
  }, []);

  useEffect(() => {
    const syncOnlineState = () => setBrowserOnline(typeof navigator === "undefined" ? true : navigator.onLine);
    const beat = () => setHeartbeatAt(new Date());
    syncOnlineState();
    const interval = window.setInterval(beat, 30000);
    window.addEventListener("online", syncOnlineState);
    window.addEventListener("offline", syncOnlineState);
    document.addEventListener("visibilitychange", beat);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("online", syncOnlineState);
      window.removeEventListener("offline", syncOnlineState);
      document.removeEventListener("visibilitychange", beat);
    };
  }, []);

  useEffect(() => {
    let alive = true;
    setNewsLoading(true);
    setNewsIssue("");
    summarizeNews({ topic: "机器人", region: "CN", lang: "zh-CN", limit: 3 })
      .then((res) => {
        if (!alive) return;
        setDashboardNews(res);
      })
      .catch(() => {
        if (!alive) return;
        setNewsIssue("信息源暂不可用，可进入宏观情报页刷新。");
      })
      .finally(() => {
        if (alive) setNewsLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [newsRefreshKey]);

  const visibleModules = useMemo(
    () =>
      modules.filter((item) => {
        if (item.advanced && !advancedMode) return false;
        return activeCategory === "全部" || item.category === activeCategory;
      }),
    [activeCategory, advancedMode],
  );

  const visibleCategories = useMemo(() => {
    const available = new Set(visibleModules.map((item) => item.category));
    return (["全部", "量化研究", "AI 工具", "数据产品", "效率工具", "高级工具"] as CategoryFilter[]).filter(
      (category) => category === "全部" || available.has(category),
    );
  }, [visibleModules]);

  const technicalAnalysisConfig = useMemo(
    () => ({
      interval: "1D",
      width: "100%",
      isTransparent: false,
      height: "278",
      symbol,
      showIntervalTabs: true,
      displayMode: "single",
      locale: "zh_CN",
      colorTheme: theme,
    }),
    [symbol, theme],
  );

  const marketOverviewConfig = useMemo(
    () => ({
      colorTheme: theme,
      dateRange: "12M",
      showChart: true,
      locale: "zh_CN",
      width: "100%",
      height: "238",
      largeChartUrl: "",
      isTransparent: false,
      showSymbolLogo: true,
      showFloatingTooltip: true,
      tabs: [
        {
          title: "指数",
          symbols: [
            { s: "SSE:000001", d: "上证指数" },
            { s: "SZSE:399001", d: "深证成指" },
            { s: "SZSE:399006", d: "创业板指" },
            { s: "NASDAQ:NDX", d: "纳指 100" },
          ],
          originalTitle: "Indices",
        },
      ],
    }),
    [theme],
  );

  function refreshBoard() {
    const now = new Date();
    setUpdatedAt(now);
    setHeartbeatAt(now);
    setChartKey((value) => value + 1);
    setNewsRefreshKey((value) => value + 1);
  }

  const liveNewsRows = useMemo<DashboardNewsRow[]>(() => {
    return (dashboardNews?.items || []).slice(0, 3).map((item) => ({
      title: item.title,
      sector: item.source || "新闻",
      tone: "摘要",
      time: formatNewsTime(item.published_at),
      href: macroIntelHref("机器人", item.title),
    }));
  }, [dashboardNews]);

  const fallbackNewsRows = useMemo<DashboardNewsRow[]>(
    () =>
      newsSignals.map((item) => ({
        ...item,
        href: macroIntelHref(item.sector, item.title),
        toneKind: item.tone === "利空" ? "bad" : item.tone === "利好" ? "good" : undefined,
      })),
    [],
  );

  const displayNewsRows = liveNewsRows.length ? liveNewsRows : fallbackNewsRows;
  const newsSourceText = dashboardNews?.count
    ? `信息源已接通：${sourceLabel(dashboardNews.source)} · ${dashboardNews.count} 条`
    : newsLoading
      ? "信息源连接中..."
      : newsIssue || "信息源待刷新";
  const boardOnlineText = browserOnline
    ? newsIssue
      ? "看板在线 · API 兜底"
      : newsLoading
        ? "看板在线 · 同步中"
        : "看板在线"
    : "浏览器离线 · 本地快照可用";

  return (
    <main className={styles.dashboardPage}>
      <section className={styles.marketBoard} aria-label="市场看板">
        <header className={styles.boardHeader}>
          <div>
            <h1>智能投研工作台</h1>
            <p>聚合行情、候选标的与事件信息，辅助研究人员进行风险识别、情景推演与可回测策略设计。</p>
          </div>
          <Space wrap className={styles.boardControls}>
            <span className={`${styles.onlinePill} ${browserOnline ? "" : styles.onlinePillWarning}`}>
              <span aria-hidden="true" />
              {boardOnlineText}
            </span>
            <span className={styles.updatedText}>心跳：{formatUpdatedAt(heartbeatAt)}</span>
            <span className={styles.updatedText}>数据更新：{formatUpdatedAt(updatedAt)}</span>
            <Button icon={<ReloadOutlined />} onClick={refreshBoard}>
              刷新
            </Button>
          </Space>
        </header>

        <div className={styles.boardGrid}>
          <section className={styles.chartPanel}>
            <div className={styles.panelTitleRow}>
              <span className={styles.iconBox}>
                <BarChartOutlined />
              </span>
              <div>
                <h2>市场看板</h2>
                <span>实时行情</span>
              </div>
            </div>

            <div className={styles.marketTabs}>
              <Segmented
                value={market}
                options={(Object.keys(marketOptions) as MarketKey[]).map((key) => ({
                  label: marketOptions[key].label,
                  value: key,
                }))}
                onChange={(value) => {
                  const nextMarket = value as MarketKey;
                  setMarket(nextMarket);
                  setSymbol(marketOptions[nextMarket].symbols[0].value);
                }}
              />
              <Space wrap>
                <Select
                  value={symbol}
                  options={marketOptions[market].symbols}
                  style={{ minWidth: 210 }}
                  onChange={setSymbol}
                />
                <Segmented
                  value={theme}
                  options={[
                    { label: "浅色", value: "light" },
                    { label: "深色", value: "dark" },
                  ]}
                  onChange={(value) => setTheme(value as WidgetTheme)}
                />
              </Space>
            </div>

            <div className={styles.chartArea}>
              <aside className={styles.indexList}>
                {focusIndexes.map((item) => (
                  <div key={item.code} className={styles.indexItem}>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.code}</span>
                    </div>
                    <div className={item.trend === "up" ? styles.upText : styles.downText}>
                      <b>{item.value}</b>
                      <span>{item.change}</span>
                    </div>
                    <span className={`${styles.sparkline} ${item.trend === "up" ? styles.sparklineUp : styles.sparklineDown}`} />
                  </div>
                ))}
              </aside>
              <div className={styles.tvChartFrame}>
                <TradingViewAdvancedChart
                  key={`${symbol}-${theme}-${chartKey}`}
                  symbol={symbol}
                  theme={theme}
                  height={650}
                  fallbackAfterMs={7000}
                />
              </div>
            </div>

            <div className={styles.marketStats}>
              <div className={styles.statCard}>
                <span className={styles.statIcon}><LineChartOutlined /></span>
                <div>
                  <span>市场宽度（上涨/下跌）</span>
                  <strong><em className={styles.upText}>3,428</em> / <em className={styles.downText}>1,126</em></strong>
                </div>
                <div className={styles.breadthBar}><span /></div>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statIcon}><DatabaseOutlined /></span>
                <div>
                  <span>成交额</span>
                  <strong>9,842.65 <small>亿元</small></strong>
                </div>
                <b className={styles.downText}>较昨日 +6.31%</b>
              </div>
            </div>
          </section>

          <aside className={styles.sideColumn}>
            <section className={styles.sidePanel}>
              <div className={styles.sidePanelHeader}>
                <span className={styles.iconBox}>
                  <RobotOutlined />
                </span>
                <div>
                  <h2>AI 选股</h2>
                  <span>多因子模型智能筛选潜力标的</span>
                </div>
                <Link href={stockRadarHref} className={styles.primaryAction}>开始选股</Link>
              </div>
              <div className={styles.nextStepRow}>
                <span>下一步：候选池筛选</span>
                <span>从看板进入 AI 选股会自动带入 A 股、多因子与动量预设</span>
              </div>
              <div className={styles.chipRow}>
                {["成长性", "价值", "动量", "风险"].map((tag) => <span key={tag}>{tag}</span>)}
              </div>
              <div className={styles.signalStrip}>
                <div>
                  <span>候选强度</span>
                  <strong>偏多观察</strong>
                </div>
                <MiniTrend points={[52, 58, 55, 63, 67, 72, 69, 76]} tone="positive" height={42} />
                <em>置信度 86%</em>
              </div>
              <div className={styles.pickTable}>
                {aiPicks.map((item) => (
                  <Link
                    key={item.code}
                    href={stockPickingForSymbol(item)}
                    className={styles.pickRow}
                    aria-label={`围绕 ${item.name} 生成可回测选股策略`}
                  >
                    <span className={styles.rankBadge}>{item.rank}</span>
                    <strong>{item.name}<small>{item.code}</small></strong>
                    <span>{item.sector}</span>
                    <em>{item.score}</em>
                    <b>{item.rating}</b>
                  </Link>
                ))}
              </div>
              <div className={styles.actionLinkRow}>
                <Link href={stockRadarHref} className={styles.inlineLink}>查看候选池 <ArrowRightOutlined /></Link>
                <Link href={strategyBuilderForSymbol()} className={styles.inlineLink}>生成策略 <ArrowRightOutlined /></Link>
              </div>
            </section>

            <section className={styles.sidePanel}>
              <div className={styles.sidePanelHeader}>
                <span className={styles.iconBox}>
                  <ThunderboltOutlined />
                </span>
                <div>
                  <h2>信息搜集</h2>
                  <span>识别事件影响与市场情绪</span>
                </div>
                <Link href={macroIntelHref()} className={styles.primaryAction}>搜集信息</Link>
              </div>
              <div className={styles.nextStepRow}>
                <span>下一步：搜集信息</span>
                <span>进入新闻摘要与宏观链路分析</span>
              </div>
              <div className={`${styles.sourceStatus} ${dashboardNews?.count ? styles.sourceStatusReady : newsIssue ? styles.sourceStatusWarning : ""}`}>
                {newsSourceText}
              </div>
              <div className={styles.newsHeatRow}>
                <div>
                  <span>新闻热度</span>
                  <strong>{dashboardNews?.items?.length ? "信息源已接通" : "等待刷新"}</strong>
                </div>
                <div className={styles.heatBars} aria-hidden="true">
                  {[54, 68, 82, 73, 88].map((height, index) => <span key={index} style={{ height: `${height}%` }} />)}
                </div>
              </div>
              <div className={styles.newsTable}>
                {displayNewsRows.map((item) => (
                  <Link
                    key={item.title}
                    href={item.href}
                    className={styles.newsRow}
                    aria-label={`分析新闻事件：${item.title}`}
                  >
                    <strong>{item.title}</strong>
                    <span>{item.sector}</span>
                    <em className={item.toneKind === "bad" ? styles.badTone : item.toneKind === "good" ? styles.goodTone : ""}>{item.tone}</em>
                    <b>{item.time}</b>
                  </Link>
                ))}
              </div>
              <Link href={macroIntelHref()} className={styles.inlineLink}>查看全部新闻 <ArrowRightOutlined /></Link>
            </section>

            {advancedMode ? (
              <section className={styles.widgetPanel}>
                <div className={styles.widgetFallback}>
                  <strong>市场信息</strong>
                  <span>外部市场组件加载中，若网络受限可继续使用左侧行情与 AI 筛选摘要。</span>
                </div>
                <TradingViewExternalWidget
                  scriptSrc="https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js"
                  config={marketOverviewConfig}
                />
              </section>
            ) : null}
          </aside>
        </div>

        <div className={styles.quickCards} aria-label="今日摘要">
          <Link href="/signal-center" className={styles.quickCard}>
            <SafetyCertificateOutlined />
            <strong>今日信号</strong>
            <span>强势信号 <b>18</b>　弱势信号 <em>7</em></span>
            <ArrowRightOutlined />
          </Link>
          <Link href={stockRadarHref} className={styles.quickCard}>
            <StarOutlined />
            <strong>AI 选股</strong>
            <span>候选池 <b>3</b>　自动预设　可回测</span>
            <ArrowRightOutlined />
          </Link>
          <Link href={macroIntelHref("机器人产业链")} className={styles.quickCard}>
            <ThunderboltOutlined />
            <strong>宏观情报</strong>
            <span>新闻源 <b>{dashboardNews?.count || displayNewsRows.length}</b>　事件链路　摘要</span>
            <ArrowRightOutlined />
          </Link>
          <Link href="/regime-monitor" className={styles.quickCard}>
            <SafetyCertificateOutlined />
            <strong>风险预警</strong>
            <span>预警中 <em>3</em>　关注中 8　正常 <b>42</b></span>
            <ArrowRightOutlined />
          </Link>
        </div>

        <div className={styles.researchDashboard}>
          <div>
            <span className={styles.statusDot} />
            <strong>研究建议</strong>
            <p>当前候选池偏多但风险过滤仍需关注，建议先生成策略并回测验证。</p>
          </div>
          <div>
            <span className={styles.statusDotWarning} />
            <strong>事件风险</strong>
            <p>机器人与半导体新闻热度较高，进入宏观情报查看传导路径。</p>
          </div>
          <div>
            <span className={styles.statusDotNeutral} />
            <strong>执行纪律</strong>
            <p>普通模式仅展示研究观察，不给出直接交易指令或收益承诺。</p>
          </div>
        </div>

        {advancedMode ? (
          <div className={styles.advancedDiagnostics}>
            <TradingViewExternalWidget
              scriptSrc="https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js"
              config={technicalAnalysisConfig}
            />
          </div>
        ) : null}
      </section>

      <section className={styles.modulesSection} aria-label="研究模块">
        <header className={styles.modulesHeader}>
          <div className={styles.titleGroup}>
            <span className={styles.titleAccent} aria-hidden="true" />
            <div>
              <h2>研究应用</h2>
              <p>看板之后进入策略、信号、回测和研究工具；高级模式下可访问数据与运维入口。</p>
            </div>
          </div>
          <Link href="/ai-strategy-builder" className={styles.featuredLink}>
            查看策略生成
            <ArrowRightOutlined />
          </Link>
        </header>

        <div className={styles.categoryBar} role="tablist" aria-label="项目分类">
          {visibleCategories.map((category) => (
            <button
              key={category}
              type="button"
              role="tab"
              aria-selected={activeCategory === category}
              className={`${styles.categoryButton} ${activeCategory === category ? styles.categoryButtonActive : ""}`}
              onClick={() => setActiveCategory(category)}
            >
              {category}
            </button>
          ))}
        </div>

        <div className={styles.moduleGrid}>
          {visibleModules.map((module) => {
            const Icon = module.icon;
            return (
              <Link
                key={module.href}
                href={module.href}
                className={`${styles.moduleCard} ${module.featured ? styles.moduleCardFeatured : ""}`}
              >
                <span className={styles.cardArrow} aria-hidden="true">
                  <ArrowRightOutlined />
                </span>
                <span className={styles.moduleIconBox}>
                  <Icon />
                </span>
                <h3>{module.title}</h3>
                <p>{module.description}</p>
                <span className={styles.tagRow}>
                  {module.tags.map((tag) => (
                    <span key={tag} className={styles.tag}>
                      {tag}
                    </span>
                  ))}
                </span>
              </Link>
            );
          })}
        </div>
      </section>
    </main>
  );
}
