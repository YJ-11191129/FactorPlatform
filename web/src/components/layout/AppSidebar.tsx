"use client";

import {
  BarChartOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  FundProjectionScreenOutlined,
  GlobalOutlined,
  HistoryOutlined,
  LineChartOutlined,
  RadarChartOutlined,
  RobotOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Segmented, Typography } from "antd";
import Link from "next/link";
import { useMemo } from "react";

import styles from "@/components/layout/layout.module.css";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { useLanguage, type Language } from "@/lib/i18n";

const { Sider } = Layout;

const sidebarCopy = {
  zh: {
    console: "研究工作台",
    language: "语言",
    dashboard: "市场看板",
    stockRadar: "AI 选股",
    signalCenter: "新闻筛选",
    signalHistory: "信号历史",
    macroIntel: "宏观情报",
    performance: "绩效归因",
    regimeMonitor: "市场状态",
    marketDashboard: "TradingView 看板",
    dataMaintenance: "数据维护",
    strategyRouter: "策略路由",
    factors: "因子分析",
    aiStrategy: "AI 策略生成",
    backtests: "策略回测",
    runs: "运行记录",
    settings: "系统设置",
  },
  en: {
    console: "Research Workspace",
    language: "Language",
    dashboard: "Dashboard",
    stockRadar: "AI Picks",
    signalCenter: "News Signals",
    signalHistory: "Signal History",
    macroIntel: "Macro Intelligence",
    performance: "Performance",
    regimeMonitor: "Regime Monitor",
    marketDashboard: "TradingView",
    dataMaintenance: "Data Maintenance",
    strategyRouter: "Strategy Router",
    factors: "Factors",
    aiStrategy: "AI Strategy Builder",
    backtests: "Backtest",
    runs: "Runs",
    settings: "Settings",
  },
} as const;

export function AppSidebar(props: { pathname: string }) {
  const { language, setLanguage } = useLanguage();
  const [advancedMode] = useAdvancedMode();
  const copy = sidebarCopy[language];
  const items = useMemo(
    () =>
      [
        { key: "/dashboard", icon: <BarChartOutlined />, label: <Link href="/dashboard">{copy.dashboard}</Link>, advanced: false },
        { key: "/stock-radar", icon: <RadarChartOutlined />, label: <Link href="/stock-radar">{copy.stockRadar}</Link>, advanced: false },
        { key: "/signal-center", icon: <ThunderboltOutlined />, label: <Link href="/signal-center">{copy.signalCenter}</Link>, advanced: false },
        { key: "/strategies", icon: <FundProjectionScreenOutlined />, label: <Link href="/strategies">{copy.backtests}</Link>, advanced: false },
        { key: "/performance", icon: <LineChartOutlined />, label: <Link href="/performance">{copy.performance}</Link>, advanced: false },
        { key: "/regime-monitor", icon: <RadarChartOutlined />, label: <Link href="/regime-monitor">{copy.regimeMonitor}</Link>, advanced: false },
        { key: "/factors", icon: <LineChartOutlined />, label: <Link href="/factors">{copy.factors}</Link>, advanced: true },
        { key: "/ai-strategy-builder", icon: <RobotOutlined />, label: <Link href="/ai-strategy-builder">{copy.aiStrategy}</Link>, advanced: true },
        { key: "/tradingview", icon: <BarChartOutlined />, label: <Link href="/tradingview">{copy.marketDashboard}</Link>, advanced: true },
        { key: "/signal-history", icon: <HistoryOutlined />, label: <Link href="/signal-history">{copy.signalHistory}</Link>, advanced: true },
        { key: "/macro-intel", icon: <GlobalOutlined />, label: <Link href="/macro-intel">{copy.macroIntel}</Link>, advanced: true },
        { key: "/data-maintenance", icon: <DatabaseOutlined />, label: <Link href="/data-maintenance">{copy.dataMaintenance}</Link>, advanced: true },
        { key: "/strategy-router", icon: <DeploymentUnitOutlined />, label: <Link href="/strategy-router">{copy.strategyRouter}</Link>, advanced: true },
        { key: "/runs", icon: <DeploymentUnitOutlined />, label: <Link href="/runs">{copy.runs}</Link>, advanced: true },
        { key: "/settings", icon: <SettingOutlined />, label: <Link href="/settings">{copy.settings}</Link>, advanced: true },
      ].filter((item) => advancedMode || !item.advanced),
    [advancedMode, copy],
  );

  const selectedKey =
    props.pathname.startsWith("/dashboard")
      ? "/dashboard"
      : props.pathname.startsWith("/signal-center")
        ? "/signal-center"
        : props.pathname.startsWith("/signal-history")
          ? "/signal-history"
          : props.pathname.startsWith("/stock-radar")
            ? "/stock-radar"
            : props.pathname.startsWith("/macro-intel")
              ? "/macro-intel"
              : props.pathname.startsWith("/performance")
                ? "/performance"
                : props.pathname.startsWith("/regime-monitor")
                  ? "/regime-monitor"
                  : props.pathname.startsWith("/tradingview")
                    ? "/tradingview"
                    : props.pathname.startsWith("/data-maintenance")
                      ? "/data-maintenance"
                      : props.pathname.startsWith("/strategy-router")
                        ? "/strategy-router"
                        : props.pathname.startsWith("/ai-strategy-builder")
                          ? "/ai-strategy-builder"
                          : props.pathname.startsWith("/factors")
                            ? "/factors"
                            : props.pathname.startsWith("/runs")
                              ? "/runs"
                              : props.pathname.startsWith("/strategies") || props.pathname.startsWith("/backtests")
                                ? "/strategies"
                                : props.pathname.startsWith("/settings")
                                  ? "/settings"
                                  : "/dashboard";

  return (
    <Sider
      className={styles.sider}
      width={284}
      theme="dark"
      breakpoint="lg"
      collapsedWidth={0}
    >
      <div className={styles.brand}>
        <div className={styles.brandMark}>FP</div>
        <div className={styles.brandText}>
          <Typography.Text className={styles.brandTitle}>FactorPlatform</Typography.Text>
          <Typography.Text className={styles.brandSubtitle}>{copy.console}</Typography.Text>
        </div>
      </div>
      <div className={styles.sidebarPanel}>
        <Typography.Text className={styles.sidebarLabel}>{copy.language}</Typography.Text>
        <Segmented
          block
          size="small"
          value={language}
          options={[
            { label: "中文", value: "zh" },
            { label: "English", value: "en" },
          ]}
          onChange={(value) => setLanguage(value as Language)}
        />
      </div>
      <Menu className={styles.sidebarMenu} mode="inline" theme="dark" selectedKeys={[selectedKey]} items={items} />
    </Sider>
  );
}
