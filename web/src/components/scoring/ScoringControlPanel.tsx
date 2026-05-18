"use client";

import { Button, Card, DatePicker, Form, Select, Space, Switch } from "antd";

export type ScoringParams = {
  date?: string;
  universe: string;
  template: string;
  weight: string;
  industryConstraint: boolean;
  riskControl: boolean;
};

export function ScoringControlPanel(props: { loading?: boolean; onGenerate: (p: ScoringParams) => void; onExport: () => void }) {
  const [form] = Form.useForm<ScoringParams>();

  return (
    <Card styles={{ body: { padding: 16 } }} style={{ borderRadius: 12 }}>
      <Form
        form={form}
        layout="inline"
        initialValues={{ universe: "csi300", template: "core", weight: "default", industryConstraint: true, riskControl: true }}
        onFinish={(value) => props.onGenerate(value)}
      >
        <Form.Item label="Score Date" name="date">
          <DatePicker />
        </Form.Item>
        <Form.Item label="Universe" name="universe">
          <Select style={{ width: 140 }} options={[{ value: "csi300" }, { value: "csi500" }, { value: "all" }]} />
        </Form.Item>
        <Form.Item label="Factor Basket" name="template">
          <Select style={{ width: 140 }} options={[{ value: "core" }, { value: "alpha" }, { value: "custom" }]} />
        </Form.Item>
        <Form.Item label="Weights" name="weight">
          <Select style={{ width: 140 }} options={[{ value: "default" }, { value: "equal" }]} />
        </Form.Item>
        <Form.Item label="Industry Constraint" name="industryConstraint" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item label="Risk Control" name="riskControl" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={props.loading}>
              Generate
            </Button>
            <Button onClick={props.onExport}>Export CSV</Button>
            <Button onClick={() => form.resetFields()}>Reset</Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
}
