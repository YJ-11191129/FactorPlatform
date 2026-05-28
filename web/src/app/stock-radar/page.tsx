"use client";

import { Alert, Button, Card, Col, Divider, Form, Input, InputNumber, Progress, Row, Select, Space, Table, Tag, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PageContainer } from "@/components/layout/PageContainer";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { buildDemoStockRadar, listFactorMetadata, runStockRadar, type BackendFactorInfo, type StockRadarFactorSpec, type StockRadarItem, type StockRadarPayload, type StockRadarResult } from "@/lib/api/factors";
import { useLanguage, type Language } from "@/lib/i18n";

import styles from "./stock-radar.module.css";

const DEFAULT_PROVIDER_URI = "D:\\mcQlib\\data\\qlib_bin\\cn_data";
const DEFAULT_US_PROVIDER_URI = "D:\\mcQlib\\data\\qlib_bin\\us_data";

type RadarFactorMeta = { key?: string; factor_name?: string; display_name?: string; category?: string; family?: string; expression?: string; weight?: number; normalized_weight?: number; coverage_ratio?: number };
type FactorPreset = "momentum" | "trend" | "risk" | "volume";
type ProviderPreset = "cn" | "us";

const FALLBACK_FACTORS: BackendFactorInfo[] = [
  { factor_name: "MOM_RET_N_D_V1", display_name: "N-day momentum return", category: "MOM", description: "close / close.shift(N) - 1", parameter_schema: { n: { type: "int", default: 20, min: 1, max: 252 } } },
  { factor_name: "TREND_MA_BIAS_N_D_V1", display_name: "N-day MA bias", category: "TREND", description: "close / MA(N) - 1", parameter_schema: { n: { type: "int", default: 20, min: 2, max: 252 } } },
  { factor_name: "QLIB_ALPHA_SUMP20_V1", display_name: "Qlib Alpha SUMP20", category: "QLIB_COUNTING", description: "Share of positive close movement over 20 days.", parameter_schema: { family: { value: "movement_share" }, expression: { value: "SUMP20" } } },
  { factor_name: "QLIB_ALPHA_MA60_V1", display_name: "Qlib Alpha MA60", category: "QLIB_TREND", description: "60-day moving average relative to close.", parameter_schema: { family: { value: "moving_average" }, expression: { value: "Mean($close,60)/$close" } } },
];

const CATEGORY_LABELS: Record<string, { zh: string; en: string }> = {
  MOM: { zh: "传统动量", en: "Classic Momentum" },
  TREND: { zh: "传统趋势", en: "Classic Trend" },
  QLIB_CANDLE_SHAPE: { zh: "K线形态", en: "Candle Shape" },
  QLIB_PRICE_LEVEL: { zh: "价格位置", en: "Price Level" },
  QLIB_TREND: { zh: "Qlib趋势", en: "Qlib Trend" },
  QLIB_MOMENTUM: { zh: "Qlib动量", en: "Qlib Momentum" },
  QLIB_VOLATILITY: { zh: "波动率", en: "Volatility" },
  QLIB_VOLUME: { zh: "量能", en: "Volume" },
  QLIB_VOLUME_PRICE: { zh: "量价关系", en: "Volume-Price" },
  QLIB_POSITION: { zh: "通道位置", en: "Channel Position" },
  QLIB_COUNTING: { zh: "涨跌统计", en: "Up/Down Counts" },
};

