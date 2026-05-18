# REGIME_PRIMARY_SECONDARY_HIT_EVAL_TEMPLATE.md

## 1. Run Meta

- model_version:
- data_range:
- penalty:
- min_size:
- jump:
- eps / min_samples:

## 2. Hit Summary

- total_breakpoints:
- primary_hit_count:
- secondary_hit_count:
- miss_count:
- hit_rate = (primary + secondary) / total_breakpoints

## 3. Primary Shock Coverage

| primary_shock_date | nearest_breakpoint | distance_days | severity | hit_flag |
|---|---|---:|---:|---|
| 2020-02-03 |  |  |  |  |
| 2022-04-25 |  |  |  |  |
| 2024-10-09 |  |  |  |  |
| 2025-04-07 |  |  |  |  |

## 4. Secondary Transition Coverage

| secondary_date | nearest_breakpoint | distance_days | severity | hit_flag |
|---|---|---:|---:|---|
| 2020-03-02 |  |  |  |  |
| 2020-07-16 |  |  |  |  |
| 2022-05-26 |  |  |  |  |
| 2024-02-05 |  |  |  |  |
| 2024-03-12 |  |  |  |  |
| 2024-05-17 |  |  |  |  |
| 2024-11-06 |  |  |  |  |
| 2025-05-08 |  |  |  |  |

## 5. Miss Analysis

- Top miss dates:
- Expected regime transition:
- Observed nearest breakpoint:
- Potential reason:

## 6. Decision

- 是否通过：
- 是否需要调整参数：
- 下轮建议（penalty/min_size）：

