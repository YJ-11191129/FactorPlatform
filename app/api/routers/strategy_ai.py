from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import Actor, require_role
from app.api.schemas.strategy_ai import (
    ExplainBacktestIn,
    ExplainBacktestOut,
    GenerateStrategyIn,
    GenerateStrategyOut,
    LLMProviderStatusOut,
    RunAiBacktestIn,
    RunAiBacktestOut,
    StrategyValidationResult,
    ValidateStrategyIn,
)
from app.services.backtest_service import run_strategy_spec_backtest
from app.services.data_maintenance_service import evaluate_backtest_data_gate
from app.services.llm import llm_provider_status
from app.services.strategy_ai_service import explain_backtest, generate_strategy_spec
from app.services.strategy_validator import validate_strategy_spec


router = APIRouter(prefix="/api/v1/strategy-ai", tags=["strategy-ai"])


@router.get(
    "/providers",
    response_model=LLMProviderStatusOut,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def provider_status_api() -> LLMProviderStatusOut:
    return LLMProviderStatusOut(**llm_provider_status())


@router.post(
    "/generate",
    response_model=GenerateStrategyOut,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def generate_strategy_api(payload: GenerateStrategyIn) -> GenerateStrategyOut:
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    return generate_strategy_spec(payload)


@router.post(
    "/validate",
    response_model=StrategyValidationResult,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def validate_strategy_api(payload: ValidateStrategyIn) -> StrategyValidationResult:
    return validate_strategy_spec(payload.spec)


@router.post(
    "/backtest",
    response_model=RunAiBacktestOut,
    dependencies=[Depends(require_role("operator", "admin"))],
)
def run_ai_backtest_api(payload: RunAiBacktestIn, actor: Actor = Depends(require_role("operator", "admin"))) -> RunAiBacktestOut:
    try:
        validation = validate_strategy_spec(payload.spec)
        if payload.run_validation and not validation.is_valid:
            raise HTTPException(
                status_code=422,
                detail={"message": "strategy spec validation failed", "validation": validation.model_dump()},
            )

        data_gate = evaluate_backtest_data_gate(requested_end_date=payload.end_date)
        if data_gate.get("blocking_status") == "BLOCKED":
            raise HTTPException(status_code=409, detail=data_gate.get("message") or "data freshness gate blocked backtest")

        artifact, summary = run_strategy_spec_backtest(
            spec=validation.normalized_spec.model_dump(),
            start_date=payload.start_date,
            end_date=payload.end_date,
            universe=payload.universe,
            initial_cash=payload.initial_cash,
            fee_bps=payload.fee_bps,
            use_adj=payload.use_adj,
        )
        summary["data_health"] = data_gate
        summary["created_by_actor"] = actor.key_id
        return RunAiBacktestOut(
            backtest_id=artifact.backtest_id,
            created_at=artifact.created_at,
            summary=summary,
            validation=validation,
            data_health=data_gate,
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/explain",
    response_model=ExplainBacktestOut,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
def explain_backtest_api(payload: ExplainBacktestIn) -> ExplainBacktestOut:
    return explain_backtest(payload)
