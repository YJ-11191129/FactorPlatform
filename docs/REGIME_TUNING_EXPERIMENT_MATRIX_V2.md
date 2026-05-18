# REGIME_TUNING_EXPERIMENT_MATRIX_V2.md

## 1. 目标

围绕 NPDP 版本进一步调优 `penalty/min_size`，平衡：

- 断点密度（不过碎）
- shock/transition 命中率
- 下游 filter/router 稳定性

## 2. 固定项

- jump = 1
- state vector 与预处理固定
- DBSCAN 暂固定为 `eps=1.0`, `min_samples=10`

## 3. 参数矩阵

| case | penalty | min_size | jump |
|---|---:|---:|---:|
| A | 12 | 20 | 1 |
| B | 15 | 20 | 1 |
| C | 10 | 25 | 1 |
| D | 12 | 25 | 1 |
| E | 15 | 25 | 1 |
| F | 12 | 30 | 1 |

## 4. 评价指标

- `rows_breakpoints`
- `breakpoints_per_100_rows`
- `avg_segment_len`
- `primary_hit_count`
- `secondary_hit_count`
- 组合评分（可自定义）

## 5. 推荐执行

运行：

```bash
python scripts/run_regime_tuning_matrix_v2.py
```

产物：

- `data/exports/regime_engine/regime_tuning_matrix_v2.json`
- `data/exports/regime_engine/regime_tuning_matrix_v2.md`

