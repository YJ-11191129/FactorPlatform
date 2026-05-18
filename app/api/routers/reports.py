from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.dependencies.auth import Actor, require_role
from app.db.session import db_session
from app.models.report_artifact import ReportArtifact
from app.services.report_service import generate_qlib_factor_mining_report, generate_qlib_portfolio_backtest_report


router = APIRouter(prefix="/api/reports", tags=["reports"])


class GenerateReportIn(BaseModel):
    report_type: str
    run_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    backtest_id: Optional[str] = None
    enable_pdf: bool = False


@router.post("/generate")
def generate_report(payload: GenerateReportIn, actor: Actor = Depends(require_role("operator", "admin"))) -> dict:
    try:
        if payload.report_type == "qlib_factor_mining":
            if not payload.run_id:
                raise HTTPException(status_code=422, detail="run_id is required for qlib_factor_mining")
            return generate_qlib_factor_mining_report(payload.run_id, enable_pdf=payload.enable_pdf)
        if payload.report_type == "qlib_portfolio_backtest":
            if not payload.portfolio_id:
                raise HTTPException(status_code=422, detail="portfolio_id is required for qlib_portfolio_backtest")
            return generate_qlib_portfolio_backtest_report(
                payload.portfolio_id,
                backtest_id=payload.backtest_id,
                enable_pdf=payload.enable_pdf,
            )
        raise HTTPException(status_code=400, detail="unsupported report_type")
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def list_reports(limit: int = 50, actor: Actor = Depends(require_role("viewer", "operator", "admin"))) -> dict:
    try:
        from sqlalchemy import select

        with db_session() as db:
            rows = list(
                db.scalars(
                    select(ReportArtifact)
                    .order_by(ReportArtifact.created_at.desc())
                    .limit(max(1, int(limit)))
                ).all()
            )
        return {
            "items": [
                {
                    "report_id": r.report_id,
                    "report_type": r.report_type,
                    "analysis_id": r.analysis_id,
                    "status": r.status,
                    "meta": r.meta,
                    "html_path": r.html_path,
                    "pdf_path": r.pdf_path,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{report_id}")
def get_report(report_id: str, actor: Actor = Depends(require_role("viewer", "operator", "admin"))) -> dict:
    try:
        with db_session() as db:
            r = db.get(ReportArtifact, report_id)
        if r is None:
            raise HTTPException(status_code=404, detail="report not found")
        return {
            "report_id": r.report_id,
            "report_type": r.report_type,
            "analysis_id": r.analysis_id,
            "status": r.status,
            "meta": r.meta,
            "html_path": r.html_path,
            "pdf_path": r.pdf_path,
            "created_at": r.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{report_id}/download")
def download_report(
    report_id: str,
    fmt: str = "html",
    actor: Actor = Depends(require_role("viewer", "operator", "admin")),
):
    try:
        with db_session() as db:
            r = db.get(ReportArtifact, report_id)
        if r is None:
            raise HTTPException(status_code=404, detail="report not found")
        if fmt == "pdf":
            if not r.pdf_path:
                raise HTTPException(status_code=404, detail="pdf not available")
            p = Path(r.pdf_path)
            if not p.exists():
                raise HTTPException(status_code=404, detail="file not found")
            return FileResponse(str(p), media_type="application/pdf", filename=f"{report_id}.pdf")
        p = Path(r.html_path)
        if not p.exists():
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(str(p), media_type="text/html", filename=f"{report_id}.html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
