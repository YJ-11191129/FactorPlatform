"use client";

import {
  BarChartOutlined,
  BellOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  FundProjectionScreenOutlined,
  GlobalOutlined,
  HistoryOutlined,
  LineChartOutlined,
  NotificationOutlined,
  RadarChartOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Segmented, Typography } from "antd";
import Link from "next/link";
import { useMemo } from "react";

import styles from "@/components/layout/layout.module.css";
import { useLanguage, type Language } from "@/lib/i18n";

const { Sider } = Layout;

const sidebarCopy = {
  zh: {
    console: "\u7814\u7a76\u63a7\u5236\u53f0",
    language: "\u8bed\u8a00",
    signalCenter: "\u4fe1\u53f7\u4e2d\u5fc3",
    signalHistory: "\u4fe1\u53f7\u5386\u53f2",
    stockRadar: "\u9009\u80a1\u96f7\u8fbe",
    macroIntel: "\u5b8f\u89c2\u60c5\u62a5",
    performance: "\u7ee9\u6548\u5f52\u56e0",
    regimeMonitor: "\u5e02\u573a\u72b6\u6001",
    marketDashboard: "\u884c\u60c5\u9762\u677f",
    dataMaintenance: "\u6570\u636e\u7ef4\u62a4",
    strategyRouter: "\u7b56\u7565\u8def\u7531",
    backtests: "\u56de\u6d4b\u5de5\u4f5c\u53f0",
    shockLibrary: "\u51b2\u51fb\u5e93\uff08\u5f85\u63a5\u5165\uff09",
    notifications: "\u901a\u77e5\u4e2d\u5fc3\uff08\u5f85\u63a5\u5165\uff09",
    settings: "\u7cfb\u7edf\u8bbe\u7f6e",
  },
  en: {
    console: "Research Console",
    language: "Language",
    signalCenter: "Signal Center",
    signalHistory: "Signal History",
    stockRadar: "Stock Radar",
    macroIntel: "Macro Intelligence",
    performance: "Performance",
    regimeMonitor: "Regime Monitor",
    marketDashboard: "Market Dashboard",
    dataMaintenance: "Data Maintenance",
    strategyRouter: "Strategy Router",
    backtests: "Backtest Lab",
    shockLibrary: "Shock Library (Soon)",
    notifications: "Notifications (Soon)",
    settings: "Settings",
  },
} as const;

export function AppSidebar(props: { pathname: string }) {
  const { language, setLanguage } = useLanguage();
  const copy = sidebarCopy[language];
  const items = useMemo(
    () => [
      { key: "/signal-center", icon: <ThunderboltOutlined />, label: <Link href="/signal-center">{copy.signalCenter}</Link> },
      { key: "/signal-history", icon: <HistoryOutlined />, label: <Link href="/signal-history">{copy.signalHistory}</Link> },
      { key: "/stock-radar", icon: <RadarChartOutlined />, label: <Link href="/stock-radar">{copy.stockRadar}</Link> },
      { key: "/macro-intel", icon: <GlobalOutlined />, label: <Link href="/macro-intel">{copy.macroIntel}</Link> },
      { key: "/performance", icon: <FundProjectionScreenOutlined />, label: <Link href="/performance">{copy.performance}</Link> },
      { key: "/regime-monitor", icon: <RadarChartOutlined />, label: <Link href="/regime-monitor">{copy.regimeMonitor}</Link> },
      { key: "/tradingview", icon: <BarChartOutlined />, label: <Link href="/tradingview">{copy.marketDashboard}</Link> },
      { key: "/data-maintenance", icon: <DatabaseOutlined />, label: <Link href="/data-maintenance">{copy.dataMaintenance}</Link> },
      { key: "/strategy-router", icon: <DeploymentUnitOutlined />, label: <Link href="/strategy-router">{copy.strategyRouter}</Link> },
      { key: "/strategies", icon: <LineChartOutlined />, label: <Link href="/strategies">{copy.backtests}</Link> },
      { key: "/shock-library", icon: <NotificationOutlined />, label: <span className={styles.disabledMenuItem}>{copy.shockLibrary}</span> },
      { key: "/notifications", icon: <BellOutlined />, label: <span className={styles.disabledMenuItem}>{copy.notifications}</span> },
      { key: "/settings", icon: <SettingOutlined />, label: <Link href="/settings">{copy.settings}</Link> },
    ],
    [copy],
  );

  const selectedKey =
    props.pathname.startsWith("/signal-center")
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
                      : props.pathname.startsWith("/strategies") || props.pathname.startsWith("/backtests")
                        ? "/strategies"
                        : props.pathname.startsWith("/settings")
                          ? "/settings"
                          : "/signal-center";

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
            { label: "\u4e2d\u6587", value: "zh" },
            { label: "English", value: "en" },
          ]}
          onChange={(value) => setLanguage(value as Language)}
        />
      </div>
      <Menu className={styles.sidebarMenu} mode="inline" theme="dark" selectedKeys={[selectedKey]} items={items} />
    </Sider>
  );
}
