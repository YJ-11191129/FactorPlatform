# FactorPlatform Project Plan And Gaps

Updated: 2026-05-10

## Current Position

FactorPlatform is now best described as a local-private **Quant ResearchOps / SignalOps platform**. The strongest implemented thread is no longer a single factor or backtest module; it is the operating chain around research evidence, data gates, signal generation, router decisions, shadow validation, outcomes, reports, and audit lineage.

Implemented foundations:

- Data Maintenance readiness gate with blocking status, source blockers, recommended updaters, and latest report artifacts.
- Stock Radar and Signal Center daily signal loop with live/shadow split, Regime/Router decision metadata, outcomes, and live/shadow performance modes.
- Native qlib research shell with readiness gate, factor mining artifacts, portfolio candidate build, and report generation hooks.
- Research Quality Guard v1 for factor mining artifacts: timing, coverage, RankIC stability, group return, and suspicious IC checks.
- ResearchOps file registry v1: data snapshots, factor runs, validation results, signal snapshots, router decisions, portfolio proposals, outcomes, reports, and external evidence.
- OpenBB information source v1 as a non-trading research evidence source for macro/news context.
- Frontend pages now expose Data Maintenance, Factors/Quality, Signal Center live/shadow, Performance live/shadow, Runs lineage, Dashboard daily brief, and Macro Intelligence source switching.

Latest verified engineering checks after OpenBB integration:

- `python -m pytest tests\unit -q`: `57 passed`
- `node node_modules\next\dist\bin\next build`: passed

Data freshness note:

- Data freshness itself is maintained separately by the Data Maintenance workflow.
- The repo-local latest maintenance artifact currently available to this document is `data/exports/data_maintenance/latest.json`, generated at `2026-05-10T06:41:45Z`.
- If data has been refreshed after that artifact, rerun `python scripts\run_daily_data_maintenance.py` or the API daily update to refresh the source-of-truth artifact before using this document for operational data status.

## Differentiation Thesis

This platform should not compete as another notebook, generic backtest framework, or hosted quant community. Its strongest market position is:

> A local-private Quant ResearchOps / SignalOps platform that turns qlib, Wind, OpenBB, and internal data into auditable daily investment signals.

The product should keep sharpening six differentiators:

- **Local private data trust:** qlib/Wind/internal sources are checked before use; stale or missing critical data blocks live use instead of producing plausible fake results.
- **Research-to-signal lineage:** every factor run, quality check, signal, router decision, outcome, report, and external evidence artifact can be traced.
- **Research Quality Guard:** timing, coverage, IC stability, group monotonicity, leakage risk, and promotion status are built into the workflow.
- **Explainable Router:** each signal can explain whether it was approved, scaled, blocked, or sent to shadow, with reason codes and evidence.
- **Shadow outcome loop:** blocked candidates are not discarded; they are tracked so the team can judge whether Router decisions were right.
- **PM-ready operations UI:** the user interface should answer daily operating questions, not just expose raw APIs or research tables.

## Major Workstreams And Gaps

| Workstream | Why it matters | Current state | Major gaps | Next milestone |
|---|---|---|---|---|
| OpenBB evidence layer | Adds external macro/news/company event evidence without polluting trading data gates | Adapter/API/UI switch exists; optional dependency returns `OPENBB_NOT_READY` | Runtime not installed; no E2E; report lineage not parented to exact evidence; Dashboard does not summarize evidence | Install/configure OpenBB, smoke `news.world/company/economy.calendar`, wire evidence into daily brief and reports |
| UI / product experience | Converts engineering artifacts into PM/research workflows | Pages exist for data, factors, signals, performance, runs, macro | Visual language is still uneven; some pages are table-heavy; PM cockpit is incomplete; lineage graph is basic; mode/status explanations need consistency | Figma-backed design pass for PM Daily Cockpit, Signal Board, Router Board, Factor Quality, and Lineage |
| Differentiation hardening | Makes the platform clearly different from qlib notebooks/backtest tools | Core concepts are implemented but scattered | Need stronger object model in UI: Data Snapshot, Factor Run, Validation Result, Router Decision, Shadow Book, Outcome, Report | Productize the four signal questions: source, usability evidence, router decision, post-result |
| Native qlib research loop | Makes factor mining/backtest/report path real rather than scaffold-only | API, artifacts, quality gate, portfolio builder exist | Native qlib package/provider readiness still blocks real run; one accepted end-to-end qlib research example is missing | One real csi300 factor mining -> quality -> portfolio -> backtest -> report lineage |
| ResearchOps registry | Provides the audit backbone | File-backed registry, rebuild index, lineage APIs, daily brief exist | External evidence not in daily brief; report parents incomplete; no lifecycle/approval objects; no visual graph | Evidence/report lineage closure and daily brief expansion |
| SignalOps / Router governance | Turns signals into governed production candidates | Live/shadow split, outcomes, performance modes exist | No promotion queue; no manual override log; no false-block/false-approve dashboard | Shadow review board with promotion/retire recommendations |
| Research Quality Guard | Explains why a factor/signal can be used | Timing/coverage/RankIC/group/suspicious IC checks exist | PIT financial/constituent/industry checks missing; no redundancy/capacity/cost/exposure checks | Add PIT readiness and factor redundancy/capacity checks |
| Portfolio and risk | Converts approved signals into PM-usable proposals | Basic portfolio candidate build and daily backtest hooks exist | No optimizer constraints, costs, risk model, exposure budget, turnover control, or execution assumptions UI | Long-only constrained daily portfolio proposal with transparent risk scaling |
| Production readiness | Lets a team operate the platform safely | API-key roles, file artifacts, tests/build pass | File store is not multi-user; auth lacks object-level audit; no task queue UI; no deployment profile for OpenBB/qlib | Local institution deployment profile with health checks and operational runbook |

