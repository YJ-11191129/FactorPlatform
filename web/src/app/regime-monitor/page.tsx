"use client";

import dynamic from "next/dynamic";
import { Button, Card, Col, Descriptions, Drawer, Popover, Progress, Row, Skeleton, Space, Table, Tag, Tooltip, Typography, message } from "antd";
import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import {
  getCurrentStateProfile,
  getRegimeCurrent,
  getRegimeHistory,
  getRegimeSimilarPeriods,
  getRegimeTimeline,
  getShockEvents,
  getEnumsMeta,
  recomputeRegimeSimilarPeriods,
} from "@/lib/api/signal-center";
import { RegimeBadge } from "@/components/signal/SignalBadge";
import type { CurrentStateProfile, SimilarPeriodLookupItem } from "@/types/signal-center";
import type { EnumsMeta } from "@/types/signal-center";

const Line = dynamic(() => import("@ant-design/charts").then((m) => m.Line), { ssr: false });
const Column = dynamic(() => import("@ant-design/charts").then((m) => m.Column), { ssr: false });

type LoadState = "loading" | "error" | "ready";

const REGIME_HELP: Record<
  string,
  {
    title: string;
    traits: string[];
    actionHints: string[];
  }
> = {
  CALM_LOW_VOL: {
    title: "低波动 / 稳态",
    traits: ["波动率偏低", "流动性良好", "尾部风险低", "相关性偏低/分化更明显"],
    actionHints: ["允许更高风险预算", "更偏趋势/Carry", "风控可放松但保留止损"],
  },
  NORMAL_VOL_STABLE: {
    title: "常态波动 / 稳定",
    traits: ["波动处于常态区间", "流动性稳定", "尾部风险可控", "结构性机会更多"],
    actionHints: ["适合多策略并行", "保持仓位纪律", "关注风格轮动"],
  },
  TREND_RISK_ON: {
    title: "风险偏好上行 / 趋势",
    traits: ["趋势强度上升", "回撤相对可控", "资金风险偏好提升", "追随趋势有效"],
    actionHints: ["趋势策略优先", "仓位可适度放大", "避免过度逆势抄底"],
  },
  FRAGILE_HIGH_VOL: {
    title: "高波动 / 脆弱状态",
    traits: ["波动率上升且不稳定", "尾部风险抬升", "流动性更脆弱（冲击成本更高）", "假突破/快速反转更常见"],
    actionHints: ["降低杠杆与仓位", "缩短持有周期", "更严格止损与风控", "优先防御/对冲"],
  },
  LIQUIDITY_SHOCK: {
    title: "流动性冲击",
    traits: ["流动性显著收缩", "波动极端", "相关性上升", "滑点/成交冲击显著"],
    actionHints: ["以保命为主（降仓/观望）", "限制换手", "只做最高置信度信号"],
  },
  POST_SHOCK_REBOUND: {
    title: "冲击后修复 / 反弹",
    traits: ["波动仍高但边际改善", "流动性逐步修复", "风险偏好回升", "反弹阶段更依赖节奏"],
    actionHints: ["分批/节奏化进出", "优先高流动性标的", "警惕二次下探"],
  },
  TRANSITION: {
    title: "过渡态",
    traits: ["状态切换频繁", "信号一致性差", "不确定性高"],
    actionHints: ["降低交易频率", "等待状态确认", "以小仓试错"],
  },
  INFLATION_ENERGY_SHOCK: {
    title: "通胀/能源冲击",
    traits: ["宏观冲击主导", "期限/风格分化", "定价因子切换"],
    actionHints: ["偏宏观对冲", "控制暴露", "关注大宗/利率相关风险"],
  },
  UNKNOWN: {
    title: "未知",
    traits: ["模型或数据不确定", "解释有限"],
    actionHints: ["以保守风控为主", "优先检查数据源与指标稳定性"],
  },
};

function regimeHelp(label?: string | null) {
  if (!label) return null;
  return REGIME_HELP[label] || { title: "未定义", traits: ["暂无预设解释"], actionHints: ["可补充该 regime 的定义与特征"], label };
}

