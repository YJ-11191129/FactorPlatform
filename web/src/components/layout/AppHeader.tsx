"use client";

import {
  ApiOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  FundProjectionScreenOutlined,
  LineChartOutlined,
  RobotOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Layout, Segmented, Space, Switch, Tag, Typography } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import styles from "@/components/layout/layout.module.css";
import { allowMockFallback, demoReadOnly, mockModeLabel } from "@/lib/api/mockPolicy";
import { listLiveSignals } from "@/lib/api/signal-center";
import { useAdvancedMode } from "@/lib/advanced-mode";
import { useLanguage, type Language } from "@/lib/i18n";

const { Header } = Layout;

const headerCopy = {
  zh: {
    product: "智能投研平台",
    subtitle: "研究工作台",
    dashboard: "市场看板",
    stockRadar: "AI 选股",
    signals: "宏观情报",
    backtests: "策略回测",
    performance: "绩效归因",
    factors: "因子分析",
    data: "数据维护",
    settings: "系统设置",
    advanced: "研究模式",
  },
  en: {
    product: "FactorPlatform",
    subtitle: "Research Workspace",
    dashboard: "Dashboard",
    stockRadar: "AI Picks",
    signals: "Macro Intel",
    backtests: "Backtest",
    performance: "Performance",
    factors: "Factors",
    data: "Data",
    settings: "Settings",
    advanced: "Research mode",
  },
} as const;

export function AppHeader() {
  const pathname = usePathname();
  const { language, setLanguage } = useLanguage();
  const [advancedMode, setAdvancedMode] = useAdvancedMode();
  const copy = headerCopy[language];
  const [apiState, setApiState] = useState<"checking" | "ok" | "error">("checking");
  const [snapshotStatus, setSnapshotStatus] = useState<string>("NO_SNAPSHOT");
  const isDemoFallback = allowMockFallback();

  useEffect(() => {
    if (!advancedMode) return;
    let alive = true;
    setApiState("checking");
    listLiveSignals({ page: 1, page_size: 1 })
      .then((res) => {
        if (!alive) return;
        setApiState("ok");
        setSnapshotStatus(res.status || "UNKNOWN");
      })
      .catch(() => {
        if (!alive) return;
        setApiState("error");
        setSnapshotStatus("UNAVAILABLE");
      });
    return () => {
      alive = false;
    };
  }, [advancedMode]);

  const navItems = useMemo(
    () =>
      [
        { href: "/dashboard", label: copy.dashboard, icon: BarChartOutlined, match: ["/dashboard"], advanced: false },
        { href: "/stock-radar", label: copy.stockRadar, icon: RobotOutlined, match: ["/stock-radar"], advanced: false },
        { href: "/macro-intel", label: copy.signals, icon: ThunderboltOutlined, match: ["/macro-intel"], advanced: false },
        { href: "/strategies", label: copy.backtests, icon: FundProjectionScreenOutlined, match: ["/strategies", "/backtests"], advanced: false },
        { href: "/performance", label: copy.performance, icon: LineChartOutlined, match: ["/performance"], advanced: false },
        { href: "/factors", label: copy.factors, icon: LineChartOutlined, match: ["/factors"], advanced: true },
        { href: "/data-maintenance", label: copy.data, icon: DatabaseOutlined, match: ["/data-maintenance"], advanced: true },
        { href: "/settings", label: copy.settings, icon: SettingOutlined, match: ["/settings"], advanced: true },
      ].filter((item) => advancedMode || !item.advanced),
    [advancedMode, copy],
  );

  return (
    <Header className={styles.header}>
      <div className={styles.headerInner}>
        <Link href="/dashboard" className={styles.topBrand} aria-label="FactorPlatform dashboard">
          <span className={styles.topBrandMark}>
            <AppstoreOutlined />
          </span>
          <span className={styles.topBrandText}>
            <Typography.Text className={styles.topBrandTitle}>{copy.product}</Typography.Text>
            <Typography.Text className={styles.topBrandSubtitle}>{copy.subtitle}</Typography.Text>
          </span>
        </Link>

        <nav className={styles.topNav} aria-label="Application navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.match.some((prefix) => pathname.startsWith(prefix));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.topNavLink} ${active ? styles.topNavLinkActive : ""}`}
              >
                <Icon />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <Space size={8} className={styles.headerActions}>
          {advancedMode ? (
            <>
              <Tag className={styles.statusTag} color={apiState === "ok" ? "success" : apiState === "checking" ? "processing" : "error"}>
                <ApiOutlined /> API {apiState.toUpperCase()}
              </Tag>
              <Tag className={styles.statusTag}>Snapshot {snapshotStatus}</Tag>
              <Tag className={isDemoFallback ? styles.demoModeTag : styles.modeTag}>
                {mockModeLabel().toUpperCase()}
                {isDemoFallback && demoReadOnly() ? " / READ ONLY" : ""}
              </Tag>
            </>
          ) : null}
          <span className={styles.advancedSwitch}>
            <Switch size="small" checked={advancedMode} onChange={setAdvancedMode} />
            <span>{copy.advanced}</span>
          </span>
          <Segmented
            size="small"
            value={language}
            className={styles.languageSwitch}
            options={[
              { label: "中", value: "zh" },
              { label: "EN", value: "en" },
            ]}
            onChange={(value) => setLanguage(value as Language)}
          />
        </Space>
      </div>
    </Header>
  );
}
