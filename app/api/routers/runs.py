from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.run_store import get_run_meta, get_run_parquet_path


router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("/{calc_batch_id}/meta")
def run_meta(calc_batch_id: str) -> dict:
    try:
        return get_run_meta(calc_batch_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{calc_batch_id}/download")
def download(calc_batch_id: str) -> FileResponse:
    try:
        path = get_run_parquet_path(calc_batch_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")

    filename = f"{calc_batch_id}.parquet"
    return FileResponse(path=str(path), filename=filename, media_type="application/octet-stream")

