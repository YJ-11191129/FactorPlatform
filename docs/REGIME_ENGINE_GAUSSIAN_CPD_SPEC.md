# REGIME_ENGINE_GAUSSIAN_CPD_SPEC.md

- 版本：v1.0
- 日期：2026-03-29
- 适用范围：Signal Center / Regime Engine v1
- 目标：定义基于 Gaussian CPD 的状态识别引擎（离线分段、状态聚类、标签映射、下游消费）。

---

## 1. 文档目标

定义 Regime Engine v1 的实现规范：

- regime shift 统计定义
- state vector 构建
- Gaussian CPD（`ruptures.Pelt + CostNormal`）离线分段
- DBSCAN 状态聚类与业务标签映射
- `regime_snapshot` / `regime_breakpoints` 产物
- 与 filter / router / signal engine 接口契约
- 可解释、可回放、可审计要求

---

## 2. Regime Shift 定义

regime shift 定义为：状态向量生成机制发生显著变化（均值、波动、尾部风险、流动性、风险偏好或协方差结构变化）。

数学形式：分段高斯近似

- `X_t in R^d`
- 存在断点 `tau_1 ... tau_k`
- 每段 `X_t ~ N(mu_k, Sigma_k)`
- 相邻段满足 `mu` 或 `Sigma` 显著变化

---

## 3. 架构

```text
Bars -> Feature Engine -> State Vector Builder
    -> Gaussian CPD (PELT + CostNormal)
    -> Segment Summary -> DBSCAN
    -> Label Mapper -> Snapshot Store
    -> Filter / Router / Signal / Attribution
```

---

## 4. 输入与状态向量

输入层建议：

- 收益与波动：`rv_20`, `semivol_20-`, `tail loss / ES`, `drawdown`
- 流动性与量价：`illiq_20`, `volume_z_20`, `turnover_z_20`, `dispersion_20`, `breadth_stress`
- 跨资产风险：`vix_z`, `vrp_z`, 利率/商品/汇率 proxy

v1 推荐 8~10 维（可做 A 股纯本土版）。

---

## 5. 预处理规范

- 缺失值：不得直接带 NaN 进 CPD
- 去极值：推荐 1/99 或 2.5/97.5 winsorize
- 标准化：优先 `RobustScaler`
- 降维：维度 > 10 时建议 PCA 到 4~6 维（累计方差 > 80%）

---

## 6. Gaussian CPD 主算法

基线实现：

```python
import ruptures as rpt

cost = rpt.costs.CostNormal()
algo = rpt.Pelt(custom_cost=cost, min_size=20, jump=1).fit(X)
bkps = algo.predict(pen=penalty)
```

参数约束：

- `min_size`（v1 默认 20）
- `jump`（研究默认 1）
- `penalty` 必须网格搜索（例如 `{2,4,6,8,10,12,15,20}`）

---

## 7. Breakpoint Severity

建议用断点左右窗口特征均值差加权：

- 左右窗口如 `[-10,-1]` 和 `[+1,+10]`
- 特征先标准化后比较
- 重点风险维度可给更高权重（如 ES/尾损、VIX、ILLIQ）

---

## 8. DBSCAN 规范

- 输入：标准化后的状态向量或 PCA embedding（3~5 维）
- 默认起点：`eps=1.0`, `min_samples=10`
- 输出：
  - `cluster_id >= 0`：有效簇
  - `cluster_id = -1`：噪声/过渡态

---

## 9. 业务 Regime 标签映射（v1）

建议 v1 映射为 5 类：

- `CALM_LOW_VOL`
- `TREND_RISK_ON`
- `FRAGILE_HIGH_VOL`
- `LIQUIDITY_SHOCK`
- `POST_SHOCK_REBOUND`

映射依据：`cluster + segment summary + 规则阈值`。

---

## 10. 输出结构

### 10.1 `regime_snapshot_daily`

- `date`, `scope`, `regime_label`, `cluster_id`
- `cpd_boundary_flag`, `cpd_score`, `severity_score`
- `rv_20`, `es_975`, `illiq_20`, `vix_z`, `vrp_z`, `breadth_stress`
- `computed_at`, `model_version`

### 10.2 `regime_breakpoints`

- `breakpoint_date`
- 左右段起止日期
- `penalty`, `min_size`, `jump`
- `severity_score`, `event_hit_flag`, `model_version`

### 10.3 `regime_cluster_map`

- `cluster_id`, `mapped_label`, `centroid_features`
- `rule_version`, `valid_from`

---

## 11. 下游接口契约

给 Filter Engine 的最小字段：

- `regime_label`, `severity_score`, `cpd_boundary_flag`
- `vix_z`, `vrp_z`, `illiq_20`, `breadth_stress`

给 Router 的最小字段：

- `regime_label`, `severity_score`, `shock_proximity`, `cluster_id`

用于决定：

- template、threshold、position cap、止损模板、rebalance mode

---

## 12. v1 边界

v1 不做：

- BOCPD 在线后验
- HMM / Switching VAR / 复杂深度表示学习
- 多市场多频联合变点同步

v1 必做：

- 可稳定重算、可解释、可审计的离线 regime 分段
- 提供真实 `regime/current` 与 `regime/history`
- 可被 filter/router/signal 消费

---

## 13. 实施与验收

实施阶段：

1. State Vector 接入与预处理
2. Gaussian CPD + severity + breakpoints 落库
3. DBSCAN + label mapping + snapshot 落库
4. API 替换 mock（`/api/v1/regime/*` 与 signal detail 中 snapshot）

验收标准：

- 能稳定产出 `regime_snapshot_daily` 与 `regime_breakpoints`
- 已知 shock 窗口附近断点命中可解释
- 下游 filter/router 可直接消费
- regime 分层下 signal 频率/收益/回撤有方向性差异

