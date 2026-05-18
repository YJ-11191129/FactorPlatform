from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import require_role
from app.api.schemas.qlib_research import (
    BuildPortfolioIn,
    FactorMiningRunOut,
    PortfolioOut,
    QlibStatusOut,
    RunFactorMiningIn,
)
from app.services.native_qlib_research_service import (
    QlibResearchError,
    build_portfolio,
    get_factor_mining_run,
    get_portfolio,
    list_factor_mining_runs,
    list_portfolios,
    qlib_status,
    run_factor_mining,
)


router = APIRouter(prefix="/api/qlib", tags=["qlib-research"])


def _research_error(e: QlibResearchError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"status": e.status, "message": e.message, "readiness": e.readiness},
    )


@router.get(
    "/status",
    response_model=QlibStatusOut,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def qlib_status_api(provider_uri: str | None = None, universe: str = "csi300", freq: str = "day") -> QlibStatusOut:
    return QlibStatusOut(**qlib_status(provider_uri=provider_uri, universe=universe, freq=freq))


@router.post(
    "/factor-mining/run",
    response_model=FactorMiningRunOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def run_factor_mining_api(payload: RunFactorMiningIn) -> FactorMiningRunOut:
    try:
        out = run_factor_mining(
            factor_pool=payload.factor_pool,
            provider_uri=payload.provider_uri,
            universe=payload.universe,
            start_date=payload.start_date,
            end_date=payload.end_date,
            horizon=payload.horizon,
            quantiles=payload.quantiles,
            top_k=payload.top_k,
            freq=payload.freq,
            factor_limit=payload.factor_limit,
        )
        return FactorMiningRunOut(**out)
    except QlibResearchError as e:
        try:
            from app.services.research_ops_registry import register_qlib_blocked_event

            register_qlib_blocked_event(
                request=payload.model_dump(mode="json"),
                readiness=e.readiness,
                status=e.status,
                message=e.message,
            )
        except Exception:
            pass
        raise _research_error(e)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/factor-mining/runs",
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def list_factor_mining_runs_api(limit: int = 50) -> dict:
    return {"items": list_factor_mining_runs(limit=limit)}


@router.get(
    "/factor-mining/runs/{run_id}",
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def get_factor_mining_run_api(run_id: str) -> dict:
    try:
        return get_factor_mining_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="factor mining run not found")


@router.post(
    "/portfolios/build",
    response_model=PortfolioOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def build_portfolio_api(payload: BuildPortfolioIn) -> PortfolioOut:
    try:
        return PortfolioOut(
            **build_portfolio(
                mining_run_id=payload.mining_run_id,
                selected_factors=payload.selected_factors,
                weighting_method=payload.weighting_method,
                top_n=payload.top_n,
                long_top_n=payload.long_top_n,
            )
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="factor mining run not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/portfolios",
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def list_portfolios_api(limit: int = 50) -> dict:
    return {"items": list_portfolios(limit=limit)}


@router.get(
    "/portfolios/{portfolio_id}",
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def get_portfolio_api(portfolio_id: str) -> dict:
    try:
        return get_portfolio(portfolio_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="portfolio not found")
