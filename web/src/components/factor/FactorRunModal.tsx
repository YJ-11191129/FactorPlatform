"use client";

import { Form, InputNumber, Modal, Select, Switch, Typography } from "antd";
import { useEffect } from "react";

export type RunMode = "demo" | "qlib";

export type FactorRunFormValues = {
  instrument_limit: number;
  universe: string;
  save: boolean;
  n: number;
};

export function FactorRunModal(props: {
  open: boolean;
  mode: RunMode;
  factorName: string;
  loading?: boolean;
  onCancel: () => void;
  onSubmit: (values: FactorRunFormValues) => void;
}) {
  const [form] = Form.useForm<FactorRunFormValues>();

  useEffect(() => {
    if (!props.open) return;
    form.setFieldsValue({
      instrument_limit: 50,
      universe: "csi300",
      save: true,
      n: 20,
    });
  }, [props.open, form]);

  return (
    <Modal
      open={props.open}
      title={props.mode === "demo" ? "运行 Demo" : "运行 Qlib"}
      okText="提交运行"
      onCancel={props.onCancel}
      confirmLoading={props.loading}
      onOk={() => {
        form.validateFields().then((v) => props.onSubmit(v));
      }}
      destroyOnClose
    >
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 0 }}>
        因子：<Typography.Text code>{props.factorName}</Typography.Text>
      </Typography.Paragraph>
      <Form layout="vertical" form={form}>
        <Form.Item label="参数 n" name="n" rules={[{ required: true, message: "请输入 n" }]}>
          <InputNumber min={1} max={252} style={{ width: "100%" }} />
        </Form.Item>
        {props.mode === "qlib" ? (
          <>
            <Form.Item label="股票池 universe" name="universe" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: "csi300", label: "csi300" },
                  { value: "csi500", label: "csi500" },
                  { value: "csi100", label: "csi100" },
                  { value: "all", label: "all" },
                ]}
              />
            </Form.Item>
            <Form.Item label="instrument_limit" name="instrument_limit" rules={[{ required: true }]}>
              <InputNumber min={1} max={5000} style={{ width: "100%" }} />
            </Form.Item>
          </>
        ) : null}
        <Form.Item label="保存结果到 Parquet（生成 calc_batch_id）" name="save" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}

