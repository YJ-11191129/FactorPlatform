# E2E Validation Report

- Generated At: 2026-05-10T15:25:00+08:00
- Backend URL: `http://127.0.0.1:8003`
- Frontend URL: `http://127.0.0.1:3001`
- Status: partial in current Codex sandbox

## Passed

- `python -m pytest tests\unit -q`: `36 passed`
- `node node_modules\next\dist\bin\next build`: passed
- TestClient API checks for health, live snapshot read, snapshot history, live performance, shadow performance endpoint shape, outcome refresh dry-run, and production mock fallback policy are implemented in `scripts/run_e2e_validation.py`.

## Not Completed In Sandbox

- Real snapshot regeneration could not read `D:\mcQlib\data\qlib_bin\cn_data` from the current sandbox (`PermissionError: [WinError 5]`).
- The existing `latest_signals.json` was generated before shadow support, so it has no `shadow_items`, `counts`, or `regime_freshness`.
- Runtime backend checks require a running `uvicorn` process; frontend dev server was reachable on `3001`, but backend startup did not remain alive in this sandbox session.

## Required Acceptance Rerun

Run from a process with qlib read access:

```powershell
cd D:\FactorPlatform
python -m uvicorn app.api.app:app --host 127.0.0.1 --port 8003
```

In another shell:

```powershell
cd D:\FactorPlatform\web
$env:BACKEND_ORIGIN = "http://127.0.0.1:8003"
npm run dev -- --hostname 127.0.0.1 --port 3001
```

Then refresh and validate:

```powershell
Invoke-RestMethod "http://127.0.0.1:8003/api/v1/signals/refresh" -Method Post -ContentType "application/json" -Body '{"topn":30}'
Invoke-RestMethod "http://127.0.0.1:8003/api/v1/signals/outcomes/refresh" -Method Post -ContentType "application/json" -Body '{"horizon_days":10}'
$env:FACTOR_PLATFORM_E2E_BACKEND_URL = "http://127.0.0.1:8003"
$env:FACTOR_PLATFORM_E2E_FRONTEND_URL = "http://127.0.0.1:3001"
python scripts\run_e2e_validation.py
```
