"use client";

import { ConfigProvider, Layout, theme } from "antd";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AppHeader } from "@/components/layout/AppHeader";
import styles from "@/components/layout/layout.module.css";

const { Content } = Layout;

const lightAppTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    borderRadius: 10,
    borderRadiusLG: 12,
    colorPrimary: "#008B8B",
    colorInfo: "#008B8B",
    colorSuccess: "#059669",
    colorWarning: "#D97706",
    colorError: "#DC2626",
    colorBgLayout: "#F8FBFC",
    colorBgContainer: "#FFFFFF",
    colorBgElevated: "#FFFFFF",
    colorText: "#0F172A",
    colorTextSecondary: "#526173",
    colorTextTertiary: "#7A8A9D",
    colorBorder: "#D6E4EC",
    colorBorderSecondary: "#E6EFF4",
    boxShadow: "0 18px 42px rgba(15, 23, 42, 0.08)",
  },
  components: {
    Layout: {
      headerBg: "transparent",
      bodyBg: "#F8FBFC",
    },
    Card: {
      headerBg: "#FFFFFF",
      colorBgContainer: "#FFFFFF",
    },
    Table: {
      headerBg: "#F4F8FA",
      headerColor: "#526173",
      rowHoverBg: "#F2FBFA",
      borderColor: "#E6EFF4",
    },
    Tag: {
      defaultBg: "#F4FAFA",
      defaultColor: "#007A7A",
    },
    Button: {
      primaryShadow: "0 10px 22px rgba(0, 139, 139, 0.16)",
    },
  },
};

export function AppShell(props: { children: ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/") {
    return <>{props.children}</>;
  }

  return (
    <ConfigProvider theme={lightAppTheme}>
      <Layout className={styles.appShell}>
        <Layout className={styles.mainShell}>
          <AppHeader />
          <Content className={styles.content}>
            <main className={styles.contentCanvas}>{props.children}</main>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}
