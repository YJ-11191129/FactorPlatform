from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas.factors import (
    ComputeStoreFactorIn,
    ComputeStoreFactorOut,
    FactorInfoOut,
    FactorValuesQueryOut,
    RunDemoFactorIn,
    RunFactorOut,
    RunQlibFactorIn,
    RunStockScreenIn,
    RunStockScreenOut,
    RunStockRadarIn,
    RunStockRadarOut,
)
from app.api.dependencies.auth import require_role
from app.db.session import db_session
from app.models.factor_run import FactorRun
from app.services.factor_metadata_service import sync_code_factor_metadata
from app.services.factor_service import factor_info_dict, get_factor_info, list_factor_infos, run_demo_factor, run_qlib_factor
from app.services.factor_library_master_service import (
    compute_and_store_factor_values,
    list_factor_registry,
    list_strategy_registry,
    read_factor_values,
    read_screened_universe_latest,
    run_stock_screen,
)
from app.services.run_store import list_runs, save_run
from app.services.stock_radar_service import run_stock_radar
from app.services.data_maintenance_service import evaluate_stock_radar_data_gate


router = APIRouter(prefix="/api", tags=["factors"])


@router.get(
    "/factors",
    response_model=list[FactorInfoOut],
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def list_factors_api() -> list[FactorInfoOut]:
    return [FactorInfoOut(**factor_info_dict(fi)) for fi in list_factor_infos()]


@router.get(
    "/factors/{factor_name}",
    response_model=FactorInfoOut,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def get_factor_api(factor_name: str) -> FactorInfoOut:
    try:
        fi = get_factor_info(factor_name)
        return FactorInfoOut(**factor_info_dict(fi))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/factors/run-demo",
    response_model=RunFactorOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def run_demo_factor_api(payload: RunDemoFactorIn) -> RunFactorOut:
    try:
        df = run_demo_factor(payload.factor_name, payload.params)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    artifact = None
    if payload.save:
        try:
            artifact = save_run(
                factor_name=payload.factor_name,
                mode="demo",
                df=df,
                params=payload.params,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    preview = df.head(200).to_dict(orient="records")
    return RunFactorOut(
        factor_name=payload.factor_name,
        row_count=int(df.shape[0]),
        preview=preview,
        columns=list(df.columns),
        message="demo 数据源：内置 synthetic daily_bar，仅用于验证流程",
        calc_batch_id=(artifact.calc_batch_id if artifact else None),
        download_url=(f"/api/runs/{artifact.calc_batch_id}/download" if artifact else None),
    )


@router.post(
    "/factors/run-qlib",
    response_model=RunFactorOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def run_qlib_factor_api(payload: RunQlibFactorIn) -> RunFactorOut:
    try:
        df = run_qlib_factor(
            factor_name=payload.factor_name,
            params=payload.params,
            provider_uri=payload.provider_uri,
            universe=payload.universe,
            start_date=payload.start_date,
            end_date=payload.end_date,
            instrument_limit=payload.instrument_limit,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    artifact = None
    if payload.save:
        try:
            artifact = save_run(
                factor_name=payload.factor_name,
                mode="qlib_bin",
                df=df,
                params=payload.params,
                universe=payload.universe,
                provider_uri=payload.provider_uri,
                start_date=(payload.start_date.isoformat() if payload.start_date else None),
                end_date=(payload.end_date.isoformat() if payload.end_date else None),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    preview = df.head(200).to_dict(orient="records")
    return RunFactorOut(
        factor_name=payload.factor_name,
        row_count=int(df.shape[0]),
        preview=preview,
        columns=list(df.columns),
        message="数据源：本地 qlib_bin（ohlc/volume/factor）",
        calc_batch_id=(artifact.calc_batch_id if artifact else None),
        download_url=(f"/api/runs/{artifact.calc_batch_id}/download" if artifact else None),
    )


@router.get("/runs", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def list_runs_api(limit: int = 50) -> list[dict]:
    return list_runs(limit=limit)


@router.get("/factor-library/registry", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_factor_library_registry() -> dict[str, Any]:
    df = list_factor_registry()
    return {"items": df.to_dict(orient="records")}


@router.post("/factor-library/registry/sync", dependencies=[Depends(require_role("admin"))])
def sync_factor_library_registry() -> dict[str, Any]:
    try:
        with db_session() as db:
            return sync_code_factor_metadata(db)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/factor-library/strategies", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_strategy_library_registry() -> dict[str, Any]:
    df = list_strategy_registry()
    return {"items": df.to_dict(orient="records")}


@router.post(
    "/factor-library/compute-store",
    response_model=ComputeStoreFactorOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def compute_store_factor_api(payload: ComputeStoreFactorIn) -> ComputeStoreFactorOut:
    try:
        out = compute_and_store_factor_values(
            factor_name=payload.factor_name,
            params=payload.params,
            universe_name=payload.universe_name,
            factor_version=payload.factor_version,
            start_date=payload.start_date,
            end_date=payload.end_date,
            instrument_limit=payload.instrument_limit,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ComputeStoreFactorOut(**out)


@router.get(
    "/factor-library/values",
    response_model=FactorValuesQueryOut,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def list_factor_values_api(
    factor_name: str | None = None,
    trade_date: str | None = None,
    limit: int = 200,
) -> FactorValuesQueryOut:
    df = read_factor_values(factor_name=factor_name, trade_date=trade_date, limit=limit)
    return FactorValuesQueryOut(items=df.to_dict(orient="records"))


@router.get("/factor-library/runs", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def list_factor_library_runs(limit: int = 50) -> dict[str, Any]:
    try:
        from sqlalchemy import select

        with db_session() as db:
            rows = list(
                db.scalars(
                    select(FactorRun).order_by(FactorRun.computed_at.desc()).limit(max(1, int(limit)))
                ).all()
            )
        return {
            "items": [
                {
                    "calc_batch_id": r.calc_batch_id,
                    "factor_name": r.factor_name,
                    "factor_version": r.factor_version,
                    "mode": r.mode,
                    "params": r.params,
                    "universe_name": r.universe_name,
                    "start_date": (r.start_date.isoformat() if r.start_date else None),
                    "end_date": (r.end_date.isoformat() if r.end_date else None),
                    "instrument_limit": r.instrument_limit,
                    "artifact_path": r.artifact_path,
                    "row_count": r.row_count,
                    "status": r.status,
                    "error": r.error,
                    "computed_at": r.computed_at.isoformat(),
                }
                for r in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get(
    "/factor-library/runs/{calc_batch_id}",
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def get_factor_library_run(calc_batch_id: str) -> dict[str, Any]:
    try:
        from sqlalchemy import select

        with db_session() as db:
            r = db.scalar(select(FactorRun).where(FactorRun.calc_batch_id == calc_batch_id))
        if r is None:
            raise HTTPException(status_code=404, detail="run not found")
        return {
            "calc_batch_id": r.calc_batch_id,
            "factor_name": r.factor_name,
            "factor_version": r.factor_version,
            "mode": r.mode,
            "params": r.params,
            "universe_name": r.universe_name,
            "start_date": (r.start_date.isoformat() if r.start_date else None),
            "end_date": (r.end_date.isoformat() if r.end_date else None),
            "instrument_limit": r.instrument_limit,
            "artifact_path": r.artifact_path,
            "row_count": r.row_count,
            "status": r.status,
            "error": r.error,
            "computed_at": r.computed_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post(
    "/factor-library/screen/run",
    response_model=RunStockScreenOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def run_stock_screen_api(payload: RunStockScreenIn) -> RunStockScreenOut:
    try:
        out = run_stock_screen(
            min_market_cap=payload.min_market_cap,
            max_market_cap=payload.max_market_cap,
            min_listed_days=payload.min_listed_days,
            exclude_st=payload.exclude_st,
            trade_status=payload.trade_status,
            min_roe_avg=payload.min_roe_avg,
            min_oper_rev_growth_ttm=payload.min_oper_rev_growth_ttm,
            min_net_profit_growth_ttm=payload.min_net_profit_growth_ttm,
            max_debt_to_asset=payload.max_debt_to_asset,
            topn=payload.topn,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RunStockScreenOut(**out)


@router.get("/factor-library/screen/latest", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_stock_screen_latest(limit: int = 200) -> dict[str, Any]:
    df = read_screened_universe_latest(limit=limit)
    return {"items": df.to_dict(orient="records")}


@router.post(
    "/factor-library/radar/run",
    response_model=RunStockRadarOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def run_stock_radar_api(payload: RunStockRadarIn) -> RunStockRadarOut:
    try:
        data_gate = evaluate_stock_radar_data_gate(
            payload.provider_uri,
            requested_end_date=payload.asof_date or payload.end_date,
        )
        if data_gate.get("blocking_status") == "BLOCKED":
            raise HTTPException(status_code=409, detail=data_gate.get("message") or "data freshness gate blocked Stock Radar")
        out = run_stock_radar(
            provider_uri=payload.provider_uri,
            universe=payload.universe,
            factors=[factor.model_dump() for factor in payload.factors],
            start_date=payload.start_date,
            end_date=payload.end_date,
            asof_date=payload.asof_date,
            instrument_limit=payload.instrument_limit,
            topn=payload.topn,
            min_score=payload.min_score,
            min_factor_count=payload.min_factor_count,
            winsorize_q=payload.winsorize_q,
        )
        out["data_health"] = data_gate
        if data_gate.get("blocking_status") == "WARN":
            out["timing_note"] = f"{out.get('timing_note', '')} Data freshness warning: {data_gate.get('message')}"
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RunStockRadarOut(**out)
