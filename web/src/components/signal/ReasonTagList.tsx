"use client";

import { Space, Tag } from "antd";

export function ReasonTagList(props: { tags: string[]; max?: number }) {
  const max = props.max ?? 3;
  const shown = props.tags.slice(0, max);
  const hiddenCount = Math.max(0, props.tags.length - max);

  return (
    <Space size={[6, 6]} wrap>
      {shown.map((tag) => (
        <Tag key={tag}>{tag}</Tag>
      ))}
      {hiddenCount > 0 ? <Tag>+{hiddenCount}</Tag> : null}
    </Space>
  );
}