## Current Product Gaps

### P0 - Operating Chain Gaps

- **OpenBB runtime is not installed in the current backend environment.** The integration is intentionally optional and returns `OPENBB_NOT_READY`; real OpenBB evidence requires installing `openbb`, running any needed `openbb-build`, and configuring provider credentials where needed.
- **OpenBB evidence is registered as `external_evidence`, but report lineage is not yet explicitly parented to the exact OpenBB evidence objects.** Macro context can include evidence artifacts, but report objects should expose those as first-class ResearchOps parents.
- **ResearchOps daily brief does not yet summarize external evidence.** It shows data health, signal snapshot, router/outcome, and reports, but not latest OpenBB evidence or evidence warnings.
- **Native qlib remains gated by package readiness.** The platform correctly returns `QLIB_NOT_READY` when native qlib is unavailable; true qlib factor mining/backtest acceptance still requires installing/configuring qlib in the runtime.
- **Portfolio build has quality promotion flags, but downstream backtest/strategy pages do not yet make `SHADOW_ONLY` and `not_executable` visually dominant enough.**
- **E2E script coverage has not yet been extended for OpenBB.** Unit tests cover OpenBB readiness and artifact registration, but the broader `scripts/run_e2e_validation.py` should include OpenBB status and non-fallback checks.
- **UI/UX is not yet differentiated enough.** The frontend exposes functions, but it does not yet feel like a polished PM/research operating cockpit with a consistent design system, visual hierarchy, and workflow-first navigation.
- **The product differentiation is not yet fully encoded in the UI.** Users can retrieve lineage and quality details, but the interface does not consistently force every signal to answer: where did it come from, why is it usable, why was it routed that way, and how did it perform.

### P1 - Research Quality And Governance Gaps

- Research Quality Guard v1 does not yet implement full PIT checks for financial statements, constituents, industry classification, or announcement availability.
- Factor lifecycle is still artifact-driven, not a governed workflow with `draft -> validated -> shadow -> production -> retired` transitions.
- Manual override/approval is not implemented. Router decisions are explainable, but PM override, reason capture, and outcome accountability are still future work.
- Signal promotion from shadow to production is not yet a workflow. Shadow outcomes are tracked, but there is no promotion queue, review gate, or approval artifact.
- Factor correlation/redundancy, capacity, cost coverage, exposure breach, and model drift checks are not yet formal Research Quality checks.

### P2 - Production Hardening Gaps

- File-backed artifacts are suitable for local/private workflow v1, but not yet a multi-user concurrent production store.
- Permission model is API-key based and role-aware, but lacks object-level authorization, approval trails, and user identity in all ResearchOps objects.
- Portfolio construction remains simple; advanced constraints, risk model integration, costs, slippage, turnover caps, and optimizer explainability remain future work.
- Outcome v1 is daily-bar based and does not model intraday fills, auction constraints, limit-up/down execution, slippage, or fees in detail.
- Shock replay is still a planned event-window replay engine.
- OpenBB is only macro/news/economic-calendar evidence in v1; it does not feed qlib provider updates or trading signal execution.
- The current UI is not yet backed by a formal design system, Figma component library, or screen-by-screen acceptance baseline.
- Differentiation messaging is mostly in documents, not yet reflected as product mechanics across Dashboard, Signal detail, Report Center, and Lineage.

## Next Project Plan

### Phase A - Evidence And Audit Closure

Goal: make every non-price research evidence artifact traceable in ResearchOps.

