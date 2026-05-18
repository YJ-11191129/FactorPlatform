"use client";

import { Layout } from "antd";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AppHeader } from "@/components/layout/AppHeader";
import { AppSidebar } from "@/components/layout/AppSidebar";
import styles from "@/components/layout/layout.module.css";

const { Content } = Layout;

export function AppShell(props: { children: ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/") {
    return <>{props.children}</>;
  }

  return (
    <Layout className={styles.appShell}>
      <AppSidebar pathname={pathname} />
      <Layout className={styles.mainShell}>
        <AppHeader />
        <Content className={styles.content}>
          <main className={styles.contentCanvas}>{props.children}</main>
        </Content>
      </Layout>
    </Layout>
  );
}
