# REGIME_MARKET_STATE_EXTENSION_REPLY

## 1. ????

- ??????`risk_regime`??? `regime_label`?
- ??????`market_state`
- ??????`event_context`
- ??????`trend_strength`
- ??????`policy_regime_flag`, `bull_phase_flag`, `direction_score`, `trend_score`
- ????? API?`GET /api/v1/regime/events`

## 2. ??????

- rows_snapshot=1951
- rows_breakpoints=91
- hit_counts={'total_hit': 12, 'primary_shock_hit': 4, 'primary_policy_hit': 0, 'secondary_transition_hit': 8}
- latest=2026-03-25 / risk_regime=FRAGILE_HIGH_VOL / market_state=RANGE_BOUND / event_context=NONE / trend_strength=WEAK / market_risk_level=EXTREME

## 3. ???????review ???

- 2024-09-24: {'regime_label': 'FRAGILE_HIGH_VOL', 'risk_regime': 'FRAGILE_HIGH_VOL', 'market_state': 'POLICY_RISK_ON', 'event_context': 'PRIMARY_POLICY_REGIME_WINDOW', 'trend_strength': 'STRONG', 'market_risk_level': 'HIGH'}
- 2024-10-09: {'regime_label': 'LIQUIDITY_SHOCK', 'risk_regime': 'LIQUIDITY_SHOCK', 'market_state': 'RANGE_BOUND', 'event_context': 'PRIMARY_SHOCK_HIT', 'trend_strength': 'EXTREME', 'market_risk_level': 'EXTREME'}
- 2024-11-06: {'regime_label': 'TRANSITION', 'risk_regime': 'TRANSITION', 'market_state': 'RANGE_BOUND', 'event_context': 'SECONDARY_TRANSITION_HIT', 'trend_strength': 'EXTREME', 'market_risk_level': 'EXTREME'}

## 4. ???

- {'primary_shocks': ['2020-02-03', '2022-04-25', '2024-10-09', '2025-04-07'], 'secondary_transitions': ['2020-03-02', '2020-07-16', '2022-05-26', '2024-02-05', '2024-03-12', '2024-05-17', '2024-11-06', '2025-05-08'], 'primary_policy_dates': ['2024-09-24']}

## 5. ?????

- `app/services/regime_engine.py`
- `app/api/routers/signal_center.py`
- `data/exports/regime_engine/regime_market_state_extension_summary.json`