- Install/configure OpenBB in the backend runtime and run smoke checks for `news.world`, `news.company`, and `economy.calendar`.
- Add latest external evidence to ResearchOps daily brief and Dashboard.
- Parent Macro report artifacts to OpenBB `external_evidence` objects when evidence is used.
- Add OpenBB checks to `scripts/run_e2e_validation.py`: status endpoint, `OPENBB_NOT_READY` explainability, and no silent Google RSS fallback when `source=openbb`.
- Update stack health output with OpenBB mode: `READY | OPENBB_NOT_READY | WARN`.

Acceptance:

- OpenBB missing state is visible and non-blocking.
- OpenBB ready state can produce an artifact, a ResearchOps object, and a lineage edge into a report.
- E2E remains green whether OpenBB is installed or not.

### Phase B - UI And Differentiation Pass

Goal: make the product feel like a PM/research operating system rather than a collection of technical pages.

- Create a Figma-backed visual direction for core pages: PM Daily Cockpit, Signal Board, Router Board, Factor Quality, Lineage, Macro Intelligence.
- Standardize status language and tags: `READY`, `BLOCKED`, `NO_TRADE`, `SHADOW_ONLY`, `OPENBB_NOT_READY`, `QLIB_NOT_READY`, `PENDING_OUTCOME`.
- Rework Dashboard into a daily operating cockpit with data readiness, signal snapshot, router summary, shadow candidates, outcomes, reports, and evidence.
- Rework Signal detail around the four differentiating questions: source, quality evidence, router decision, outcome.
- Improve Runs/Lineage from table-only to a compact graph/timeline view.

Acceptance:

- A PM can open the Dashboard and understand today's decision state in under one minute.
- A researcher can open a factor run and see quality, promotion status, lineage, and next action without reading raw artifacts.
- No page silently shows mock/demo data unless demo mode is explicitly enabled.

### Phase C - Native qlib Research Acceptance

Goal: complete one real qlib factor mining -> quality -> portfolio -> backtest -> report loop.

- Install/configure native qlib in the runtime or document the exact environment profile required.
- Run a small `csi300` factor mining job with a bounded factor pool and date range.
- Evaluate Research Quality automatically and require portfolio candidates to inherit quality promotion flags.
- Build one portfolio candidate from passing/warning factors and run daily portfolio backtest.
- Generate an HTML qlib factor/portfolio report and register the lineage.

Acceptance:

- A single `run_id` can trace to data snapshot, factor run, validation result, quality report, portfolio proposal, backtest result, and report artifact.
- `FAIL` factors remain `SHADOW_ONLY`; they cannot be presented as production-ready.

### Phase D - PM Daily Cockpit And SignalOps Review

Goal: turn daily signals, Router decisions, and shadow outcomes into a repeatable review process.

- Show data readiness, latest signal snapshot, router risk scale, live/shadow counts, latest outcomes, latest reports, and latest external evidence in one compact board.
- Add clear `NO_TRADE`, `SHADOW_PENDING`, `SHADOW_EVALUATED`, `OPENBB_NOT_READY`, and `QLIB_NOT_READY` explanations.
- Add links from each daily brief card into lineage detail.
- Add Shadow Review Board: reason-code performance, false blocks, false approvals, promotion candidates, retire candidates.

Acceptance:

- PM can answer: what data is ready, what signals exist, what was blocked, what is shadow-only, what evidence was used, and where the report is.
- Research lead can answer: which blocked signals deserved a second look and which Router rules are working.

### Phase E - Governance Workflow

Goal: convert artifact status into managed lifecycle decisions.

- Add factor/signal promotion states and review artifacts.
- Add manual override records with user, timestamp, reason, before/after decision, and outcome tracking.
- Add Router false-block / false-approve summaries based on shadow/live outcomes.
- Add quality trend view per factor and per reason code.

Acceptance:

- Any production or shadow signal has a lifecycle state, reason codes, upstream evidence, and outcome history.

### Phase F - Portfolio/Risk Production Path

Goal: turn approved/scaled signals into explainable portfolio proposals.

- Add a long-only constrained portfolio builder with position caps, industry exposure caps, turnover limit, and cost assumptions.
- Show risk scaling decomposition: signal quality, regime confidence, volatility, drawdown, liquidity, and final scale.
- Add portfolio proposal report with weights, changes vs previous proposal, exposures, expected turnover, and blocked instruments.
- Keep execution research-only until daily OHLCV outcome and cost assumptions are accepted.

Acceptance:

- A portfolio proposal can explain why each position exists, what risk constraints shaped it, and which signals were excluded.

## Operating Defaults

- qlib/Wind remain the trading data source of truth.
- OpenBB remains a research evidence source and is non-blocking for live signal execution.
- Data freshness should be read from the latest Data Maintenance artifact, not from static documentation.
- Research Quality failures do not delete research artifacts; they force `SHADOW_ONLY` / `not_executable`.
- Live Router risk controls remain strict; blocked candidates continue through shadow validation only.
