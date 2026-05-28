from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.dependencies.auth import require_role
from app.services.artifact_service import display_storage_path, get_artifact, list_artifacts


router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def list_artifacts_api(run_id: str | None = None, artifact_type: str | None = None, limit: int = 100) -> dict:
    items = list_artifacts(run_id=run_id, artifact_type=artifact_type, limit=limit)
    return {
        "items": [
            {
                **item,
                "display_path": display_storage_path(item.get("storage_path")),
                "storage_path": None,
            }
            for item in items
        ]
    }


@router.get("/{artifact_id}", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_artifact_api(artifact_id: str) -> dict:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {
        "artifact_id": artifact.artifact_id,
        "run_id": artifact.run_id,
        "artifact_type": artifact.artifact_type,
        "file_type": artifact.file_type,
        "display_path": display_storage_path(artifact.storage_path),
        "download_path": artifact.download_path,
        "size_bytes": artifact.size_bytes,
        "checksum_sha256": artifact.checksum_sha256,
        "meta": artifact.meta,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
    }


@router.get("/{artifact_id}/download")
def download_artifact_api(artifact_id: str, actor=Depends(require_role("viewer", "operator", "admin"))):
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    path = Path(artifact.storage_path)
    if path.is_dir():
        raise HTTPException(status_code=400, detail="artifact is a directory and cannot be downloaded directly")
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact file not found")
    media_type = "application/octet-stream"
    if artifact.file_type == "html":
        media_type = "text/html"
    elif artifact.file_type == "pdf":
        media_type = "application/pdf"
    elif artifact.file_type == "json":
        media_type = "application/json"
    return FileResponse(str(path), media_type=media_type, filename=path.name)
