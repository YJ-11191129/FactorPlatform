# REGIME_EVENT_LIBRARY_SPEC.md

## 1. 目标

定义 Regime Engine 的事件库，用于断点命中分类：

- `PRIMARY_SHOCK_HIT`
- `SECONDARY_TRANSITION_HIT`
- `NONE`

## 2. 数据结构

```json
{
  "primary_shocks": ["2020-02-03", "2022-04-25", "2024-10-09", "2025-04-07"],
  "secondary_transitions": ["2020-03-02", "2020-07-16", "2022-05-26", "2024-02-05", "2024-03-12", "2024-05-17", "2024-11-06", "2025-05-08"]
}
```

## 3. 命中规则

1. 先判主事件：
- `abs(bp_date - primary_shock_date) <= shock_hit_window_days` -> `PRIMARY_SHOCK_HIT`

2. 再判次级转折事件：
- `abs(bp_date - secondary_transition_date) <= secondary_hit_window_days` -> `SECONDARY_TRANSITION_HIT`

3. 最后判主事件后滞后窗口（兜底）：
- `transition_hit_start_days <= (bp_date - primary_shock_date) <= transition_hit_end_days` -> `SECONDARY_TRANSITION_HIT`

4. 否则：
- `NONE`

## 4. 配置项

- `FACTOR_PLATFORM_SHOCK_DATES`
- `FACTOR_PLATFORM_SECONDARY_DATES`
- `FACTOR_PLATFORM_SHOCK_HIT_WINDOW_DAYS`
- `FACTOR_PLATFORM_SECONDARY_HIT_WINDOW_DAYS`
- `FACTOR_PLATFORM_TRANSITION_HIT_START_DAYS`
- `FACTOR_PLATFORM_TRANSITION_HIT_END_DAYS`

## 5. 输出字段

每个 breakpoint 输出：

- `event_hit_flag: bool`
- `event_hit_type: PRIMARY_SHOCK_HIT | SECONDARY_TRANSITION_HIT | NONE`

