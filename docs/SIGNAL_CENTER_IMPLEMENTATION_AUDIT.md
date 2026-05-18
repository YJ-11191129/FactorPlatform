# Signal Center Implementation Audit

Updated: 2026-05-10

## Current Conclusion

Signal Center now has a real file-backed daily signal loop instead of a mock/demo-only shell.

- Live signals are generated from data freshness gate + Stock Radar + Regime/Router.
- Router-blocked Stock Radar candidates are also materialized as `shadow_items` for research validation.
- Latest snapshot is materialized to `data/exports/signal_center/latest_signals.json`.
- Signal outcomes are materialized to `data/exports/signal_center/latest_outcomes.json`.
- Performance endpoints read `data_source: "signal_outcomes"`.
- Performance and outcome endpoints support `execution_mode=live|shadow|all`; live remains the default.
- Mock fallback is disabled by default; demo mode requires `NEXT_PUBLIC_ALLOW_MOCK_FALLBACK=1`.

## Latest Real Snapshot

- Provider: `D:\mcQlib\data\qlib_bin\cn_data`
- Universe: `csi300`
- Data health: `OK`
- Signal date: `2026-05-08`
- Source run id: `signal_20260510_064555_e83dbb`
- Generated signals: `30`
- Blocked signals: `30`

The current Regime/Router maps the latest regime to observe-only risk control:

- Regime: `FRAGILE_HIGH_VOL`
- Router profile: `liquidity_shock_observe_only_profile`
- Risk scale: `0.0`
- Enabled template: `OBSERVE_ONLY_CRISIS_V1`

So the current snapshot is a real set of Stock Radar candidates, but every candidate is blocked as `NO_TRADE`. This is a risk decision, not mock data and not an empty pipeline.

The double-track blocked implementation adds the missing explanation and downstream validation path:

- Live `items` stay compatible and keep `side=NEUTRAL`, `entry_type=NO_TRADE`, and `status=BLOCKED` when Router risk scale is zero.
- Shadow `shadow_items` preserve the same real candidates as proposed long paper signals with `execution_mode=shadow` and `not_executable=true`.
- Snapshot metadata now includes `router_decision`, `regime_freshness`, and `counts`.
- `REGIME_STALE_BLOCKED` is emitted when Regime date lags Signal date by more than one trading day; live remains blocked, shadow remains inspectable.

## Outcome And Performance

Latest outcome refresh:

- Source run id: `signal_20260510_064555_e83dbb`
- Outcome count: `30`
- Status counts: `NO_TRADE=30`

Performance summary:

- `data_source`: `signal_outcomes`
- `total_signals`: `30`
- `evaluated_signals`: `0`
- `pending_signals`: `0`
- `no_trade_signals`: `30`

`NO_TRADE` signals are excluded from evaluated PnL and are no longer counted as pending outcome.

Shadow outcomes use separate statuses:

- `SHADOW_PENDING`: daily bars do not yet cover the paper evaluation window.
- `SHADOW_EVALUATED`: a paper outcome was computed from daily OHLCV.

Shadow metrics are available through `execution_mode=shadow` and are never mixed into live performance.

## Public Interfaces

- `GET /api/v1/signals/live`
- `GET /api/v1/signals/shadow`
- `POST /api/v1/signals/refresh`
- `GET /api/v1/signals/by-id/{signal_id}?execution_mode=live|shadow`
- `GET /api/v1/signals/snapshots`
- `GET /api/v1/signals/outcomes?execution_mode=live|shadow|all`
- `GET /api/v1/signals/outcomes/{signal_id}?execution_mode=live|shadow|all`
- `POST /api/v1/signals/outcomes/refresh`
- `GET /api/v1/signals/performance/summary?execution_mode=live|shadow|all`
- `GET /api/v1/signals/performance/timeseries?execution_mode=live|shadow|all`
- `GET /api/v1/signals/performance/attribution?execution_mode=live|shadow|all`

## Frontend State

- Signal Center displays snapshot metadata, data health, and source run id.
- Signal Center has a `Live / Shadow Candidates` switch.
- Live blocked state displays Regime date, Signal date, risk scale, and block reason.
- Shadow rows are explicitly marked `Not executable`.
- Signal detail no longer shows fake replay/subscribe/export success actions.
- Signal detail price chart only uses real outcome `price_path`.
- Signal detail can load shadow detail via `execution_mode=shadow`.
- Performance page has a `Live / Shadow` switch and marks shadow as research-only.
- Header displays API status, production/demo mode, and latest Signal snapshot state.
- Dashboard and Scoring no longer silently fall back to mock data.

## Validation

Latest validation results after implementation:

- `python -m pytest tests\unit -q`: `36 passed`
- `node node_modules\next\dist\bin\next build`: passed
- `python scripts\run_e2e_validation.py`: script updated for shadow checks; runtime checks require backend/frontend servers.
- Real snapshot regeneration was blocked in the current Codex sandbox by `D:\mcQlib` read permissions. Run `/api/v1/signals/refresh` or `python scripts\run_daily_data_maintenance.py` from a process with qlib access to materialize new `shadow_items`.

Runtime URLs used for the successful validation:

- Backend: `http://127.0.0.1:8003`
- Frontend: `http://127.0.0.1:3001`

Ports `8002` and `3000` are currently held by `svchost` on this machine and reset HTTP requests, so the validation scripts now support alternate ports.

## Remaining Non-Data Gaps

- Shock replay remains a future real event-window replay engine.
- External notifications are not sent yet; current logs are system snapshot logs.
- Outcome v1 is daily-bar based and does not model intraday fills, slippage, fees, or matching.
- File-backed artifacts are suitable for the local workflow but not yet a multi-user concurrent production store.
