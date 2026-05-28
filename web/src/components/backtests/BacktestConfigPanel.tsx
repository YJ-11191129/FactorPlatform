"use client";

import { Alert, Button, Card, DatePicker, Form, Input, InputNumber, Select, Space, Switch, Typography, message } from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { useEffect, useMemo } from "react";

import type { BacktestRunPayload } from "@/types/backtest";
import type { StrategyInfo } from "@/types/strategy";

type FormValues = {
  start_date?: Dayjs | null;
  end_date?: Dayjs | null;
  universe_text?: string;
  data_source: "qlib_auto" | "qlib_cn" | "qlib_us" | "wind_parquet";
  qlib_universe?: string | null;
  initial_cash: number;
  fee_bps: number;
  use_adj: boolean;
} & Record<string, any>;

function isNumberType(t?: string) {
  return t === "int" || t === "float" || t === "number";
}

function splitUniverse(raw: string | undefined): string[] | null {
  const values = String(raw || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
  return values.length ? values : null;
}

function qlibRegion(value: FormValues["data_source"]): string | null {
  if (value === "qlib_cn") return "cn";
  if (value === "qlib_us") return "us";
  return null;
}

export function BacktestConfigPanel(props: {
  strategy: StrategyInfo | null;
  loading?: boolean;
  onRun: (payload: BacktestRunPayload) => void | Promise<void>;
}) {
  const [form] = Form.useForm<FormValues>();

  const paramEntries = useMemo(() => Object.entries(props.strategy?.parameter_schema || {}), [props.strategy?.parameter_schema]);

  function defaults(): FormValues {
    return {
      start_date: dayjs().add(-90, "day"),
      end_date: dayjs(),
      data_source: "qlib_auto",
      qlib_universe: "auto",
      universe_text: "",
      initial_cash: 1_000_000,
      fee_bps: 5,
      use_adj: true,
      ...Object.fromEntries(paramEntries.map(([k, v]) => [k, v?.default])),
    };
  }

  useEffect(() => {
    form.setFieldsValue(defaults() as any);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.strategy?.strategy_id]);

  function resetToDefaults() {
    form.setFieldsValue(defaults() as any);
  }

  function setRange(days: number) {
    form.setFieldsValue({
      start_date: dayjs().add(-days, "day"),
      end_date: dayjs(),
    });
  }

  return (
    <Card
      title="回测配置"
      extra={
        <Space wrap>
          <Button onClick={() => setRange(30)} disabled={!props.strategy}>
            近 30 天
          </Button>
          <Button onClick={() => setRange(90)} disabled={!props.strategy}>
            近 90 天
          </Button>
          <Button onClick={() => setRange(180)} disabled={!props.strategy}>
            近 180 天
          </Button>
          <Button onClick={resetToDefaults} disabled={!props.strategy}>
            重置
          </Button>
        </Space>
      }
    >
      {props.strategy ? (
        <>
          <Typography.Paragraph style={{ marginTop: 0 }}>
            <Typography.Text strong>{props.strategy.strategy_name}</Typography.Text>
            <Typography.Text type="secondary"> ({props.strategy.strategy_id})</Typography.Text>
          </Typography.Paragraph>
          <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
            {props.strategy.description}
          </Typography.Paragraph>

          <Alert
            showIcon
            type="info"
            style={{ marginBottom: 16 }}
            message="默认使用 qlib CN/US 数据源"
            description="信号在 t 日收盘后形成，组合收益从下一根 bar 开始计算；页面会记录数据源、交易成本、换手和时序说明。"
          />

          <Form
            form={form}
            layout="vertical"
            initialValues={defaults()}
            onFinish={(v) => {
              if (v.start_date && v.end_date && dayjs(v.start_date).isAfter(dayjs(v.end_date))) {
                message.error("开始日期不能晚于结束日期");
                return;
              }
              const params: Record<string, unknown> = {};
              for (const [k] of paramEntries) params[k] = v[k];
              const dataSource = v.data_source === "wind_parquet" ? "parquet" : "qlib";
              props.onRun({
                strategy_id: props.strategy!.strategy_id,
                params,
                start_date: v.start_date ? dayjs(v.start_date).format("YYYY-MM-DD") : null,
                end_date: v.end_date ? dayjs(v.end_date).format("YYYY-MM-DD") : null,
                universe: splitUniverse(v.universe_text),
                data_source: dataSource,
                qlib_region: qlibRegion(v.data_source),
                qlib_universe: v.qlib_universe && v.qlib_universe !== "auto" ? String(v.qlib_universe) : null,
                initial_cash: Number(v.initial_cash),
                fee_bps: Number(v.fee_bps),
                use_adj: Boolean(v.use_adj),
              });
            }}
          >
            <Space size={12} style={{ width: "100%" }} align="start" wrap>
              <Form.Item
                label="开始日期"
                name="start_date"
                rules={[
                  { required: true, message: "请选择开始日期" },
                  ({ getFieldValue }) => ({
                    validator: async (_, value) => {
                      const end = getFieldValue("end_date");
                      if (!value || !end) return;
                      if (dayjs(value).isAfter(dayjs(end))) throw new Error("开始日期不能晚于结束日期");
                    },
                  }),
                ]}
                style={{ flex: "1 1 180px" }}
              >
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item
                label="结束日期"
                name="end_date"
                rules={[
                  { required: true, message: "请选择结束日期" },
                  ({ getFieldValue }) => ({
                    validator: async (_, value) => {
                      const start = getFieldValue("start_date");
                      if (!value || !start) return;
                      if (dayjs(start).isAfter(dayjs(value))) throw new Error("结束日期不能早于开始日期");
                    },
                  }),
                ]}
                style={{ flex: "1 1 180px" }}
              >
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
            </Space>

            <Space size={12} style={{ width: "100%" }} align="start" wrap>
              <Form.Item label="数据源" name="data_source" style={{ flex: "1 1 220px" }}>
                <Select
                  options={[
                    { label: "Auto qlib (CN/US)", value: "qlib_auto" },
                    { label: "CN qlib", value: "qlib_cn" },
                    { label: "US qlib", value: "qlib_us" },
                    { label: "Wind parquet fallback", value: "wind_parquet" },
                  ]}
                />
              </Form.Item>
              <Form.Item label="qlib 预设池" name="qlib_universe" style={{ flex: "1 1 180px" }}>
                <Select
                  options={[
                    { label: "Auto", value: "auto" },
                    { label: "CSI 300", value: "csi300" },
                    { label: "CSI 500", value: "csi500" },
                    { label: "CSI 1000", value: "csi1000" },
                    { label: "S&P 500", value: "sp500" },
                    { label: "NASDAQ 100", value: "nasdaq100" },
                    { label: "All", value: "all" },
                  ]}
                />
              </Form.Item>
            </Space>

            <Form.Item label="标的列表" name="universe_text">
              <Input placeholder="留空使用预设池；或输入 AAPL, MSFT / 000001.SZ, 600000.SH" />
            </Form.Item>

            <Form.Item label="复权价格" name="use_adj" valuePropName="checked">
              <Switch checkedChildren="使用 adj_factor" unCheckedChildren="不复权" />
            </Form.Item>

            <Space size={12} style={{ width: "100%" }} align="start" wrap>
              <Form.Item
                label="初始资金"
                name="initial_cash"
                rules={[{ required: true, message: "请输入初始资金" }]}
                style={{ flex: "1 1 180px" }}
              >
                <InputNumber min={0} step={10000} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item
                label="交易费率 (bps)"
                name="fee_bps"
                rules={[{ required: true, message: "请输入交易费率" }]}
                style={{ flex: "1 1 180px" }}
              >
                <InputNumber min={0} max={1000} step={1} style={{ width: "100%" }} />
              </Form.Item>
            </Space>

            {paramEntries.length > 0 ? <Typography.Title level={5}>策略参数</Typography.Title> : null}

            {paramEntries.map(([k, def]) => {
              const t = def?.type;
              if (t === "bool") {
                return (
                  <Form.Item key={k} label={k} name={k} valuePropName="checked">
                    <Switch />
                  </Form.Item>
                );
              }
              if (isNumberType(t)) {
                return (
                  <Form.Item key={k} label={k} name={k}>
                    <InputNumber
                      min={typeof def?.min === "number" ? def.min : undefined}
                      max={typeof def?.max === "number" ? def.max : undefined}
                      style={{ width: "100%" }}
                    />
                  </Form.Item>
                );
              }
              return (
                <Form.Item key={k} label={k} name={k}>
                  <Input placeholder="value" />
                </Form.Item>
              );
            })}

            <Form.Item style={{ marginBottom: 0 }}>
              <Button type="primary" htmlType="submit" loading={props.loading} disabled={!props.strategy || props.loading}>
                运行回测
              </Button>
            </Form.Item>
          </Form>
        </>
      ) : (
        <Typography.Text type="secondary">先从左侧选择一个策略。</Typography.Text>
      )}
    </Card>
  );
}
