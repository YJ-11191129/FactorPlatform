from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import require_role
from app.api.schemas.backtests import BacktestDataStatusOut, BacktestSummaryOut, RunBacktestIn, RunBacktestOut, StrategyInfoOut
from app.services.backtest_service import backtest_data_status, list_backtests, read_equity_curve, run_backtest, run_portfolio_backtest
from app.services.data_maintenance_service import evaluate_backtest_data_gate
from app.services.native_qlib_research_service import get_portfolio, qlib_status
from app.services.strategy_service import list_strategy_infos


router = APIRouter(prefix="/api", tags=["backtests"])


@router.get(
    "/strategies",
    response_model=list[StrategyInfoOut],
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def list_strategies_api() -> list[StrategyInfoOut]:
    return [StrategyInfoOut(**x) for x in list_strategy_infos()]


@router.get(
    "/backtests/data-status",
    response_model=BacktestDataStatusOut,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def backtest_data_status_api() -> BacktestDataStatusOut:
    out = backtest_data_status()
    out["data_health"] = evaluate_backtest_data_gate()
    return BacktestDataStatusOut(**out)


@router.post(
    "/backtests/run",
    response_model=RunBacktestOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def run_backtest_api(payload: RunBacktestIn) -> RunBacktestOut:
    try:
        data_gate = evaluate_backtest_data_gate(requested_end_date=payload.end_date)
        if data_gate.get("blocking_status") == "BLOCKED":
            raise HTTPException(status_code=409, detail=data_gate.get("message") or "data freshness gate blocked backtest")
        if payload.portfolio_id:
            portfolio = get_portfolio(payload.portfolio_id)
            readiness = qlib_status(
                provider_uri=portfolio.get("provider_uri"),
                universe=portfolio.get("universe") or "csi300",
            )
            if readiness.get("status") != "READY":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "status": readiness.get("status"),
                        "message": "native qlib readiness gate blocked portfolio backtest",
                        "readiness": readiness,
                    },
                )
            artifact, summary = run_portfolio_backtest(
                portfolio_id=payload.portfolio_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                universe=payload.universe,
                initial_cash=payload.initial_cash,
                fee_bps=payload.fee_bps,
                use_adj=payload.use_adj,
            )
        else:
            if not payload.strategy_id:
                raise HTTPException(status_code=422, detail="strategy_id is required when portfolio_id is not provided")
            artifact, summary = run_backtest(
                strategy_id=payload.strategy_id,
                params=payload.params,
                start_date=payload.start_date,
                end_date=payload.end_date,
                universe=payload.universe,
                initial_cash=payload.initial_cash,
                fee_bps=payload.fee_bps,
                use_adj=payload.use_adj,
            )
        summary["data_health"] = data_gate
        return RunBacktestOut(backtest_id=artifact.backtest_id, created_at=artifact.created_at, summary=summary, data_health=data_gate)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/backtests",
    response_model=list[BacktestSummaryOut],
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def list_backtests_api(limit: int = 50) -> list[BacktestSummaryOut]:
    return [BacktestSummaryOut(**x) for x in list_backtests(limit=limit)]


@router.get(
    "/backtests/{backtest_id}/equity",
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def get_backtest_equity_api(backtest_id: str) -> dict:
    df = read_equity_curve(backtest_id)
    return {"items": df.head(5000).to_dict(orient="records"), "row_count": int(df.shape[0])}
