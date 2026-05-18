"use client";

import { Button, Input, Select, Space } from "antd";

export type FactorFilters = {
  q?: string;
  category?: string;
  status?: string;
};

export function FactorFilterBar(props: {
  loading?: boolean;
  categories: string[];
  value: FactorFilters;
  onChange: (v: FactorFilters) => void;
  onRefresh: () => void;
}) {
  return (
    <Space wrap style={{ width: "100%", justifyContent: "space-between" }}>
      <Space wrap>
        <Input.Search
          placeholder="搜索因子名 / 中文名"
          allowClear
          style={{ width: 280 }}
          value={props.value.q}
          onChange={(e) => props.onChange({ ...props.value, q: e.target.value })}
          onSearch={() => {}}
        />
        <Select
          placeholder="分类"
          allowClear
          style={{ width: 160 }}
          options={props.categories.map((c) => ({ value: c, label: c }))}
          value={props.value.category}
          onChange={(v) => props.onChange({ ...props.value, category: v })}
        />
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 160 }}
          options={[
            { value: "draft", label: "draft" },
            { value: "research", label: "research" },
            { value: "online", label: "online" },
            { value: "offline", label: "offline" },
          ]}
          value={props.value.status}
          onChange={(v) => props.onChange({ ...props.value, status: v })}
        />
      </Space>
      <Button onClick={props.onRefresh} loading={props.loading}>
        刷新
      </Button>
    </Space>
  );
}

