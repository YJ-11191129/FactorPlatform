"use client";

import dynamic from "next/dynamic";
import { Button, Card, Col, DatePicker, Row, Select, Skeleton, Space, Statistic, Table } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { getEnumsMeta, getPerformanceSummary, listSignalHistory } from "@/lib/api/signal-center";
import type { ApiError } from "@/lib/api/client";
import type { EnumsMeta, PerformanceSummary, Signal } from "@/types/signal-center";

const Column = dynamic(() => import("@ant-design/charts").then((m) => m.Column), { ssr: false });
const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });

type LoadState = "loading" | "error" | "ready";

export default function SignalHistoryPage() {
  const [state, setState] = useState<LoadState>("loading");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [history, setHistory] = useState<Signal[]>([]);
  const [summary, setSummary] = useState<PerformanceSummary | null>(null);
  const [enums, setEnums] = useState<EnumsMeta>({});

  const load = useCallback(async (attempt = 0) => {
    setState("loading");
    setErrorMsg("");
    const [historyRes, summaryRes, metaRes] = await Promise.allSettled([
      listSignalHistory({ page_size: 60 }),
      getPerformanceSummary(),
      getEnumsMeta(),
    ]);

    if (summaryRes.status !== "fulfilled") {
      const e = summaryRes.reason as ApiError;
      const msg = e?.message || "Request failed";
      if (attempt < 1) {
        setTimeout(() => load(attempt + 1), 800);
        return;
      }
      setErrorMsg(msg);
      setState("error");
      return;
    }

    setHistory(historyRes.status === "fulfilled" ? historyRes.value.items : []);
    setSummary(summaryRes.value);
    setEnums(metaRes.status === "fulfilled" ? metaRes.value : {});
    setState("ready");
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const pnlTrend = useMemo(() => {
    let cum = 0;
    return history
      .slice()
      .reverse()
      .map((h) => {
        cum += h.realized_pnl || 0;
        return { date: h.signal_time.slice(0, 10), cum_pnl: Number(cum.toFixed(4)) };
      });
  }, [history]);

  if (state === "loading") return <Skeleton active paragraph={{ rows: 10 }} />;
  if (state === "error" || !summary)
    return <ErrorState title="History page load failed" subtitle={errorMsg || "Check API key in Settings"} onRetry={load} />;

  return (
    <PageContainer title="Signal History" subtitle="Historical signal outcomes and attribution-ready views">
      <Card>
        <Row gutter={[12, 12]}>
          <Col span={5}><DatePicker.RangePicker style={{ width: "100%" }} /></Col>
          <Col span={3}><Select placeholder="Market" style={{ width: "100%" }} allowClear options={(enums.market || []).map((v) => ({ label: v, value: v }))} /></Col>
          <Col span={3}><Select placeholder="Instrument" style={{ width: "100%" }} allowClear options={history.slice(0, 10).map((s) => ({ label: s.instrument, value: s.instrument }))} /></Col>
          <Col span={3}><Select placeholder="Timeframe" style={{ width: "100%" }} allowClear options={(enums.timeframe || []).map((v) => ({ label: v, value: v }))} /></Col>
          <Col span={4}><Select placeholder="Regime" style={{ width: "100%" }} allowClear options={(enums.regime_label || []).map((v) => ({ label: v, value: v }))} /></Col>
          <Col span={3}><Select placeholder="Template" style={{ width: "100%" }} allowClear options={(enums.signal_template || []).map((v) => ({ label: v, value: v }))} /></Col>
          <Col span={3}><Button type="primary" block onClick={() => load()}>Refresh</Button></Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={4}><Card><Statistic title="Total Signals" value={summary.summary.total_signals} /></Card></Col>
        <Col span={4}><Card><Statistic title="Win Rate" value={Math.round(summary.summary.win_rate * 100)} suffix="%" /></Card></Col>
        <Col span={4}><Card><Statistic title="Avg PnL" value={summary.summary.avg_pnl} precision={4} /></Card></Col>
        <Col span={4}><Card><Statistic title="Max Drawdown" value={summary.summary.max_drawdown} precision={4} /></Card></Col>
        <Col span={4}><Card><Statistic title="Profit Factor" value={summary.summary.profit_factor} precision={2} /></Card></Col>
        <Col span={4}><Card><Statistic title="Avg Bars Held" value={summary.summary.avg_holding_bars} precision={1} /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={12} xs={24}>
          <Card title="Cumulative PnL">
            <Line data={pnlTrend} xField="date" yField="cum_pnl" height={260} />
          </Card>
        </Col>
        <Col xl={12} xs={24}>
          <Card title="By Regime">
            <Column data={summary.breakdowns.by_regime} xField="regime_label" yField="avg_pnl" height={260} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={12} xs={24}>
          <Card title="By Confidence Bucket">
            <Column data={summary.breakdowns.by_confidence_bucket} xField="bucket" yField="avg_pnl" height={260} />
          </Card>
        </Col>
        <Col xl={12} xs={24}>
          <Card title="By Template">
            <Column data={summary.breakdowns.by_template} xField="template" yField="win_rate" height={260} />
          </Card>
        </Col>
      </Row>

      <Card title="History Table" style={{ marginTop: 16 }}>
        <Table
          rowKey="signal_id"
          dataSource={history}
          scroll={{ x: 1280 }}
          columns={[
            { title: "Signal Time", dataIndex: "signal_time", width: 180 },
            { title: "Instrument", dataIndex: "instrument", width: 110 },
            { title: "Timeframe", dataIndex: "timeframe", width: 90 },
            { title: "Side", dataIndex: "side", width: 90 },
            { title: "Regime", dataIndex: "regime_label", width: 170 },
            { title: "Confidence", dataIndex: "confidence", width: 100 },
            { title: "Risk", dataIndex: "risk_level", width: 100 },
            { title: "Status", dataIndex: "status", width: 110 },
            { title: "Realized PnL", dataIndex: "realized_pnl", width: 120 },
            { title: "Holding Bars", dataIndex: "holding_bars", width: 120 },
            { title: "Template", dataIndex: "signal_template", width: 220 },
            {
              title: "Actions",
              key: "actions",
              width: 150,
              fixed: "right",
              render: (_, row) => <Space><a href={`/signal-center/${row.signal_id}`}>Detail</a><a>Replay</a><a>Compare</a></Space>,
            },
          ]}
        />
      </Card>
    </PageContainer>
  );
}
