"use client";

import { Alert, Button, Col, Divider, Input, List, Progress, Row, Select, Skeleton, Space, Table, Tabs, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { SectionCard } from "@/components/common/SectionCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { MiniTrend, SignalGauge } from "@/components/visual/ResearchVisuals";
import { generateChainOfImpact, generateTopicReport } from "@/lib/api/macro";
import { summarizeNews } from "@/lib/api/news";
import type { MacroChainResponse, MacroInputs, MacroTopicReportResponse } from "@/types/macro";
import type { NewsSummaryResponse } from "@/types/news";

type LoadState = "idle" | "loading";

const regionOptions = ["CN", "US", "EU", "Global"].map((v) => ({ label: v, value: v }));
const horizonOptions = ["days", "weeks", "months", "quarters"].map((v) => ({ label: v, value: v }));
const langOptions = ["zh-CN", "en-US"].map((v) => ({ label: v, value: v }));
const newsRegionOptions = ["CN", "US", "GB", "JP"].map((v) => ({ label: v, value: v }));

function errorText(_error: unknown, fallback: string) {
  return fallback;
}

function normalizeTab(value: string | null): "chain" | "report" | "news" | null {
  return value === "chain" || value === "report" || value === "news" ? value : null;
}

function readUrlDefaults(params: Pick<URLSearchParams, "get" | "has">) {
  const hasDashboardContext = ["topic", "event", "region", "tab", "autoRun"].some((key) => params.has(key));
  if (!hasDashboardContext) return null;

  return {
    topic: params.get("topic")?.trim() || undefined,
    event: params.get("event")?.trim() || undefined,
    region: params.get("region")?.trim() || undefined,
    tab: normalizeTab(params.get("tab")),
    autoRun: params.get("autoRun") === "1",
  };
}

function cleanEventTitle(value: string) {
  return value
    .replace(/\s[-–—]\s[^-–—]{2,40}$/, "")
    .replace(/[“”"'《》]/g, "")
    .trim();
}

function topicFromEvent(event: string) {
  const text = cleanEventTitle(event);
  if (!text) return "";
  if (/华为|韬[（(]?\s*τ?|半导体|晶体管|芯片|Mate\s*\d+/i.test(text)) return "华为韬定律与半导体";
  if (/机器人|具身智能|人形机器人|工业机器人/.test(text)) return "机器人产业链";
  if (/新能源车|新能源汽车|电动车|车企|电池/.test(text)) return "新能源汽车";
  if (/美联储|通胀|降息|加息|美元|利率/.test(text)) return "美元利率与宏观流动性";
  if (/黄金|金价|XAU|贵金属/i.test(text)) return "黄金波动驱动";
  if (/油价|原油|OPEC|石油/i.test(text)) return "原油供需与通胀";

  const firstClause = text.split(/[，。,:：;；!！?？]/)[0]?.trim() || "";
  return firstClause.length >= 2 ? firstClause.slice(0, 24) : "";
}

function isWeakTopic(value: string | undefined) {
  const text = (value || "").trim();
  if (!text) return true;
  if (["韬", "τ", "陶", "策略", "事件"].includes(text)) return true;
  return text.length <= 1;
}

function normalizeMacroTopic(topicValue: string | undefined, eventValue: string | undefined) {
  const rawTopic = (topicValue || "").trim();
  const eventTopic = topicFromEvent(eventValue || "");
  if (isWeakTopic(rawTopic)) return eventTopic || (rawTopic === "韬" || rawTopic === "τ" ? "华为韬定律与半导体" : rawTopic);
  if (rawTopic.length <= 2 && eventTopic && cleanEventTitle(eventValue || "").includes(rawTopic)) return eventTopic;
  return rawTopic;
}

function sourceLabel(source?: string) {
  if (!source) return "公开新闻源";
  const normalized = source.toLowerCase();
  if (normalized.includes("google")) return "Google 新闻";
  if (normalized.includes("gdelt")) return "GDELT 新闻";
  if (normalized.includes("openbb")) return "OpenBB 新闻";
  return source;
}

function formatFetchedAt(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function directionTag(value?: string) {
  const normalized = String(value || "mixed").toLowerCase();
  if (normalized.includes("up") || normalized.includes("positive") || normalized.includes("利好")) return <Tag color="green">正向</Tag>;
  if (normalized.includes("down") || normalized.includes("negative") || normalized.includes("利空")) return <Tag color="red">负向</Tag>;
  return <Tag color="gold">分化</Tag>;
}

function confidencePercent(value: unknown) {
  const number = typeof value === "number" ? value : 0.58;
  return Math.round(Math.max(0, Math.min(1, number)) * 100);
}

function chainConfidence(result: Record<string, any> | undefined) {
  return confidencePercent(result?.confidence ?? 0.62);
}

export default function MacroIntelPage() {
  const initializedSearchRef = useRef("");
  const [topic, setTopic] = useState("oil");
  const [event, setEvent] = useState("");
  const [region, setRegion] = useState("CN");
  const [horizon, setHorizon] = useState("weeks");
  const [newsLang, setNewsLang] = useState("zh-CN");
  const [newsRegion, setNewsRegion] = useState("CN");
  const [newsLimit, setNewsLimit] = useState(20);
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
      topic: normalizeMacroTopic(topic, event),
      event: event.trim() || undefined,
      region: region.trim() || undefined,
      horizon: horizon.trim() || undefined,
    }),
    [topic, event, region, horizon],
  );

  const guardTopic = useCallback((targetPayload: MacroInputs) => {
    if (!targetPayload.topic) {
      message.error("Topic is required");
      return false;
    }
    return true;
  }, []);

  const runChainForPayload = useCallback(async (targetPayload: MacroInputs) => {
    if (!guardTopic(targetPayload)) return;
    setChainState("loading");
    setChainErrorMsg("");
    try {
      setChain(await generateChainOfImpact(targetPayload));
    } catch (e) {
      const msg = errorText(e, "宏观链路分析暂不可用，可稍后刷新。");
      setChainErrorMsg(msg);
      message.error(msg);
    } finally {
      setChainState("idle");
    }
  }, [guardTopic]);

  const runReportForPayload = useCallback(async (targetPayload: MacroInputs) => {
    if (!guardTopic(targetPayload)) return;
    setReportState("loading");
    setReportErrorMsg("");
    try {
      setReport(await generateTopicReport(targetPayload));
    } catch (e) {
      const msg = errorText(e, "主题研究报告暂不可用，可稍后刷新。");
      setReportErrorMsg(msg);
      message.error(msg);
    } finally {
      setReportState("idle");
    }
  }, [guardTopic]);

  const runNewsForPayload = useCallback(async (targetPayload: MacroInputs, targetRegion = newsRegion) => {
    if (!guardTopic(targetPayload)) return;
    setNewsState("loading");
    setNewsErrorMsg("");
    try {
      const res = await summarizeNews({
        topic: targetPayload.topic,
        limit: newsLimit,
        lang: newsLang,
        region: targetRegion,
      });
      setNews(res);
    } catch (e) {
      const msg = errorText(e, "信息源暂不可用，可稍后刷新。");
      setNewsErrorMsg(msg);
      message.error(msg);
    } finally {
      setNewsState("idle");
    }
  }, [guardTopic, newsLang, newsLimit, newsRegion]);

  const runAllForPayload = useCallback(async (targetPayload: MacroInputs, targetRegion = newsRegion) => {
    if (!guardTopic(targetPayload)) return;
    setChainState("loading");
    setReportState("loading");
    setNewsState("loading");
    setChainErrorMsg("");
    setReportErrorMsg("");
    setNewsErrorMsg("");
    const [chainRes, reportRes, newsRes] = await Promise.allSettled([
      generateChainOfImpact(targetPayload),
      generateTopicReport(targetPayload),
      summarizeNews({
        topic: targetPayload.topic,
        limit: newsLimit,
        lang: newsLang,
        region: targetRegion,
      }),
    ]);
    if (chainRes.status === "fulfilled") setChain(chainRes.value);
    if (reportRes.status === "fulfilled") setReport(reportRes.value);
    if (newsRes.status === "fulfilled") setNews(newsRes.value);
    if (chainRes.status === "rejected") setChainErrorMsg(errorText(chainRes.reason, "宏观链路分析暂不可用，可稍后刷新。"));
    if (reportRes.status === "rejected") setReportErrorMsg(errorText(reportRes.reason, "主题研究报告暂不可用，可稍后刷新。"));
    if (newsRes.status === "rejected") setNewsErrorMsg(errorText(newsRes.reason, "信息源暂不可用，可稍后刷新。"));
    setChainState("idle");
    setReportState("idle");
    setNewsState("idle");
  }, [guardTopic, newsLang, newsLimit, newsRegion]);

  const runChain = useCallback(() => runChainForPayload(payload), [payload, runChainForPayload]);
  const runReport = useCallback(() => runReportForPayload(payload), [payload, runReportForPayload]);
  const runNews = useCallback(() => runNewsForPayload(payload), [payload, runNewsForPayload]);
  const runAll = useCallback(() => runAllForPayload(payload), [payload, runAllForPayload]);

  useEffect(() => {
    const searchKey = typeof window === "undefined" ? "" : window.location.search;
    if (initializedSearchRef.current === searchKey) return;
    const defaults = readUrlDefaults(new URLSearchParams(searchKey));
    if (!defaults) return;
    initializedSearchRef.current = searchKey;

    const nextEvent = defaults.event || "";
    const nextTopic = normalizeMacroTopic(defaults.topic || topic, nextEvent);
    const nextRegion = defaults.region || region;
    const nextNewsRegion = newsRegionOptions.some((item) => item.value === nextRegion) ? nextRegion : newsRegion;
    const nextPayload: MacroInputs = {
      topic: nextTopic,
      event: nextEvent || undefined,
      region: nextRegion,
      horizon,
    };

    setTopic(nextTopic);
    setEvent(nextEvent);
    setRegion(nextRegion);
    setNewsRegion(nextNewsRegion);
    setActiveTab(defaults.tab || (defaults.autoRun ? "news" : activeTab));

    if (defaults.autoRun) {
      void runChainForPayload(nextPayload);
      void runNewsForPayload(nextPayload, nextNewsRegion);
    }
  }, [activeTab, horizon, newsRegion, region, runChainForPayload, runNewsForPayload, topic]);

  const llmReady = chain?.llm_ready || report?.llm_ready || false;
  const chainResult = chain?.result as Record<string, any> | undefined;
  const reportResult = report?.result as Record<string, any> | undefined;
  const impactRows = useMemo(() => {
    const assets = ((chainResult?.impact?.assets || []) as any[]).map((item) => ({ ...item, type: "资产" }));
    const sectors = ((chainResult?.impact?.sectors || []) as any[]).map((item) => ({ ...item, type: "行业" }));
    return [...assets, ...sectors].map((item, index) => ({
      key: `${item.type}-${item.name || index}`,
      type: item.type,
      name: item.name || "-",
      direction: item.direction || "mixed",
      confidence: confidencePercent(item.confidence),
    }));
  }, [chainResult]);
  const reportDashboardRows = useMemo(() => {
    return ((reportResult?.market_dashboard || []) as any[]).map((item, index) => ({
      key: `${item.metric || index}`,
      metric: item.metric || "-",
      value: item.value || "-",
      interpretation: item.interpretation || "-",
    }));
  }, [reportResult]);

  return (
    <PageContainer title="宏观情报" subtitle="新闻摘要、事件影响链路与跨资产情景分析">
      <Row gutter={[16, 16]}>
        <Col xxl={7} xl={8} lg={24}>
          <div style={{ position: "sticky", top: 16 }}>
            <SectionCard
              title="研究输入"
              extra={
                <Space size={8}>
                  <Typography.Text type="secondary">分析引擎</Typography.Text>
                  {llmReady ? <Tag color="green">可用</Tag> : <Tag>模板兜底</Tag>}
                </Space>
              }
            >
              <Space orientation="vertical" size={10} style={{ width: "100%" }}>
                <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="主题，例如：机器人、黄金、美元兑日元" />
                <Input value={event} onChange={(e) => setEvent(e.target.value)} placeholder="事件，可选" />
                <Select value={region} options={regionOptions} onChange={setRegion} placeholder="Region" />
                <Select value={horizon} options={horizonOptions} onChange={setHorizon} placeholder="Horizon" />

                <Divider style={{ margin: "8px 0" }} />
                <Typography.Text type="secondary">新闻源</Typography.Text>
                <Space wrap>
                  <Select value={newsLang} options={langOptions} onChange={setNewsLang} style={{ width: 110 }} />
                  <Select value={newsRegion} options={newsRegionOptions} onChange={setNewsRegion} style={{ width: 110 }} />
                  <Select value={newsLimit} options={[10, 20, 30, 50].map((v) => ({ label: `${v}`, value: v }))} onChange={setNewsLimit} style={{ width: 90 }} />
                </Space>

                <Divider style={{ margin: "8px 0" }} />
                <Space wrap>
                  <Button type="primary" onClick={runAll} loading={chainState === "loading" || reportState === "loading" || newsState === "loading"}>
                    全部分析
                  </Button>
                  <Button onClick={runChain} loading={chainState === "loading"}>链路</Button>
                  <Button onClick={runReport} loading={reportState === "loading"}>报告</Button>
                  <Button onClick={runNews} loading={newsState === "loading"}>新闻</Button>
                </Space>
              </Space>
            </SectionCard>
          </div>
        </Col>

        <Col xxl={17} xl={16} lg={24}>
          <SectionCard title="分析结果" bodyStyle={{ padding: 12 }}>
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={[
                {
                  key: "chain",
                  label: <span>链路 {chain?.llm_ready ? <Tag color="green">AI</Tag> : <Tag>模板</Tag>}</span>,
                  children:
                    chainState === "loading" ? (
                      <Skeleton active paragraph={{ rows: 6 }} />
                    ) : chainErrorMsg ? (
                      <ErrorState title="宏观链路分析暂不可用" subtitle={chainErrorMsg} onRetry={runChain} />
                    ) : chainResult ? (
                      <Space orientation="vertical" style={{ width: "100%" }} size={14}>
                        <Row gutter={[12, 12]}>
                          <Col xs={24} md={7}>
                            <SignalGauge
                              label="链路置信度"
                              value={chainConfidence(chainResult)}
                              tone={chainConfidence(chainResult) >= 70 ? "positive" : "warning"}
                              caption="用于辅助研究，不构成投资建议"
                            />
                          </Col>
                          <Col xs={24} md={17}>
                            <Alert
                              type="info"
                              showIcon
                              message="市场状态假设"
                              description={chainResult.regime_hypothesis || "暂未形成稳定假设，可先查看新闻摘要。"}
                            />
                            <div style={{ marginTop: 12 }}>
                              <MiniTrend tone="warning" />
                            </div>
                          </Col>
                        </Row>

                        <Row gutter={[12, 12]}>
                          <Col xs={24} lg={10}>
                            <div style={{ padding: 12, border: "1px solid var(--fp-border)", borderRadius: "var(--fp-radius)", background: "rgba(248,250,252,0.78)" }}>
                              <Typography.Text strong>驱动因素</Typography.Text>
                              <List
                                size="small"
                                dataSource={((chainResult.cause || []) as string[]).slice(0, 5)}
                                renderItem={(item) => <List.Item>{item}</List.Item>}
                              />
                            </div>
                          </Col>
                          <Col xs={24} lg={14}>
                            <div style={{ padding: 12, border: "1px solid var(--fp-border)", borderRadius: "var(--fp-radius)", background: "rgba(248,250,252,0.78)" }}>
                              <Typography.Text strong>事件传导时间线</Typography.Text>
                              <Space direction="vertical" style={{ width: "100%", marginTop: 10 }} size={10}>
                                {((chainResult.transmission || []) as any[]).slice(0, 5).map((item, index) => (
                                  <div key={`${item.step || index}`} style={{ display: "grid", gridTemplateColumns: "28px minmax(0,1fr)", gap: 10 }}>
                                    <Tag color="blue" style={{ margin: 0 }}>{index + 1}</Tag>
                                    <div>
                                      <Typography.Text strong>{item.step || "影响节点"}</Typography.Text>
                                      <div>
                                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                          {[item.channel, item.who, item.timeframe].filter(Boolean).join(" / ")}
                                        </Typography.Text>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </Space>
                            </div>
                          </Col>
                        </Row>

                        <Table
                          size="small"
                          rowKey="key"
                          dataSource={impactRows}
                          pagination={false}
                          locale={{ emptyText: "暂无资产/行业影响矩阵" }}
                          columns={[
                            { title: "类型", dataIndex: "type", width: 90 },
                            { title: "对象", dataIndex: "name" },
                            { title: "方向", dataIndex: "direction", width: 100, render: directionTag },
                            {
                              title: "置信度",
                              dataIndex: "confidence",
                              width: 160,
                              render: (value: number) => <Progress percent={value} size="small" />,
                            },
                          ]}
                        />

                        <div>
                          <Typography.Text type="secondary">观察信号</Typography.Text>
                          <div style={{ marginTop: 8 }}>
                            <Space wrap>
                              {((chainResult.impact?.signals_to_watch || []) as string[]).map((s) => <Tag key={s}>{s}</Tag>)}
                            </Space>
                          </div>
                        </div>
                      </Space>
                    ) : (
                      <EmptyState title="尚未生成宏观链路" description="运行链路分析后，会生成结构化影响路径。" actionText="生成链路" onAction={runChain} />
                    ),
                },
                {
                  key: "report",
                  label: <span>报告 {report?.llm_ready ? <Tag color="green">AI</Tag> : <Tag>模板</Tag>}</span>,
                  children:
                    reportState === "loading" ? (
                      <Skeleton active paragraph={{ rows: 6 }} />
                    ) : reportErrorMsg ? (
                      <ErrorState title="主题研究报告暂不可用" subtitle={reportErrorMsg} onRetry={runReport} />
                    ) : reportResult ? (
                      <Space orientation="vertical" style={{ width: "100%" }} size={14}>
                        <Alert type="info" showIcon message="核心摘要" description={reportResult.executive_summary || "N/A"} />
                        <Row gutter={[12, 12]}>
                          <Col xs={24} lg={12}>
                            <div style={{ padding: 12, border: "1px solid var(--fp-border)", borderRadius: "var(--fp-radius)", background: "rgba(248,250,252,0.78)" }}>
                              <Typography.Text strong>主要驱动</Typography.Text>
                              <List size="small" dataSource={((reportResult.drivers || []) as string[]).slice(0, 6)} renderItem={(item) => <List.Item>{item}</List.Item>} />
                            </div>
                          </Col>
                          <Col xs={24} lg={12}>
                            <div style={{ padding: 12, border: "1px solid var(--fp-border)", borderRadius: "var(--fp-radius)", background: "rgba(248,250,252,0.78)" }}>
                              <Typography.Text strong>观察清单</Typography.Text>
                              <div style={{ marginTop: 10 }}>
                                <Space wrap>
                                  {((reportResult.watchlist || []) as string[]).slice(0, 10).map((item) => <Tag key={item}>{item}</Tag>)}
                                </Space>
                              </div>
                            </div>
                          </Col>
                        </Row>
                        <Table
                          size="small"
                          rowKey="key"
                          dataSource={reportDashboardRows}
                          pagination={false}
                          locale={{ emptyText: "暂无市场仪表盘数据" }}
                          columns={[
                            { title: "指标", dataIndex: "metric", width: 160 },
                            { title: "数值", dataIndex: "value", width: 140 },
                            { title: "解读", dataIndex: "interpretation" },
                          ]}
                        />
                      </Space>
                    ) : (
                      <EmptyState title="尚未生成主题报告" description="运行报告生成后，会形成简短研究摘要。" actionText="生成报告" onAction={runReport} />
                    ),
                },
                {
                  key: "news",
                  label: <span>新闻 {news?.items?.length ? <Tag color="blue">{news.items.length}</Tag> : <Tag>0</Tag>}</span>,
                  children:
                    newsState === "loading" ? (
                      <Skeleton active paragraph={{ rows: 8 }} />
                    ) : newsErrorMsg ? (
                      <ErrorState title="信息源暂不可用" subtitle={newsErrorMsg} onRetry={runNews} />
                    ) : news?.items ? (
                      <Space orientation="vertical" style={{ width: "100%" }} size={8}>
                        <Space wrap>
                          <Tag color="blue">新闻源：{sourceLabel(news.source)}</Tag>
                          {news.fetched_at ? <Typography.Text type="secondary">更新时间：{formatFetchedAt(news.fetched_at)}</Typography.Text> : null}
                        </Space>
                        {news.warnings?.length ? (
                          <Alert
                            type="warning"
                            showIcon
                            message="主信息源不可用，已切换备用新闻源。"
                            description="备用结果仍可用于新闻摘要和宏观链路分析，可稍后刷新获取主信息源。"
                          />
                        ) : null}
                        <Typography.Text type="secondary">摘要要点</Typography.Text>
                        <List size="small" dataSource={news.summary?.highlights || []} renderItem={(item) => <List.Item>{item}</List.Item>} />
                        <Typography.Text type="secondary">最新新闻</Typography.Text>
                        <List
                          size="small"
                          dataSource={news.items || []}
                          renderItem={(item) => (
                            <List.Item>
                              <Space orientation="vertical" size={0}>
                                {item.link ? (
                                  <Typography.Link href={item.link} target="_blank" rel="noreferrer">{item.title}</Typography.Link>
                                ) : (
                                  <Typography.Text>{item.title}</Typography.Text>
                                )}
                                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                  {[item.source, item.published_at].filter(Boolean).join(" / ")}
                                </Typography.Text>
                              </Space>
                            </List.Item>
                          )}
                        />
                      </Space>
                    ) : (
                      <EmptyState title="尚未搜集新闻" description="点击后将从公开新闻源抓取并生成摘要。" actionText="搜集新闻" onAction={runNews} />
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
