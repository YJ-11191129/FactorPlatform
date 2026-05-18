"use client";

import { Alert, Button, Col, Divider, Input, List, Row, Select, Skeleton, Space, Tabs, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { generateChainOfImpact, generateTopicReport } from "@/lib/api/macro";
import { summarizeNews } from "@/lib/api/news";
import { getOpenBBStatus } from "@/lib/api/openbb";
import type { MacroChainResponse, MacroInputs, MacroTopicReportResponse } from "@/types/macro";
import type { NewsSummaryResponse } from "@/types/news";
import type { OpenBBStatus } from "@/types/openbb";

type LoadState = "idle" | "loading";
type NewsSource = "google_news_rss" | "openbb";

const regionOptions = ["CN", "US", "EU", "Global"].map((v) => ({ label: v, value: v }));
const horizonOptions = ["days", "weeks", "months", "quarters"].map((v) => ({ label: v, value: v }));
const langOptions = ["zh-CN", "en-US"].map((v) => ({ label: v, value: v }));
const newsRegionOptions = ["CN", "US", "GB", "JP"].map((v) => ({ label: v, value: v }));

function statusColor(status?: string) {
  if (status === "READY") return "green";
  if (status === "WARN" || status === "OPENBB_NOT_READY") return "gold";
  return "default";
}

function errorText(error: unknown, fallback: string) {
  if (error && typeof error === "object" && "message" in error) return String((error as { message?: unknown }).message || fallback);
  return fallback;
}

export default function MacroIntelPage() {
  const [topic, setTopic] = useState("oil");
  const [event, setEvent] = useState("");
  const [region, setRegion] = useState("CN");
  const [horizon, setHorizon] = useState("weeks");
  const [newsSource, setNewsSource] = useState<NewsSource>("google_news_rss");
  const [newsLang, setNewsLang] = useState("zh-CN");
  const [newsRegion, setNewsRegion] = useState("CN");
  const [newsLimit, setNewsLimit] = useState(20);
  const [openbbProvider, setOpenbbProvider] = useState("");
  const [openbbSymbol, setOpenbbSymbol] = useState("");

  const [openbbStatus, setOpenbbStatus] = useState<OpenBBStatus | null>(null);
  const [chain, setChain] = useState<MacroChainResponse | null>(null);
  const [report, setReport] = useState<MacroTopicReportResponse | null>(null);
  const [news, setNews] = useState<NewsSummaryResponse | null>(null);

  const [chainErrorMsg, setChainErrorMsg] = useState("");
  const [reportErrorMsg, setReportErrorMsg] = useState("");
  const [newsErrorMsg, setNewsErrorMsg] = useState("");
  const [activeTab, setActiveTab] = useState("chain");
  const [chainState, setChainState] = useState<LoadState>("idle");
  const [reportState, setReportState] = useState<LoadState>("idle");
  const [newsState, setNewsState] = useState<LoadState>("idle");

  const payload: MacroInputs = useMemo(
    () => ({
      topic: topic.trim(),
      event: event.trim() || undefined,
      region: region.trim() || undefined,
      horizon: horizon.trim() || undefined,
    }),
    [topic, event, region, horizon],
  );

  useEffect(() => {
    getOpenBBStatus().then(setOpenbbStatus).catch(() => setOpenbbStatus(null));
  }, []);

  const guardTopic = useCallback(() => {
    if (!payload.topic) {
      message.error("Topic is required");
      return false;
    }
    return true;
  }, [payload.topic]);

  async function runChain() {
    if (!guardTopic()) return;
    setChainState("loading");
    setChainErrorMsg("");
    try {
      setChain(await generateChainOfImpact(payload));
    } catch (e) {
      const msg = errorText(e, "Macro chain request failed");
      setChainErrorMsg(msg);
      message.error(msg);
    } finally {
      setChainState("idle");
    }
  }

  async function runReport() {
    if (!guardTopic()) return;
    setReportState("loading");
    setReportErrorMsg("");
    try {
      setReport(await generateTopicReport(payload));
    } catch (e) {
      const msg = errorText(e, "Topic report request failed");
      setReportErrorMsg(msg);
      message.error(msg);
    } finally {
      setReportState("idle");
    }
  }

  async function runNews() {
    if (!guardTopic()) return;
    setNewsState("loading");
    setNewsErrorMsg("");
    try {
      const res = await summarizeNews({
        topic: payload.topic,
        limit: newsLimit,
        lang: newsLang,
        region: newsRegion,
        source: newsSource,
        provider: openbbProvider.trim() || undefined,
        symbol: newsSource === "openbb" ? openbbSymbol.trim() || undefined : undefined,
      });
      setNews(res);
    } catch (e) {
      const msg = errorText(e, "News request failed");
      setNewsErrorMsg(msg);
      message.error(msg);
    } finally {
      setNewsState("idle");
    }
  }

  async function runAll() {
    if (!guardTopic()) return;
    setChainState("loading");
    setReportState("loading");
    setNewsState("loading");
    setChainErrorMsg("");
    setReportErrorMsg("");
    setNewsErrorMsg("");
    const [chainRes, reportRes, newsRes] = await Promise.allSettled([
      generateChainOfImpact(payload),
      generateTopicReport(payload),
      summarizeNews({
        topic: payload.topic,
        limit: newsLimit,
        lang: newsLang,
        region: newsRegion,
        source: newsSource,
        provider: openbbProvider.trim() || undefined,
        symbol: newsSource === "openbb" ? openbbSymbol.trim() || undefined : undefined,
      }),
    ]);
    if (chainRes.status === "fulfilled") setChain(chainRes.value);
    if (reportRes.status === "fulfilled") setReport(reportRes.value);
    if (newsRes.status === "fulfilled") setNews(newsRes.value);
    if (chainRes.status === "rejected") setChainErrorMsg(errorText(chainRes.reason, "Macro chain request failed"));
    if (reportRes.status === "rejected") setReportErrorMsg(errorText(reportRes.reason, "Topic report request failed"));
    if (newsRes.status === "rejected") setNewsErrorMsg(errorText(newsRes.reason, "News request failed"));
    setChainState("idle");
    setReportState("idle");
    setNewsState("idle");
  }

  const llmReady = chain?.llm_ready || report?.llm_ready || false;
  const chainResult = chain?.result as Record<string, any> | undefined;
  const reportResult = report?.result as Record<string, any> | undefined;
  const openbbEvidence = chain?.context?.openbb_evidence || report?.context?.openbb_evidence;

  return (
    <PageContainer title="Macro Intelligence" subtitle="Macro reasoning, news aggregation, and OpenBB research evidence">
      <Row gutter={[16, 16]}>
        <Col xxl={7} xl={8} lg={24}>
          <div style={{ position: "sticky", top: 16 }}>
            <SectionCard
              title="Inputs"
              extra={
                <Space size={8}>
                  <Typography.Text type="secondary">LLM</Typography.Text>
                  {llmReady ? <Tag color="green">Ready</Tag> : <Tag>Fallback</Tag>}
                </Space>
              }
            >
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Topic" />
                <Input value={event} onChange={(e) => setEvent(e.target.value)} placeholder="Event (optional)" />
                <Select value={region} options={regionOptions} onChange={setRegion} placeholder="Region" />
                <Select value={horizon} options={horizonOptions} onChange={setHorizon} placeholder="Horizon" />

                <Divider style={{ margin: "8px 0" }} />
                <Typography.Text type="secondary">News source</Typography.Text>
                <Select
                  value={newsSource}
                  onChange={(value) => setNewsSource(value)}
                  options={[
                    { label: "Google RSS", value: "google_news_rss" },
                    { label: "OpenBB", value: "openbb" },
                  ]}
                />
                <Space wrap>
                  <Select value={newsLang} options={langOptions} onChange={setNewsLang} style={{ width: 110 }} disabled={newsSource === "openbb"} />
                  <Select value={newsRegion} options={newsRegionOptions} onChange={setNewsRegion} style={{ width: 110 }} disabled={newsSource === "openbb"} />
                  <Select value={newsLimit} options={[10, 20, 30, 50].map((v) => ({ label: `${v}`, value: v }))} onChange={setNewsLimit} style={{ width: 90 }} />
                </Space>
                {newsSource === "openbb" ? (
                  <Space direction="vertical" style={{ width: "100%" }} size={8}>
                    <Input value={openbbProvider} onChange={(e) => setOpenbbProvider(e.target.value)} placeholder="OpenBB provider (optional)" />
                    <Input value={openbbSymbol} onChange={(e) => setOpenbbSymbol(e.target.value.toUpperCase())} placeholder="Company symbol (optional, e.g. AAPL)" />
                    <Alert
                      type={openbbStatus?.status === "READY" ? "success" : "warning"}
                      showIcon
                      message={
                        <Space size={6}>
                          <span>OpenBB</span>
                          <Tag color={statusColor(openbbStatus?.status)}>{openbbStatus?.status || "UNKNOWN"}</Tag>
                        </Space>
                      }
                      description={(openbbStatus?.notes || [openbbStatus?.install_hint || "OpenBB status unavailable"]).filter(Boolean).join("; ")}
                    />
                  </Space>
                ) : null}

                <Divider style={{ margin: "8px 0" }} />
                <Space wrap>
                  <Button type="primary" onClick={runAll} loading={chainState === "loading" || reportState === "loading" || newsState === "loading"}>
                    Run all
                  </Button>
                  <Button onClick={runChain} loading={chainState === "loading"}>Chain</Button>
                  <Button onClick={runReport} loading={reportState === "loading"}>Report</Button>
                  <Button onClick={runNews} loading={newsState === "loading"}>News</Button>
                </Space>
              </Space>
            </SectionCard>
          </div>
        </Col>

        <Col xxl={17} xl={16} lg={24}>
          {openbbEvidence ? (
            <Alert
              style={{ marginBottom: 16 }}
              type={openbbEvidence.status === "READY" ? "success" : "warning"}
              showIcon
              message="OpenBB research evidence"
              description={`status=${openbbEvidence.status || "UNKNOWN"} items=${openbbEvidence.items?.length || 0} calendar=${openbbEvidence.calendar?.length || 0}`}
            />
          ) : null}
          <SectionCard title="Analysis Output" bodyStyle={{ padding: 12 }}>
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={[
                {
                  key: "chain",
                  label: <span>Chain {chain?.llm_ready ? <Tag color="green">LLM</Tag> : <Tag>Template</Tag>}</span>,
                  children:
                    chainState === "loading" ? (
                      <Skeleton active paragraph={{ rows: 6 }} />
                    ) : chainErrorMsg ? (
                      <ErrorState title="Macro chain failed" subtitle={chainErrorMsg} onRetry={runChain} />
                    ) : chainResult ? (
                      <Space direction="vertical" style={{ width: "100%" }} size={8}>
                        <Typography.Text type="secondary">Regime</Typography.Text>
                        <Typography.Text>{chainResult.regime_hypothesis || "N/A"}</Typography.Text>
                        <Typography.Text type="secondary">Cause</Typography.Text>
                        <List size="small" dataSource={(chainResult.cause || []) as string[]} renderItem={(item) => <List.Item>{item}</List.Item>} />
                        <Typography.Text type="secondary">Transmission</Typography.Text>
                        <List
                          size="small"
                          dataSource={(chainResult.transmission || []) as any[]}
                          renderItem={(item) => (
                            <List.Item>
                              <Space direction="vertical" size={0}>
                                <Typography.Text>{item.step}</Typography.Text>
                                <Typography.Text type="secondary">{[item.channel, item.who, item.timeframe].filter(Boolean).join(" / ")}</Typography.Text>
                              </Space>
                            </List.Item>
                          )}
                        />
                        <Typography.Text type="secondary">Signals to watch</Typography.Text>
                        <Space wrap>
                          {((chainResult.impact?.signals_to_watch || []) as string[]).map((s) => <Tag key={s}>{s}</Tag>)}
                        </Space>
                      </Space>
                    ) : (
                      <EmptyState title="No macro chain yet" description="Run the macro chain to generate a structured view." actionText="Generate chain" onAction={runChain} />
                    ),
                },
                {
                  key: "report",
                  label: <span>Report {report?.llm_ready ? <Tag color="green">LLM</Tag> : <Tag>Template</Tag>}</span>,
                  children:
                    reportState === "loading" ? (
                      <Skeleton active paragraph={{ rows: 6 }} />
                    ) : reportErrorMsg ? (
                      <ErrorState title="Topic report failed" subtitle={reportErrorMsg} onRetry={runReport} />
                    ) : reportResult ? (
                      <Space direction="vertical" style={{ width: "100%" }} size={8}>
                        <Typography.Text type="secondary">Executive summary</Typography.Text>
                        <Typography.Paragraph>{reportResult.executive_summary || "N/A"}</Typography.Paragraph>
                        <Typography.Text type="secondary">Drivers</Typography.Text>
                        <List size="small" dataSource={(reportResult.drivers || []) as string[]} renderItem={(item) => <List.Item>{item}</List.Item>} />
                      </Space>
                    ) : (
                      <EmptyState title="No topic report yet" description="Run the report generator to create a structured brief." actionText="Generate report" onAction={runReport} />
                    ),
                },
                {
                  key: "news",
                  label: <span>News {news?.items?.length ? <Tag color="blue">{news.items.length}</Tag> : <Tag>0</Tag>}</span>,
                  children:
                    newsState === "loading" ? (
                      <Skeleton active paragraph={{ rows: 8 }} />
                    ) : newsErrorMsg ? (
                      <ErrorState title="News aggregation failed" subtitle={newsErrorMsg} onRetry={runNews} />
                    ) : news?.items ? (
                      <Space direction="vertical" style={{ width: "100%" }} size={8}>
                        <Space wrap>
                          <Tag>{news.source || newsSource}</Tag>
                          {news.endpoint ? <Tag>{news.endpoint}</Tag> : null}
                          {news.provider ? <Tag color="blue">{news.provider}</Tag> : null}
                          {news.research_ops_object_id ? <Tag color="purple">{news.research_ops_object_id}</Tag> : null}
                        </Space>
                        {(news.warnings || []).length ? <Alert type="warning" showIcon message="OpenBB warnings" description={(news.warnings || []).map((w) => JSON.stringify(w)).join("; ")} /> : null}
                        <Typography.Text type="secondary">Highlights</Typography.Text>
                        <List size="small" dataSource={news.summary?.highlights || []} renderItem={(item) => <List.Item>{item}</List.Item>} />
                        <Typography.Text type="secondary">Latest items</Typography.Text>
                        <List
                          size="small"
                          dataSource={news.items || []}
                          renderItem={(item) => (
                            <List.Item>
                              <Space direction="vertical" size={0}>
                                {item.link ? (
                                  <Typography.Link href={item.link} target="_blank" rel="noreferrer">{item.title}</Typography.Link>
                                ) : (
                                  <Typography.Text>{item.title}</Typography.Text>
                                )}
                                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                  {[item.source, item.provider, item.openbb_endpoint, item.published_at].filter(Boolean).join(" / ")}
                                </Typography.Text>
                              </Space>
                            </List.Item>
                          )}
                        />
                      </Space>
                    ) : (
                      <EmptyState title="No news fetched" description="Fetch news from Google RSS or OpenBB." actionText="Fetch news" onAction={runNews} />
                    ),
                },
              ]}
            />
          </SectionCard>
        </Col>
      </Row>
    </PageContainer>
  );
}
