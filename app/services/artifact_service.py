from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.settings import get_settings
from app.db.session import db_session
from app.models.artifact_registry import ArtifactRegistry


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifact_root() -> Path:
    raw = get_settings().artifact_root
    root = Path(raw)
    if not root.is_absolute():
        root = _project_root() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path_size(path: Path) -> int:
    if path.is_file():
        return int(path.stat().st_size)
    if path.is_dir():
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += int(item.stat().st_size)
                except OSError:
                    continue
        return total
    return 0


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_type(path: Path, explicit: str | None = None) -> str:
    if explicit:
        return explicit.strip().lstrip(".").lower() or "artifact"
    if path.is_dir():
        return "directory"
    suffix = path.suffix.strip(".").lower()
    return suffix or "artifact"


def _download_path(artifact_id: str) -> str:
    return f"/api/artifacts/{artifact_id}/download"


def register_artifact(
    path: str | Path,
    *,
    artifact_type: str,
    run_id: str | None = None,
    file_type: str | None = None,
    meta: dict[str, Any] | None = None,
    artifact_id: str | None = None,
) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = (_project_root() / p).resolve()
    checksum = _sha256_file(p) if p.exists() else None
    aid = artifact_id or (f"art_{checksum[:24]}" if checksum else f"art_{uuid4().hex[:24]}")
    record = ArtifactRegistry(
        artifact_id=aid,
        run_id=run_id,
        artifact_type=artifact_type,
        file_type=_file_type(p, file_type),
        storage_path=str(p),
        download_path=_download_path(aid),
        size_bytes=_path_size(p) if p.exists() else 0,
        checksum_sha256=checksum,
        meta=meta or {},
    )
    with db_session() as db:
        existing = db.get(ArtifactRegistry, aid)
        if existing is None:
            db.add(record)
        else:
            existing.run_id = run_id or existing.run_id
            existing.artifact_type = record.artifact_type
            existing.file_type = record.file_type
            existing.storage_path = record.storage_path
            existing.download_path = record.download_path
            existing.size_bytes = record.size_bytes
            existing.checksum_sha256 = record.checksum_sha256
            existing.meta = {**(existing.meta or {}), **(meta or {})}
    return artifact_dict(record)


def get_artifact(artifact_id: str) -> ArtifactRegistry | None:
    with db_session() as db:
        return db.scalar(select(ArtifactRegistry).where(ArtifactRegistry.artifact_id == artifact_id))


def list_artifacts(*, run_id: str | None = None, artifact_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with db_session() as db:
        stmt = select(ArtifactRegistry).order_by(ArtifactRegistry.created_at.desc()).limit(max(1, int(limit)))
        if run_id:
            stmt = stmt.where(ArtifactRegistry.run_id == run_id)
        if artifact_type:
            stmt = stmt.where(ArtifactRegistry.artifact_type == artifact_type)
        rows = list(db.scalars(stmt).all())
    return [artifact_dict(row) for row in rows]


def artifact_dict(row: ArtifactRegistry) -> dict[str, Any]:
    return {
        "artifact_id": row.artifact_id,
        "run_id": row.run_id,
        "artifact_type": row.artifact_type,
        "file_type": row.file_type,
        "storage_path": row.storage_path,
        "download_path": row.download_path,
        "size_bytes": row.size_bytes,
        "checksum_sha256": row.checksum_sha256,
        "meta": row.meta,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def display_storage_path(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    try:
        root = artifact_root().resolve()
        rel = p.resolve().relative_to(root)
        return os.path.join("artifacts", str(rel)).replace("\\", "/")
    except Exception:
        return p.name or str(path)
