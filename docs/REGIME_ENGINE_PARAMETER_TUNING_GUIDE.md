# REGIME_ENGINE_PARAMETER_TUNING_GUIDE.md

- 版本：v1.0
- 日期：2026-03-29
- 适用范围：Signal Center / Regime Engine / Gaussian CPD + DBSCAN
- 目标：给出 v1 参数微调、实验矩阵、评估体系与选优规则。

---

## 1. 调参目标

回答以下问题：

- `min_size / jump / penalty` 怎么选
- `eps / min_samples` 怎么选
- 如何避免“断点太碎”与“断点太迟钝”
- 如何以 filter/router/signal 改善作为最终标准

核心原则：不是追求更多断点，而是追求稳定、可解释、可落地的分段。

---

## 2. 总原则

1. 先固定 state vector，再调参数
2. 先做粗 regime（5 类），再细分
3. 以“下游效果”作为最终判据，不以图形好看为准

---

## 3. CPD 调参对象

核心参数：

- `min_size`
- `jump`
- `penalty`
- 输入维度 / PCA 维度

辅助参数：

- `epsilon`（协方差正则）
- winsorize 比例
- scaler 方案

---

## 4. `min_size`

含义：相邻断点的最短样本长度。

搜索网格（日频）：

- `{10, 15, 20, 30, 40}`

默认建议：

- `min_size = 20`

经验：

- 太小：断点碎、router/filter 抖动
- 太大：shock 识别迟、修复段切不出来

---

## 5. `jump`

含义：候选断点步长。

建议：

- 研究：`jump = 1`
- 批量重算：`jump = 3` 或 `5`

v1 基准：`jump = 1`，首轮先不与其他参数联动。

---

## 6. `penalty`

含义：PELT 复杂度惩罚项（小则断点多，大则断点少）。

推荐网格：

- 固定网格：`{2,4,6,8,10,12,15,20}`
- 或 `c * log(T)`，`c in {2,4,6,8,10}`

选择标准：

1. 已知 shock 命中
2. 分段稳定性
3. 经济解释性
4. 下游 filter/router/signal 改善

---

## 7. 输入维度与 PCA

建议：

- 原始特征控制在 8~10 维
- PCA 输出 4~6 维

对比实验：

- 无 PCA
- PCA 4 维
- PCA 5 维
- PCA 6 维

关注：

- 断点稳定性
- 聚类分离度
- 下游 regime 分层效果

---

## 8. DBSCAN 调参

参数网格：

- `eps in {0.6, 0.8, 1.0, 1.2, 1.5}`
- `min_samples in {8, 10, 12, 15}`

默认起点：

- `eps = 1.0`
- `min_samples = 10`

判读：

- 噪声点过多：eps 过小或 embedding 不稳
- 一个巨簇：eps 过大

---

## 9. 推荐实验矩阵

### 第一轮（只调 CPD）

- 固定 DBSCAN 与输入处理
- 扫 `min_size x penalty`
- 基准 `jump=1`

### 第二轮（固定 CPD 调 DBSCAN）

- 扫 `eps x min_samples`

### 第三轮（联合验证）

- 取前 3~5 组参数
- 做 filter/router/signal/performance 对比

---

## 10. 评估指标体系

事件层：

- `Shock Hit Rate`（事件窗口 ±5 日命中）
- `Average Detection Lag`

统计层：

- `Segment Stability Score`
- Bootstrap/Jitter 后断点一致性

聚类层：

- 噪声比例
- 聚类可分性（silhouette 仅作参考）

策略层：

- `Signal Frequency by Regime`
- `Performance Separation by Regime`
- `Filter Lift`

---

## 11. 实验记录模板（建议）

每次实验输出 `meta.json`，至少包含：

- `state_vector_version`
- `preprocess`（winsorize/scaler/pca）
- `cpd`（method/min_size/jump/penalty）
- `dbscan`（eps/min_samples）
- `metrics`（breakpoint_count/shock_hit_rate/lag/noise_ratio/filter_lift 等）

---

## 12. 选优规则（综合评分）

建议综合分：

`Score = a1*ShockHit + a2*Stability + a3*RegimeSeparation + a4*FilterLift - a5*OverSegPenalty`

示例权重：

- Shock hit: 0.25
- Stability: 0.20
- Regime separation: 0.20
- Filter lift: 0.20
- Over-segmentation penalty: 0.15

---

## 13. 常见失败模式与修复

1. 断点太碎
- 提高 `min_size` / `penalty`
- 降噪与特征精简

2. 断点太少
- 降低 `penalty` / `min_size`
- 强化风险维度权重

3. DBSCAN 全噪声
- 增大 `eps`
- 调整 embedding / PCA 维度

4. 标签不可解释
- 增加 `cluster + segment summary` 联合映射规则
- 强化 illiq / breadth / tail-risk 条件

---

## 14. v1 推荐基线

CPD：

- `PELT + CostNormal`
- `min_size = 20`
- `jump = 1`
- `penalty in {6,8,10}`

State Vector：

- 8 维
- winsorize 1/99
- robust scale
- PCA 5 维

DBSCAN：

- `eps = 1.0`
- `min_samples = 10`

业务标签：

- 5 类粗 regime

---

## 15. 调参产物要求

每轮至少产出：

- `breakpoints.csv`
- `regime_snapshot.parquet`
- `cluster_map.json`
- `tuning_meta.json`
- `evaluation_report.md`

报告最低要求：

- 断点图
- shock 命中统计
- regime 分布
- 噪声比例
- 分 regime 下 signal 频率与绩效摘要

---

## 16. 最终验收标准

1. 已知 shock 窗口附近有可解释断点
2. 分段不过碎且符合业务节奏
3. DBSCAN 既不全噪声也不单巨簇
4. 5 类 regime 具备业务解释性
5. filter/router 有正向 lift
6. 重算稳定（轻扰动后核心结论不反转）

