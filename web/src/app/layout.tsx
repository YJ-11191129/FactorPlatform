import type { Metadata } from "next";
import "./globals.css";
import "antd/dist/reset.css";

import { AntdRegistry } from "@ant-design/nextjs-registry";

import { AppShell } from "@/components/layout/AppShell";
import { AntdProvider } from "@/components/layout/AntdProvider";

export const metadata: Metadata = {
  title: "FactorPlatform | AI Market Intelligence",
  description: "Risk-aware AI market intelligence and research terminal for structured signal screening, scenario analysis, and decision support.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <AntdRegistry>
          <AntdProvider>
            <AppShell>{children}</AppShell>
          </AntdProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}