export default function RegimeMonitorPage() {
  const [state, setState] = useState<LoadState>("loading");
  const [current, setCurrent] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [shocks, setShocks] = useState<any[]>([]);
  const [similarPeriods, setSimilarPeriods] = useState<SimilarPeriodLookupItem[]>([]);
  const [currentProfile, setCurrentProfile] = useState<CurrentStateProfile | null>(null);
  const [recomputeLoading, setRecomputeLoading] = useState(false);
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [regimeHelpOpen, setRegimeHelpOpen] = useState(false);
  const [enums, setEnums] = useState<EnumsMeta | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const [c, h, t, s, sp, cp, em] = await Promise.all([
        getRegimeCurrent(),
        getRegimeHistory(),
        getRegimeTimeline(),
        getShockEvents(),
        getRegimeSimilarPeriods(20),
        getCurrentStateProfile(),
        getEnumsMeta(),
      ]);
      setCurrent(c);
      setHistory(h.items);
      setTimeline(t.items);
      setShocks(s.items);
      setSimilarPeriods(sp.items);
      setCurrentProfile(cp);
      setEnums(em);
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRecomputeSimilar() {
    setRecomputeLoading(true);
    try {
      const res = await recomputeRegimeSimilarPeriods();
      message.success(`Recomputed similar periods (${res.lookup_rows} rows)`);
      await load();
    } catch {
      message.error("Failed to recompute similar periods");
    } finally {
      setRecomputeLoading(false);
    }
  }

  if (state === "loading") return <Skeleton active paragraph={{ rows: 12 }} />;
  if (state === "error" || !current) return <ErrorState title="Regime monitor load failed" onRetry={load} />;

  return (
    <PageContainer title="Regime Monitor" subtitle="Current regime state, timeline, and recent shock context">
      <Card>
        <Descriptions column={5}>
          <Descriptions.Item
            label={
              <Space size={6}>
                <span>Current Regime</span>
                <Button size="small" type="link" onClick={() => setRegimeHelpOpen(true)} style={{ padding: 0 }}>
                  说明
                </Button>
              </Space>
            }
          >
            <Popover
              title={
                <Space size={8}>
                  <RegimeBadge value={current.regime_label} />
                  <Typography.Text>{regimeHelp(current.regime_label)?.title || ""}</Typography.Text>
                </Space>
              }
              content={
                <div style={{ maxWidth: 420 }}>
                  <Typography.Text type="secondary">特点</Typography.Text>
                  <div style={{ marginTop: 6 }}>
                    {(regimeHelp(current.regime_label)?.traits || []).map((t) => (
                      <div key={t}>- {t}</div>
                    ))}
                  </div>
                  <div style={{ marginTop: 10 }}>
                    <Typography.Text type="secondary">建议</Typography.Text>
                    <div style={{ marginTop: 6 }}>
                      {(regimeHelp(current.regime_label)?.actionHints || []).map((t) => (
                        <div key={t}>- {t}</div>
                      ))}
                    </div>
                  </div>
                </div>
              }
              trigger="hover"
            >
              <Space size={8}>
                <RegimeBadge value={current.regime_label} />
                <Tag color="default">共 {(enums?.regime_label || []).length || new Set(timeline.map((x) => x.regime_label)).size} 类</Tag>
              </Space>
            </Popover>
          </Descriptions.Item>
          <Descriptions.Item label="Interpretation">{regimeHelp(current.regime_label)?.title || ""}</Descriptions.Item>
          <Descriptions.Item label="Last Change">{current.snapshot_time}</Descriptions.Item>
          <Descriptions.Item label="Market Risk">{current.market_risk_level}</Descriptions.Item>
          <Descriptions.Item label="Data Source">{current.data_source || "unknown"}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Drawer title="Regime 词典" open={regimeHelpOpen} onClose={() => setRegimeHelpOpen(false)} width={860}>
        <Table
          size="small"
          rowKey={(r) => r.label}
          dataSource={(enums?.regime_label || Array.from(new Set(timeline.map((x) => x.regime_label)))).map((label) => ({
            label,
            title: regimeHelp(label)?.title || "",
            traits: regimeHelp(label)?.traits || [],
            actionHints: regimeHelp(label)?.actionHints || [],
            isCurrent: label === current.regime_label,
          }))}
          pagination={false}
          columns={[
            {
              title: "Regime",
              dataIndex: "label",
              width: 220,
              render: (_: string, r) => (
                <Space size={8}>
                  <RegimeBadge value={r.label} />
                  {r.isCurrent ? <Tag color="purple">当前</Tag> : null}
                </Space>
              ),
            },
            { title: "含义", dataIndex: "title", width: 220 },
            {
              title: "特点",
              dataIndex: "traits",
              render: (v: string[]) => (
                <Space direction="vertical" size={2}>
                  {v.slice(0, 4).map((x) => (
                    <span key={x}>- {x}</span>
                  ))}
                </Space>
              ),
            },
          ]}
        />
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          说明：regime 是“市场状态”标签，用于风控/策略路由。实际定义以你们模型产出的规则与阈值为准；这里是面向用户的可读解释层。
        </Typography.Paragraph>
      </Drawer>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={6} xs={12}><Card><Typography.Text type="secondary">Volatility</Typography.Text><Progress percent={Math.round(current.cpd_score * 100)} status="active" /></Card></Col>
        <Col xl={6} xs={12}><Card><Typography.Text type="secondary">Liquidity</Typography.Text><Progress percent={68} status="active" /></Card></Col>
        <Col xl={6} xs={12}><Card><Typography.Text type="secondary">Tail Risk</Typography.Text><Progress percent={Math.round(current.severity_score * 100)} status="exception" /></Card></Col>
        <Col xl={6} xs={12}><Card><Typography.Text type="secondary">Severity</Typography.Text><Progress percent={Math.round(current.severity_score * 100)} status="normal" /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={12} xs={24}>
          <Card
            title="Regime Timeline"
            extra={
              <Space>
                <Typography.Text type="secondary">显示前 10 / 共 {timeline.length}</Typography.Text>
                <Button size="small" onClick={() => setTimelineOpen(true)}>
                  预览全部
                </Button>
              </Space>
            }
          >
            <Table
              size="small"
              rowKey={(r) => `${r.start}-${r.regime_label}`}
              dataSource={timeline.slice(0, 10)}
              pagination={false}
              columns={[
                { title: "Start", dataIndex: "start", width: 180 },
                { title: "End", dataIndex: "end", width: 180 },
                { title: "Regime", dataIndex: "regime_label" },
              ]}
            />
          </Card>
        </Col>
        <Col xl={12} xs={24}>
          <Card title="CPD Score">
            <Line data={history} xField="time" yField="cpd_score" height={260} />
          </Card>
        </Col>
      </Row>

      <Drawer
        title={`Regime Timeline（共 ${timeline.length} 条）`}
        open={timelineOpen}
        onClose={() => setTimelineOpen(false)}
        width={860}
      >
        <Table
          size="small"
          rowKey={(r) => `${r.start}-${r.regime_label}`}
          dataSource={timeline}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          columns={[
            { title: "Start", dataIndex: "start", width: 180 },
            { title: "End", dataIndex: "end", width: 180 },
            { title: "Regime", dataIndex: "regime_label" },
          ]}
        />
      </Drawer>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={12} xs={24}>
          <Card title="Severity Score">
            <Line data={history} xField="time" yField="severity_score" height={260} />
          </Card>
        </Col>
        <Col xl={12} xs={24}>
          <Card title="VIX / VRP / ILLIQ Overlay">
            <Column
              data={history.flatMap((h) => [
                { time: h.time, metric: "vix", value: h.vix },
                { time: h.time, metric: "vrp", value: h.vrp },
                { time: h.time, metric: "illiq", value: h.illiq },
              ])}
              xField="time"
              yField="value"
              seriesField="metric"
              height={260}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Recent Shock Events" style={{ marginTop: 16 }}>
        <Table
          rowKey="event_id"
          dataSource={shocks}
          columns={[
            { title: "Event Date", dataIndex: "event_date", width: 120 },
            { title: "Event Type", dataIndex: "event_type" },
            { title: "Severity", dataIndex: "severity", width: 100 },
            { title: "Detected Regime", dataIndex: "detected_regime", width: 180 },
            { title: "Status", dataIndex: "status", width: 100 },
            { title: "Replay", render: () => <a>Replay Link</a>, width: 100 },
          ]}
        />
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xl={8} xs={24}>
          <Card
            title="Current State Profile"
            extra={
              <Button size="small" loading={recomputeLoading} onClick={handleRecomputeSimilar}>
                Recompute Similar
              </Button>
            }
          >
            {currentProfile ? (
              <Space direction="vertical" size={4}>
                <div>As-Of: {currentProfile.asof_date}</div>
                <div>DBSCAN Label: {currentProfile.dbscan_label}</div>
                <div>Noise Mode: {currentProfile.is_noise ? "YES" : "NO"}</div>
                <div>Nearest Cluster: {currentProfile.nearest_cluster_label}</div>
                <div>Risk Regime: <RegimeBadge value={currentProfile.risk_regime} /></div>
                <div>Market State: {currentProfile.market_state}</div>
                <div>Event Context: {currentProfile.event_context}</div>
                <div>Similarity Confidence: {(currentProfile.similarity_confidence * 100).toFixed(1)}%</div>
              </Space>
            ) : (
              <Typography.Text type="secondary">No profile data</Typography.Text>
            )}
          </Card>
        </Col>
        <Col xl={16} xs={24}>
          <Card title="Similar Historical Periods (Top-K)">
            <Table
              size="small"
              rowKey={(r) => `${r.match_rank}-${r.matched_date}`}
              dataSource={similarPeriods}
              pagination={{ pageSize: 10 }}
              columns={[
                { title: "Rank", dataIndex: "match_rank", width: 70 },
                { title: "Matched Date", dataIndex: "matched_date", width: 120 },
                { title: "Distance", dataIndex: "distance_total", width: 110, render: (v: number) => v.toFixed(3) },
                { title: "Regime", dataIndex: "matched_risk_regime", width: 150, render: (v: string) => <RegimeBadge value={v} /> },
                { title: "State", dataIndex: "matched_market_state", width: 170 },
                { title: "Event", dataIndex: "matched_event_context", width: 230 },
                {
                  title: "Fwd5",
                  dataIndex: "matched_fwd5_return",
                  width: 90,
                  render: (v?: number | null) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : "N/A"),
                },
                {
                  title: "Fwd10",
                  dataIndex: "matched_fwd10_return",
                  width: 90,
                  render: (v?: number | null) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : "N/A"),
                },
                {
                  title: "ES05",
                  dataIndex: "matched_fwd10_es05",
                  width: 90,
                  render: (v?: number | null) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : "N/A"),
                },
              ]}
              scroll={{ x: 1200 }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="标签说明" style={{ marginTop: 16 }}>
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Typography.Text type="secondary">
            这些标签用于解释当前市场状态/风险，不代表单只股票建议。若你指的是“信号列表里每只股票的标签”，我也可以在对应页面加同样的解释区。
          </Typography.Text>
          <Descriptions column={1} size="small">
            <Descriptions.Item
              label={
                <Space size={6}>
                  <span>Current Regime</span>
                  <Tooltip title="综合市场状态标签（风险/波动/流动性/事件等的组合输出）">
                    <Typography.Text type="secondary">?</Typography.Text>
                  </Tooltip>
                </Space>
              }
            >
              当前市场所处的宏观“状态桶”，用于路由策略/风控。
            </Descriptions.Item>
            <Descriptions.Item label="CPD Score">状态切换的“变点强度”评分，越高表示更可能发生 regime 切换。</Descriptions.Item>
            <Descriptions.Item label="Severity Score">极端风险/压力强度评分，越高表示尾部风险更突出。</Descriptions.Item>
            <Descriptions.Item label="Market Risk">离散化后的风险等级（如 LOW/MEDIUM/HIGH），用于快速风控决策。</Descriptions.Item>
            <Descriptions.Item label="Risk Regime">风控视角的 regime（例如 risk-on / risk-off / stress）。</Descriptions.Item>
            <Descriptions.Item label="Market State">市场结构状态（例如趋势/震荡/分化等）。</Descriptions.Item>
            <Descriptions.Item label="Event Context">事件环境标签（例如宏观冲击/政策/地缘等）。</Descriptions.Item>
            <Descriptions.Item label="DBSCAN Label">聚类算法输出的簇编号；is_noise=YES 表示当前点不稳定或属于离群。</Descriptions.Item>
            <Descriptions.Item label="Similarity Confidence">当前状态与历史簇/相似期匹配的置信度。</Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>
    </PageContainer>
  );
}
