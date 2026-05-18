from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import Actor, require_role
from app.services.macro_intelligence_service import (
    MacroInputs,
    collect_holistic_context,
    generate_chain_of_impact,
    generate_topic_report,
    llm_ready,
)


router = APIRouter(prefix="/api/v1/macro", tags=["macro"])


@router.post("/chain-of-impact")
def chain_of_impact(payload: dict, actor: Actor = Depends(require_role("viewer", "operator", "admin"))) -> dict:
    try:
        inputs = MacroInputs(
            topic=str(payload.get("topic") or "").strip(),
            event=(str(payload.get("event")).strip() if payload.get("event") else None),
            region=(str(payload.get("region")).strip() if payload.get("region") else None),
            horizon=(str(payload.get("horizon")).strip() if payload.get("horizon") else None),
        )
        if not inputs.topic:
            raise HTTPException(status_code=400, detail="topic is required")
        context = collect_holistic_context(inputs)
        out = generate_chain_of_impact(inputs, context)
        return {"inputs": payload, "context": context, "result": out, "llm_ready": llm_ready()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/topic-report")
def topic_report(payload: dict, actor: Actor = Depends(require_role("viewer", "operator", "admin"))) -> dict:
    try:
        inputs = MacroInputs(
            topic=str(payload.get("topic") or "").strip(),
            event=(str(payload.get("event")).strip() if payload.get("event") else None),
            region=(str(payload.get("region")).strip() if payload.get("region") else None),
            horizon=(str(payload.get("horizon")).strip() if payload.get("horizon") else None),
        )
        if not inputs.topic:
            raise HTTPException(status_code=400, detail="topic is required")
        context = collect_holistic_context(inputs)
        out = generate_topic_report(inputs, context)
        return {"inputs": payload, "context": context, "result": out, "llm_ready": llm_ready()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
