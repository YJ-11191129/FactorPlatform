"use client";

import { ConfigProvider, theme } from "antd";
import type { ReactNode } from "react";

import { LanguageProvider } from "@/lib/i18n";

export function AntdProvider(props: { children: ReactNode }) {
  return (
    <LanguageProvider>
      <ConfigProvider
        theme={{
          algorithm: theme.darkAlgorithm,
          token: {
            borderRadius: 14,
            borderRadiusLG: 20,
            colorPrimary: "#38bdf8",
            colorInfo: "#38bdf8",
            colorSuccess: "#34d399",
            colorWarning: "#fbbf24",
            colorError: "#fb7185",
            colorBgLayout: "#07111f",
            colorBgContainer: "#0f1b2e",
            colorBgElevated: "#16243a",
            colorText: "#f8fafc",
            colorTextSecondary: "#a8b4c6",
            colorTextTertiary: "#718096",
            colorBorder: "rgba(203, 213, 225, 0.14)",
            colorBorderSecondary: "rgba(203, 213, 225, 0.1)",
            boxShadow: "0 18px 45px rgba(2, 8, 23, 0.26)",
          },
          components: {
            Layout: {
              headerBg: "transparent",
              bodyBg: "#07111f",
              siderBg: "#09182a",
            },
            Menu: {
              darkItemBg: "#09182a",
              darkSubMenuItemBg: "#09182a",
              darkItemSelectedBg: "rgba(56, 189, 248, 0.16)",
              darkItemHoverBg: "rgba(168, 180, 198, 0.1)",
              darkItemColor: "rgba(226, 232, 240, 0.76)",
              darkItemSelectedColor: "#ffffff",
            },
            Card: {
              headerBg: "transparent",
              colorBgContainer: "#0f1b2e",
            },
            Table: {
              headerBg: "#132035",
              headerColor: "#a8b4c6",
              rowHoverBg: "rgba(56, 189, 248, 0.07)",
              borderColor: "rgba(203, 213, 225, 0.1)",
            },
            Button: {
              primaryShadow: "0 12px 26px rgba(56, 189, 248, 0.18)",
            },
          },
        }}
      >
        {props.children}
      </ConfigProvider>
    </LanguageProvider>
  );
}
