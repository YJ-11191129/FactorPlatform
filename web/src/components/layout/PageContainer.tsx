"use client";

import { Breadcrumb, Typography } from "antd";
import type { ReactNode } from "react";

import styles from "@/components/layout/layout.module.css";

export function PageContainer(props: { title: string; subtitle?: string; breadcrumb?: string[]; extra?: ReactNode; children: ReactNode }) {
  return (
    <div className={styles.pageRoot}>
      {props.breadcrumb && props.breadcrumb.length > 0 ? (
        <Breadcrumb className={styles.breadcrumb} items={props.breadcrumb.map((t) => ({ title: t }))} />
      ) : null}
      <div className={styles.pageHero}>
        <div className={styles.pageTitleBlock}>
          <Typography.Title level={2} className={styles.pageTitle}>
            {props.title}
          </Typography.Title>
          {props.subtitle ? (
            <Typography.Text type="secondary" className={styles.pageSubtitle}>
              {props.subtitle}
            </Typography.Text>
          ) : null}
        </div>
        {props.extra ? <div className={styles.pageExtra}>{props.extra}</div> : null}
      </div>
      {props.children}
    </div>
  );
}
