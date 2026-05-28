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
      title={props.mode === "demo" ? "Run Demo Factor" : "Run Market Factor"}
      okText="Submit Run"
      onCancel={props.onCancel}
      confirmLoading={props.loading}
      onOk={() => {
        form.validateFields().then((v) => props.onSubmit(v));
      }}
      destroyOnClose
    >
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 0 }}>
        Factor: <Typography.Text code>{props.factorName}</Typography.Text>
      </Typography.Paragraph>
      <Form layout="vertical" form={form}>
        <Form.Item label="Parameter n" name="n" rules={[{ required: true, message: "Enter n" }]}>
          <InputNumber min={1} max={252} style={{ width: "100%" }} />
        </Form.Item>
        {props.mode === "qlib" ? (
          <>
            <Form.Item label="Universe" name="universe" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: "csi300", label: "CSI 300" },
                  { value: "csi500", label: "CSI 500" },
                  { value: "csi100", label: "CSI 100" },
                  { value: "all", label: "All instruments" },
                ]}
              />
            </Form.Item>
            <Form.Item label="Instrument limit" name="instrument_limit" rules={[{ required: true }]}>
              <InputNumber min={1} max={5000} style={{ width: "100%" }} />
            </Form.Item>
          </>
        ) : null}
        <Form.Item label="Save result artifact" name="save" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}
