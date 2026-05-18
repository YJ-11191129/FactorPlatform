# GEO_ENERGY_REAL_RUN_20260329

## Run Config

- data: `D:/Kaggle/Data/wind_data/02_daily_stock/stock_daily_ohlcv.parquet`
- min_size: `20`
- jump: `1`
- penalty: `8`
- dbscan eps/min_samples: `1.0 / 10`
- pca_dim: `5`

## Output Summary

- snapshot rows: `1951`
- breakpoints rows: `91`
- date range: `2018-03-09 ~ 2026-03-25`
- latest: `2026-03-25 / FRAGILE_HIGH_VOL / POST_SHOCK_REBOUND / PERSISTENT_ENERGY_CRISIS_WINDOW_HIT`

## Cluster Counts

- POST_SHOCK_REBOUND: `1625`
- TRANSITION: `238`
- FRAGILE_HIGH_VOL: `84`
- GEO_ENERGY_SHOCK: `4`

## Key Date Snapshot

```text
      date       regime_label      cluster_label                       event_context       market_state market_risk_level  oil_shock_z  fwd5_down_prob  fwd10_es05  cluster_persist_prob
2026-03-12 POST_SHOCK_REBOUND         TRANSITION SECONDARY_GEO_ENERGY_ESCALATION_HIT   RANGE_BOUND_WEAK           EXTREME     2.043099        0.378151   -0.119942              0.617647
2026-03-23   FRAGILE_HIGH_VOL         TRANSITION PERSISTENT_ENERGY_CRISIS_WINDOW_HIT RISK_OFF_DERISKING           EXTREME     0.738516        0.378151   -0.119942              0.617647
2026-03-25   FRAGILE_HIGH_VOL POST_SHOCK_REBOUND PERSISTENT_ENERGY_CRISIS_WINDOW_HIT RISK_OFF_DERISKING           EXTREME     0.512666        0.476923   -0.103320              0.951385
```

## Top Breakpoints (Severity)

```text
breakpoint_date           event_hit_type  severity_score
     2025-04-07        PRIMARY_SHOCK_HIT       19.964077
     2025-05-08 SECONDARY_TRANSITION_HIT       18.540509
     2024-10-09        PRIMARY_SHOCK_HIT       17.107387
     2020-02-03        PRIMARY_SHOCK_HIT       16.400335
     2024-11-06 SECONDARY_TRANSITION_HIT       13.897252
     2024-05-17 SECONDARY_TRANSITION_HIT       13.176398
     2020-03-02 SECONDARY_TRANSITION_HIT       12.257393
     2024-02-05 SECONDARY_TRANSITION_HIT       11.507693
     2022-05-26 SECONDARY_TRANSITION_HIT       11.497917
     2022-04-25        PRIMARY_SHOCK_HIT       11.331408
```

## Cluster Forecast Profile

```text
     cluster_label  sample_size  fwd5_down_prob  fwd10_es05  cluster_persist_prob  to_liquidity_shock_prob  to_extreme_risk_prob
  FRAGILE_HIGH_VOL           84        0.297619   -0.030110              0.833333                      0.0              0.833333
  GEO_ENERGY_SHOCK            4        0.250000   -0.101266              0.750000                      0.0              0.000000
POST_SHOCK_REBOUND         1625        0.476923   -0.103320              0.951385                      0.0              0.000000
        TRANSITION          238        0.378151   -0.119942              0.617647                      0.0              0.058824
```

## Geo Event Evaluation

```text
                            event_id event_date                      event_name        event_type nearest_breakpoint_date  breakpoint_distance_days  breakpoint_hit_flag  window_hit_flag  cluster_hit_flag               event_hit_type  policy_or_geo_score                     review_note          model_version
              geo_primary_2026_02_28 2026-02-28        Primary Geo-Energy Shock           PRIMARY              2026-02-25                         3                 True             True              True PRIMARY_GEO_ENERGY_SHOCK_HIT             6.843591  nearest breakpoint distance=3d regime_v1_gaussian_cpd
            geo_secondary_2026_03_12 2026-03-12 Secondary Geo-Energy Escalation         SECONDARY              2026-02-25                        15                False            False             False PRIMARY_GEO_ENERGY_SHOCK_HIT             6.843591 nearest breakpoint distance=15d regime_v1_gaussian_cpd
geo_persistent_2026_03_23_2026_03_29 2026-03-23 Persistent Energy Crisis Window PERSISTENT_WINDOW              2026-02-25                        26                False            False             False PRIMARY_GEO_ENERGY_SHOCK_HIT             6.843591 nearest breakpoint distance=26d regime_v1_gaussian_cpd
```

## Artifacts

- `D:/FactorPlatform/data/exports/regime_engine/regime_snapshot_daily.parquet`
- `D:/FactorPlatform/data/exports/regime_engine/regime_breakpoints.parquet`
- `D:/FactorPlatform/data/exports/regime_engine/cluster_forecast_profile.parquet`
- `D:/FactorPlatform/data/exports/regime_engine/geo_energy_event_evaluation.parquet`