function formatNumber(value: unknown, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toFixed(digits);
}
function formatPercent(value: unknown) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(1)}%`;
}
function csvCell(value: unknown) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}
function errorText(error: unknown, fallback = "Stock radar request failed") {
  if (error && typeof error === "object" && "message" in error) return String((error as { message?: unknown }).message || fallback);
  return fallback;
}
function schemaValue(schema: Record<string, unknown> | undefined, key: string) {
  const item = schema?.[key];
  if (item && typeof item === "object" && "value" in item) return String((item as { value?: unknown }).value ?? "");
  return typeof item === "string" ? item : "";
}
function categoryLabel(category: string | undefined, language: Language) {
  if (!category) return "Unknown";
  const labels = CATEGORY_LABELS[category];
  return labels ? labels[language] : category.replace(/^QLIB_/, "Qlib ").replace(/_/g, " ");
}
function shortFactorName(factorName: string | undefined) {
  if (!factorName) return "-";
  return factorName.replace(/^QLIB_ALPHA_/, "").replace(/_V1$/, "").replace(/_N_D_V1$/, "");
}
function factorDisplayName(factor: BackendFactorInfo | RadarFactorMeta | undefined) {
  if (!factor) return "-";
  return factor.display_name || shortFactorName(factor.factor_name);
}
function hasNParam(factorName: string | undefined, factorByName: Map<string, BackendFactorInfo>) {
  if (!factorName) return false;
  if (factorName === "MOM_RET_N_D_V1" || factorName === "TREND_MA_BIAS_N_D_V1") return true;
  return Boolean(factorByName.get(factorName)?.parameter_schema?.n);
}
function getFactorDescription(factorName: string | undefined, factorByName: Map<string, BackendFactorInfo>, language: Language, advancedMode: boolean) {
  if (!factorName) return "";
  const factor = factorByName.get(factorName);
  if (!advancedMode) {
    const category = categoryLabel(factor?.category, language);
    return language === "zh"
      ? `用于衡量${category}特征，并参与综合排序。`
      : `Measures ${category.toLowerCase()} characteristics for the composite ranking.`;
  }
  const family = schemaValue(factor?.parameter_schema, "family");
  const expression = schemaValue(factor?.parameter_schema, "expression");
  return [factor?.description || factor?.display_name || factorName, family ? `Family: ${family}` : "", expression ? `Expression: ${expression}` : ""].filter(Boolean).join(" | ");
}
function buildFactorOptions(factors: BackendFactorInfo[], language: Language, advancedMode: boolean) {
  const grouped = new Map<string, BackendFactorInfo[]>();
  factors.forEach((factor) => grouped.set(factor.category || "UNKNOWN", [...(grouped.get(factor.category || "UNKNOWN") || []), factor]));
  return Array.from(grouped.entries()).sort(([a], [b]) => categoryLabel(a, language).localeCompare(categoryLabel(b, language))).map(([category, items]) => ({
    label: `${categoryLabel(category, language)} (${items.length})`,
    options: items.slice().sort((a, b) => a.factor_name.localeCompare(b.factor_name)).map((factor) => {
      const family = schemaValue(factor.parameter_schema, "family");
      const code = schemaValue(factor.parameter_schema, "qlib_code") || shortFactorName(factor.factor_name);
      const label = advancedMode
        ? `${code} · ${factor.display_name || factor.factor_name}${family ? ` · ${family}` : ""}`
        : `${factor.display_name || code} · ${categoryLabel(factor.category, language)}`;
      return { label, value: factor.factor_name, searchText: `${factor.factor_name} ${factor.display_name || ""} ${factor.description || ""} ${family}` };
    }),
  }));
}
function presetFactors(preset: FactorPreset): StockRadarFactorSpec[] {
  if (preset === "trend") return [
    { factor_name: "QLIB_ALPHA_BETA20_V1", params: {}, weight: 0.45, direction: "positive" },
    { factor_name: "QLIB_ALPHA_RSQR20_V1", params: {}, weight: 0.25, direction: "positive" },
    { factor_name: "QLIB_ALPHA_MA60_V1", params: {}, weight: 0.3, direction: "negative" },
  ];
  if (preset === "risk") return [
    { factor_name: "QLIB_ALPHA_STD20_V1", params: {}, weight: 0.45, direction: "negative" },
    { factor_name: "QLIB_ALPHA_WVMA20_V1", params: {}, weight: 0.25, direction: "negative" },
    { factor_name: "QLIB_ALPHA_KUP2_V1", params: {}, weight: 0.3, direction: "negative" },
  ];
  if (preset === "volume") return [
    { factor_name: "QLIB_ALPHA_VSUMP20_V1", params: {}, weight: 0.35, direction: "positive" },
    { factor_name: "QLIB_ALPHA_CORR20_V1", params: {}, weight: 0.25, direction: "positive" },
    { factor_name: "QLIB_ALPHA_ROC20_V1", params: {}, weight: 0.4, direction: "positive" },
  ];
  return [
    { factor_name: "QLIB_ALPHA_ROC20_V1", params: {}, weight: 0.4, direction: "positive" },
    { factor_name: "QLIB_ALPHA_RANK20_V1", params: {}, weight: 0.25, direction: "positive" },
    { factor_name: "QLIB_ALPHA_SUMP20_V1", params: {}, weight: 0.35, direction: "positive" },
  ];
}

function normalizePreset(value: string | null): FactorPreset {
  return value === "trend" || value === "risk" || value === "volume" ? value : "momentum";
}

function normalizeProvider(value: string | null): ProviderPreset {
  return value === "us" ? "us" : "cn";
}

function positiveInt(value: string | null, fallback: number, max: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.min(Math.floor(parsed), max);
}

function readRadarDefaults(params: Pick<URLSearchParams, "get" | "has">) {
  const hasContext = ["source", "provider", "preset", "universe", "asset", "symbol", "autoRun"].some((key) => params.has(key));
  if (!hasContext) return null;

  const provider = normalizeProvider(params.get("provider"));
  const universe = params.get("universe")?.trim() || (provider === "us" ? "sp500" : "csi300");
  return {
    provider,
    preset: normalizePreset(params.get("preset")),
    universe,
    asset: params.get("asset")?.trim() || params.get("symbol")?.trim() || "",
    source: params.get("source")?.trim() || "",
    autoRun: params.get("autoRun") === "1",
    instrumentLimit: positiveInt(params.get("instrument_limit"), provider === "us" ? 500 : 300, 6000),
    topn: positiveInt(params.get("topn"), provider === "us" ? 10 : 50, 1000),
  };
}

export default function StockRadarPage() {
  const initializedSearchRef = useRef("");
  const { language } = useLanguage();
  const [advancedMode] = useAdvancedMode();
  const zh = language === "zh";
  const t = useCallback((cn: string, en: string) => (zh ? cn : en), [zh]);
  const [form] = Form.useForm<StockRadarPayload>();
  const [loading, setLoading] = useState(false);
  const [loadingFactors, setLoadingFactors] = useState(false);
  const [factorInfos, setFactorInfos] = useState<BackendFactorInfo[]>([]);
  const [factorLoadError, setFactorLoadError] = useState<string | null>(null);
  const [result, setResult] = useState<StockRadarResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [assetQuery, setAssetQuery] = useState("");
  const [providerPreset, setProviderPreset] = useState<ProviderPreset>("cn");
  const [entryContext, setEntryContext] = useState("");

  const factorSource = factorInfos.length > 0 ? factorInfos : FALLBACK_FACTORS;
  const factorByName = useMemo(() => new Map(factorSource.map((factor) => [factor.factor_name, factor])), [factorSource]);
  const factorOptions = useMemo(() => buildFactorOptions(factorSource, language, advancedMode), [advancedMode, factorSource, language]);
  const qlibAlphaCount = useMemo(() => factorSource.filter((factor) => factor.factor_name.startsWith("QLIB_ALPHA_")).length, [factorSource]);
  const categoryStats = useMemo(() => {
    const counts = new Map<string, number>();
    factorSource.forEach((factor) => counts.set(factor.category || "UNKNOWN", (counts.get(factor.category || "UNKNOWN") || 0) + 1));
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [factorSource]);

  useEffect(() => {
    let active = true;
    setLoadingFactors(true);
    listFactorMetadata().then((items) => {
      if (!active) return;
      setFactorInfos(items);
      setFactorLoadError(null);
    }).catch((e) => {
      if (!active) return;
      setFactorLoadError(errorText(e, t("选股雷达请求失败", "Stock radar request failed")));
    }).finally(() => {
      if (active) setLoadingFactors(false);
    });
    return () => { active = false; };
  }, [t]);

  const submit = useCallback(async (values: StockRadarPayload) => {
    setLoading(true);
    setError(null);
    try {
      const payload: StockRadarPayload = {
        ...values,
        provider_uri: values.provider_uri || DEFAULT_PROVIDER_URI,
        instrument_limit: values.instrument_limit ?? 300,
        topn: values.topn ?? 50,
        winsorize_q: values.winsorize_q ?? 0.01,
        min_factor_count: values.min_factor_count ?? 1,
        min_score: values.min_score === undefined ? null : values.min_score,
        start_date: values.start_date || null,
        end_date: values.end_date || null,
        asof_date: values.asof_date || null,
        factors: (values.factors || []).filter((factor) => factor.factor_name).map((factor) => ({
          factor_name: factor.factor_name,
          params: hasNParam(factor.factor_name, factorByName) ? { n: Number((factor.params as { n?: unknown } | undefined)?.n ?? 20) } : {},
          weight: Number(factor.weight ?? 1),
          direction: factor.direction || "positive",
        })),
      };
      const response = await runStockRadar(payload);
      setResult(response);
      message.success(t(`雷达计算完成：${response.signal_date}，${response.row_count} 只股票`, `Radar computed: ${response.row_count} names on ${response.signal_date}`));
    } catch (e) {
      const text = errorText(e, t("选股雷达请求失败", "Stock radar request failed"));
      setError(text);
      message.error(text);
    } finally {
      setLoading(false);
    }
  }, [factorByName, t]);

  useEffect(() => {
    const searchKey = typeof window === "undefined" ? "" : window.location.search;
    if (initializedSearchRef.current === searchKey) return;
    const defaults = readRadarDefaults(new URLSearchParams(searchKey));
    if (!defaults) return;
    initializedSearchRef.current = searchKey;

    const nextValues: StockRadarPayload = {
      provider_uri: defaults.provider === "us" ? DEFAULT_US_PROVIDER_URI : DEFAULT_PROVIDER_URI,
      universe: defaults.universe,
      instrument_limit: defaults.instrumentLimit,
      topn: defaults.topn,
      min_factor_count: 1,
      winsorize_q: 0.01,
      min_score: null,
      start_date: null,
      end_date: null,
      asof_date: null,
      factors: presetFactors(defaults.preset),
    };

    setProviderPreset(defaults.provider);
    setAssetQuery(defaults.asset);
    setEntryContext(defaults.source === "dashboard" ? t("已从市场看板接入，预设和候选池已自动带入。", "Connected from Dashboard with preset candidate screening.") : "");
    form.setFieldsValue(nextValues as any);

    if (!defaults.autoRun) return;
    setError(null);
    setResult(buildDemoStockRadar(nextValues));
    const timer = window.setTimeout(() => {
      void submit(nextValues);
    }, 80);
    return () => window.clearTimeout(timer);
  }, [form, submit, t]);

  function applyProviderPreset(next: ProviderPreset) {
    setProviderPreset(next);
    if (next === "us") {
      form.setFieldsValue({
        provider_uri: DEFAULT_US_PROVIDER_URI,
        universe: "sp500",
        instrument_limit: 500,
        topn: 10,
      });
      return;
    }
    form.setFieldsValue({
      provider_uri: DEFAULT_PROVIDER_URI,
      universe: "csi300",
      instrument_limit: 300,
      topn: 50,
    });
  }

  const resultFactorMeta = useMemo(() => {
    const map = new Map<string, RadarFactorMeta>();
    (result?.factors || []).forEach((factor) => {
      const meta = factor as RadarFactorMeta;
      map.set(String(meta.key || meta.factor_name), meta);
    });
    return map;
  }, [result]);
  const factorKeys = useMemo(() => Array.from(resultFactorMeta.keys()), [resultFactorMeta]);
  const rows = useMemo(() => {
    const query = assetQuery.trim().toUpperCase();
    const items = result?.items || [];
    return query ? items.filter((item) => item.asset_code.toUpperCase().includes(query)) : items;
  }, [assetQuery, result]);
  const avgCoverage = useMemo(() => result?.items.length ? result.items.reduce((acc, item) => acc + Number(item.factor_coverage || 0), 0) / result.items.length : null, [result]);

  const renderContributors = useCallback((record: StockRadarItem) => {
    const contributors = (record.top_factor_contributors?.length ? record.top_factor_contributors : factorKeys.map((key) => ({ key, contribution: record.factor_contributions?.[key] ?? null }))).filter((item) => item.contribution !== null).sort((a, b) => Math.abs(Number(b.contribution)) - Math.abs(Number(a.contribution))).slice(0, 4);
    if (!contributors.length) return <Typography.Text type="secondary">-</Typography.Text>;
    return <Space size={[4, 4]} wrap>{contributors.map((item) => {
      const meta = resultFactorMeta.get(item.key);
      return <Tooltip key={item.key} title={factorDisplayName(meta)}><Tag color={Number(item.contribution) >= 0 ? "green" : "red"}>{`${shortFactorName(meta?.factor_name || item.key)} ${formatNumber(item.contribution, 2)}`}</Tag></Tooltip>;
    })}</Space>;
  }, [factorKeys, resultFactorMeta]);

  const renderBreakdown = useCallback((record: StockRadarItem) => {
    return <div className={styles.breakdownGrid}>{factorKeys.map((key) => {
      const meta = resultFactorMeta.get(key);
      return <div key={key} className={styles.breakdownCard}>
        <div className={styles.breakdownHead}><Typography.Text strong>{shortFactorName(meta?.factor_name || key)}</Typography.Text><Tag>{categoryLabel(meta?.category, language)}</Tag></div>
        <Typography.Text className={styles.breakdownExpression} ellipsis={{ tooltip: advancedMode ? meta?.expression : undefined }}>{advancedMode ? (meta?.expression || factorDisplayName(meta)) : factorDisplayName(meta)}</Typography.Text>
        {!advancedMode ? <Progress percent={Math.min(100, Math.abs(Number(record.factor_contributions?.[key] || 0)) * 100)} showInfo={false} size="small" strokeColor={Number(record.factor_contributions?.[key] || 0) >= 0 ? "#0f9f8f" : "#ef4444"} /> : null}
        <div className={styles.breakdownStats}>
          {advancedMode ? <span>{t("原值", "Raw")}: {formatNumber(record.factor_values[key])}</span> : null}
          {advancedMode ? <span>Z: {formatNumber(record.factor_scores[key])}</span> : null}
          <span>{t("贡献", "Contribution")}: {formatNumber(record.factor_contributions?.[key])}</span>
          <span>{t("分位", "Rank pct")}: {formatPercent(record.factor_ranks[key])}</span>
        </div>
      </div>;
    })}</div>;
  }, [advancedMode, factorKeys, language, resultFactorMeta, t]);

  const columns: ColumnsType<StockRadarItem> = useMemo(() => [
    { title: t("排名", "Rank"), dataIndex: "rank", key: "rank", width: 72, fixed: "left" },
    { title: t("代码", "Code"), dataIndex: "asset_code", key: "asset_code", width: 126, fixed: "left", render: (value) => <Typography.Text strong>{value}</Typography.Text> },
    { title: t("综合分", "Score"), dataIndex: "score", key: "score", width: 150, render: (value, record) => <div className={styles.scoreCell}><Tag color={Number(value) >= 0 ? "green" : "red"}>{formatNumber(value)}</Tag><Progress percent={Math.round(Number(record.score_percentile || 0) * 100)} size="small" showInfo={false} /></div> },
    { title: t("分位", "Pct"), dataIndex: "score_percentile", key: "score_percentile", width: 86, render: formatPercent },
    { title: t("覆盖率", "Coverage"), dataIndex: "factor_coverage", key: "factor_coverage", width: 108, render: formatPercent },
    { title: t("收盘", "Close"), dataIndex: "close", key: "close", width: 98, render: (value) => formatNumber(value, 3) },
    { title: t("成交量", "Volume"), dataIndex: "volume", key: "volume", width: 126, render: (value) => (value ? Number(value).toLocaleString() : "-") },
    { title: t("主要贡献", "Main contributors"), key: "contributors", width: 280, render: (_, record) => renderContributors(record) },
  ], [renderContributors, t]);

  function exportCsv() {
    if (!result || rows.length === 0) { message.warning(t("没有可导出的雷达结果", "No radar rows to export")); return; }
    const headers = ["rank", "trade_date", "asset_code", "score", "score_percentile", "factor_coverage", "valid_factor_count", "missing_factor_count", "close", "volume", ...factorKeys.flatMap((key) => [`${key}__raw`, `${key}__score`, `${key}__rank`, `${key}__contribution`])];
    const lines = rows.map((row) => [row.rank, row.trade_date, row.asset_code, row.score, row.score_percentile, row.factor_coverage ?? "", row.valid_factor_count ?? "", row.missing_factor_count ?? "", row.close ?? "", row.volume ?? "", ...factorKeys.flatMap((key) => [row.factor_values[key] ?? "", row.factor_scores[key] ?? "", row.factor_ranks[key] ?? "", row.factor_contributions?.[key] ?? ""])].map(csvCell).join(","));
    const url = URL.createObjectURL(new Blob([[headers.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = `stock_radar_${result.universe}_${result.signal_date}.csv`; a.click(); URL.revokeObjectURL(url);
  }

  return <PageContainer title={t("选股雷达", "Stock Radar")} subtitle={advancedMode ? t("按 qlib 因子族群构建多因子横截面排序；因子仅使用 signal_date 及以前数据。", "Build cross-sectional rankings with grouped qlib factor families; factors only use data through signal_date.") : t("基于动量、趋势、波动与量价特征筛选候选池，用于辅助研究与风险识别。", "Screen candidates with momentum, trend, volatility, and volume-price features for research support.")}>
    <div className={styles.radarShell}>
      <section className={styles.hero}><div className={styles.heroContent}><Typography.Title level={1} className={styles.heroTitle}>{advancedMode ? t("Qlib 因子分类雷达", "Qlib Factor Taxonomy Radar") : t("多因子候选池", "Multi-Factor Candidate Pool")}</Typography.Title><Typography.Paragraph className={styles.heroText}>{advancedMode ? t("已接入本地 qlib_bin 日频 OHLCV，并按动量、趋势、波动、量能、K线形态、量价相关等族群组织。", "Local qlib_bin daily OHLCV factors are grouped into momentum, trend, volatility, volume, candle shape, channel position, and volume-price families.") : t("围绕动量、趋势、波动、量能与价格结构生成候选排序，作为策略生成与回测前的研究输入。", "Ranks candidates across momentum, trend, volatility, volume, and price-structure features before strategy generation and backtesting.")}</Typography.Paragraph><Space wrap>{(advancedMode ? [t("真实 qlib_bin 数据", "Real qlib_bin data"), t("按因子族群筛选", "Grouped taxonomy"), t("展开因子贡献", "Contribution drill-down")] : [t("候选池筛选", "Candidate screening"), t("因子贡献解释", "Factor rationale"), t("回测前研究输入", "Pre-backtest input")]).map((tag) => <Tag key={tag} className={styles.heroTag}>{tag}</Tag>)}</Space></div><div className={styles.heroPanel}><div className={styles.radarOrb}><span /></div><div className={styles.heroMetricGrid}><div><Typography.Text className={styles.metricLabel}>{t("可用因子", "Available")}</Typography.Text><Typography.Title level={3} className={styles.metricValue}>{factorSource.length}</Typography.Title></div><div><Typography.Text className={styles.metricLabel}>{advancedMode ? "Qlib Alpha" : t("候选模型", "Models")}</Typography.Text><Typography.Title level={3} className={styles.metricValue}>{qlibAlphaCount}</Typography.Title></div><div><Typography.Text className={styles.metricLabel}>{t("分类", "Categories")}</Typography.Text><Typography.Title level={3} className={styles.metricValue}>{categoryStats.length}</Typography.Title></div><div><Typography.Text className={styles.metricLabel}>{advancedMode ? t("信号日", "Signal date") : t("排序日期", "Ranking date")}</Typography.Text><Typography.Title level={4} className={styles.metricValue}>{result?.signal_date || t("待运行", "Awaiting run")}</Typography.Title></div></div></div></section>
      <Card className={styles.taxonomyCard} title={t("因子分类", "Factor Categories")}><div className={styles.categoryStrip}>{categoryStats.map(([category, count]) => <div key={category} className={styles.categoryPill}><span>{categoryLabel(category, language)}</span><strong>{count}</strong></div>)}</div></Card>
      {entryContext ? <Alert type="info" showIcon message={entryContext} description={t("可以直接查看候选结果，也可以调整因子组合后重新运行。", "Review the generated candidates or adjust the factor mix and run again.")} /> : null}
      {result?.data_health?.blocking_status === "WARN" ? <Alert type="warning" showIcon message={t("数据新鲜度提示", "Data freshness warning")} description={result.data_health.message || result.timing_note} /> : null}
      <Row gutter={[18, 18]}><Col span={24}><Card className={styles.controlCard} title={<span className={styles.cardTitle}>{t("雷达控制台", "Radar Controls")}</span>}><Form form={form} layout="vertical" onFinish={submit} initialValues={{ provider_uri: DEFAULT_PROVIDER_URI, universe: "csi300", instrument_limit: 300, topn: 50, min_factor_count: 1, winsorize_q: 0.01, factors: presetFactors("momentum") }}>
        <Row gutter={12}><Col xs={24} md={8} xl={advancedMode ? 4 : 5}><Form.Item label={t("市场预设", "Market Preset")}><Select value={providerPreset} onChange={applyProviderPreset} options={[{ label: advancedMode ? t("A股 qlib", "CN qlib") : t("A股市场", "CN market"), value: "cn" }, { label: advancedMode ? t("美股 qlib", "US qlib") : t("美股市场", "US market"), value: "us" }]} /></Form.Item></Col>{advancedMode ? <Col xs={24} md={16} xl={8}><Form.Item label={t("Qlib 数据路径", "Qlib Provider URI")} name="provider_uri" rules={[{ required: true, message: t("请输入 provider 路径", "Provider path is required") }]}><Input /></Form.Item></Col> : null}<Col xs={12} md={6} xl={advancedMode ? 4 : 5}><Form.Item label={t("股票池", "Universe")} name="universe" rules={[{ required: true }]}><Select options={[{ label: t("沪深300", "CSI 300"), value: "csi300" }, { label: t("中证500", "CSI 500"), value: "csi500" }, { label: t("中证100", "CSI 100"), value: "csi100" }, { label: "S&P 500", value: "sp500" }, { label: "Nasdaq 100", value: "nasdaq100" }, { label: t("全部标的", "All instruments"), value: "all" }]} /></Form.Item></Col><Col xs={12} md={6} xl={advancedMode ? 3 : 4}><Form.Item label={t("标的上限", "Instrument Limit")} name="instrument_limit"><InputNumber min={1} max={6000} style={{ width: "100%" }} /></Form.Item></Col><Col xs={12} md={6} xl={advancedMode ? 2 : 4}><Form.Item label={advancedMode ? "TopN" : t("返回数量", "Return count")} name="topn"><InputNumber min={1} max={1000} style={{ width: "100%" }} /></Form.Item></Col><Col xs={12} md={6} xl={advancedMode ? 3 : 5}><Form.Item label={t("最低综合分", "Min Score")} name="min_score"><InputNumber step={0.1} style={{ width: "100%" }} placeholder={t("可选", "optional")} /></Form.Item></Col></Row>
        {providerPreset === "us" ? <Alert className={styles.providerNote} type="info" showIcon message={advancedMode ? t("当前 US qlib 为本地维护数据", "Current US qlib is locally maintained") : t("已切换到美股候选池", "US candidate pool selected")} description={advancedMode ? t("本地 US provider 已包含 all、sp500、nasdaq100 股票池；实际新鲜度以 Data Maintenance 审计为准。", "The local US provider includes all, sp500, and nasdaq100 universes; use the Data Maintenance audit as the freshness source of truth.") : t("可选择 S&P 500、Nasdaq 100 或全部标的进行候选筛选。", "Use S&P 500, Nasdaq 100, or all instruments for candidate screening.")} /> : null}
        <Row gutter={12}><Col xs={24} md={12} xl={6}><Form.Item label={t("开始日期", "Start Date")} name="start_date"><Input placeholder="YYYY-MM-DD" /></Form.Item></Col><Col xs={24} md={12} xl={6}><Form.Item label={t("结束日期", "End Date")} name="end_date"><Input placeholder="YYYY-MM-DD" /></Form.Item></Col><Col xs={24} md={12} xl={6}><Form.Item label={t("截至日期", "As-of Date")} name="asof_date"><Input placeholder="YYYY-MM-DD" /></Form.Item></Col><Col xs={24} md={12} xl={6}><Form.Item label={t("去极值分位", "Winsorize Q")} name="winsorize_q"><InputNumber min={0} max={0.25} step={0.005} style={{ width: "100%" }} /></Form.Item></Col></Row>
        <Row gutter={12}><Col xs={24} lg={7} xl={6}><Form.Item label={t("最少有效因子数", "Min Factor Count")} name="min_factor_count" tooltip={t("股票至少要有这么多个有效因子值才进入排名。", "A stock must have at least this many valid factor values.")}><InputNumber min={1} max={20} style={{ width: "100%" }} /></Form.Item></Col><Col xs={24} lg={17} xl={18}>{factorLoadError ? <Alert className={styles.factorStatus} type="warning" showIcon message={t("因子信息暂未完整加载，已使用备用选项。", "Factor metadata is temporarily incomplete; fallback options are available.")} description={advancedMode ? factorLoadError : t("可先继续使用内置因子组合，稍后刷新因子库。", "You can continue with built-in factor presets and refresh the library later.")} /> : <Alert className={styles.factorStatus} type="success" showIcon message={t(`${factorSource.length} 个因子可用${loadingFactors ? "（加载中...）" : ""}`, `${factorSource.length} factors available${loadingFactors ? " (loading...)" : ""}`)} description={advancedMode ? t("分类信息来自后端 factor registry；Qlib 因子由本地 OHLCV 日频数据计算。", "Categories come from the backend registry; Qlib factors are computed from local daily OHLCV data.") : t("因子库已就绪，可用于候选池排序与贡献解释。", "The factor library is ready for candidate ranking and contribution review.")} />}</Col></Row>
        <Divider titlePlacement="left">{t("因子组合", "Factor Combination")}</Divider><div className={styles.presetBar}><Typography.Text strong>{t("快速组合", "Quick presets")}</Typography.Text><Space wrap>{([{ key: "momentum", cn: "动量增强", en: "Momentum" }, { key: "trend", cn: "趋势确认", en: "Trend" }, { key: "risk", cn: "低波筛选", en: "Low-vol" }, { key: "volume", cn: "量价配合", en: "Volume-price" }] as const).map((preset) => <Button key={preset.key} size="small" onClick={() => form.setFieldValue("factors", presetFactors(preset.key))}>{t(preset.cn, preset.en)}</Button>)}</Space></div>
        <Form.List name="factors">{(fields, { add, remove }) => <Space direction="vertical" style={{ width: "100%" }} size={8}>{fields.map(({ key, name }) => <Row gutter={12} key={key} align="top" className={styles.factorRow}><Col xs={24} xl={9}><Form.Item label={t("因子", "Factor")} name={[name, "factor_name"]} rules={[{ required: true }]}><Select showSearch loading={loadingFactors} optionFilterProp="searchText" options={factorOptions} placeholder={t("选择因子", "Select a factor")} /></Form.Item><Form.Item noStyle shouldUpdate>{({ getFieldValue }) => { const factorName = getFieldValue(["factors", name, "factor_name"]); const description = getFactorDescription(factorName, factorByName, language, advancedMode); const factor = factorByName.get(factorName); return description ? <div className={styles.factorMetaBlock}><Tag>{categoryLabel(factor?.category, language)}</Tag><Typography.Paragraph type="secondary" className={styles.factorDescription} ellipsis={{ rows: 2, expandable: true }}>{description}</Typography.Paragraph></div> : null; }}</Form.Item></Col><Form.Item noStyle shouldUpdate>{({ getFieldValue }) => hasNParam(getFieldValue(["factors", name, "factor_name"]), factorByName) ? <Col xs={12} md={6} xl={4}><Form.Item label="N" name={[name, "params", "n"]}><InputNumber min={2} max={252} style={{ width: "100%" }} /></Form.Item></Col> : <Col xs={12} md={6} xl={4}><Form.Item label={t("参数", "Params")}><Typography.Text type="secondary">{advancedMode ? t("固定表达式", "Fixed expression") : t("固定规则", "Fixed rule")}</Typography.Text></Form.Item></Col>}</Form.Item><Col xs={12} md={6} xl={4}><Form.Item label={t("权重", "Weight")} name={[name, "weight"]}><InputNumber step={0.1} style={{ width: "100%" }} /></Form.Item></Col><Col xs={12} md={6} xl={4}><Form.Item label={t("方向", "Direction")} name={[name, "direction"]}><Select options={[{ label: t("高值更好", "High is good"), value: "positive" }, { label: t("低值更好", "Low is good"), value: "negative" }]} /></Form.Item></Col><Col xs={24} xl={3}><Button danger onClick={() => remove(name)} disabled={fields.length <= 1} className={styles.removeButton}>{t("删除", "Remove")}</Button></Col></Row>)}<Button onClick={() => add({ factor_name: "QLIB_ALPHA_ROC20_V1", params: {}, weight: 1, direction: "positive" })}>{t("添加因子", "Add Factor")}</Button></Space>}</Form.List>
        <Divider /><Space wrap><Button type="primary" htmlType="submit" loading={loading} className={styles.runButton}>{t("运行选股雷达", "Run Stock Radar")}</Button><Typography.Text type="secondary">{t("排名在 signal_date 形成；执行应等到下一 qlib 交易日。", "Ranking is formed on signal_date; execution should wait until the next qlib trading day.")}</Typography.Text></Space>
      </Form></Card></Col><Col span={24}><Card className={styles.resultCard} title={t("雷达结果", "Radar Results")} extra={<Space><Input.Search placeholder={t("筛选代码", "Filter code")} allowClear onChange={(event) => setAssetQuery(event.target.value)} style={{ width: 220 }} /><Button onClick={exportCsv} disabled={!result || rows.length === 0}>{t("导出 CSV", "Export CSV")}</Button></Space>}>{error ? <Alert type="error" showIcon style={{ marginBottom: 12 }} message={t("选股雷达请求失败", "Stock radar request failed")} description={advancedMode ? error : t("候选池计算暂不可用，可稍后刷新或调整筛选条件。", "Candidate screening is temporarily unavailable; refresh later or adjust filters.")} /> : null}{result ? <Space direction="vertical" style={{ width: "100%" }} size={12}><Alert className={styles.resultSummary} type="info" showIcon message={advancedMode ? t(`股票池 ${result.universe}，signal_date ${result.signal_date}，trade_from ${result.effective_trade_date}，打分前 ${result.row_count_before_score_filter} 只股票。`, `Universe ${result.universe}, signal_date ${result.signal_date}, trade_from ${result.effective_trade_date}, ${result.row_count_before_score_filter} names before score filter.`) : t(`股票池 ${result.universe}，排序日期 ${result.signal_date}，可观察起始日 ${result.effective_trade_date}，初筛 ${result.row_count_before_score_filter} 只股票。`, `Universe ${result.universe}, ranking date ${result.signal_date}, observable from ${result.effective_trade_date}, ${result.row_count_before_score_filter} names before score filter.`)} description={advancedMode ? result.timing_note : t("结果用于辅助研究与风险识别，不构成投资建议。", "Results support research and risk review; not financial advice.")} /><div className={styles.summaryGrid}><div className={styles.summaryTile}><span>{t("当日样本", "Loaded")}</span><strong>{result.row_count_on_signal_date ?? result.row_count_before_score_filter}</strong></div><div className={styles.summaryTile}><span>{t("返回标的", "Returned")}</span><strong>{result.row_count}</strong></div><div className={styles.summaryTile}><span>{t("最高得分", "Top score")}</span><strong>{formatNumber(result.items[0]?.score)}</strong></div><div className={styles.summaryTile}><span>{t("平均覆盖", "Avg coverage")}</span><strong>{formatPercent(avgCoverage)}</strong></div></div><Table size="small" rowKey={(record) => `${record.trade_date}-${record.asset_code}`} columns={columns} dataSource={rows} expandable={{ expandedRowRender: renderBreakdown }} scroll={{ x: 1040 }} rowClassName={(_, index) => (index < 3 ? styles.topRankRow : "")} pagination={{ pageSize: 50, showSizeChanger: true }} /></Space> : <Alert type="warning" showIcon message={t("还没有雷达结果", "No radar result yet")} description={t("选择股票池和因子组合后，点击运行选股雷达。", "Choose a universe and factor combination, then run the radar.")} />}</Card></Col></Row>
    </div>
  </PageContainer>;
}
