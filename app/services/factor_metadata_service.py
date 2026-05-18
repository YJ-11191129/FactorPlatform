from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.factors.registry import ensure_registered, get_factor
from app.models.factor_metadata import FactorMetadata
from app.services.factor_service import DEFAULT_FACTOR_MODULES, list_factor_infos


def make_factor_key(factor_name: str, version: str) -> str:
    return f"{factor_name}::{version}".lower()


def sync_code_factor_metadata(db: Session) -> dict[str, Any]:
    ensure_registered(DEFAULT_FACTOR_MODULES)
    infos = list_factor_infos()
    upserted = 0
    ts = datetime.now(tz=timezone.utc)

    for fi in infos:
        rf = get_factor(fi.factor_name)
        py_entry = f"{rf.factor_cls.__module__}:{rf.factor_cls.__name__}"
        key = make_factor_key(fi.factor_name, fi.version)

        existing = db.scalar(select(FactorMetadata).where(FactorMetadata.factor_key == key))
        if existing is None:
            db.add(
                FactorMetadata(
                    factor_key=key,
                    factor_name=fi.factor_name,
                    version=fi.version,
                    category=fi.category,
                    display_name=fi.display_name,
                    description=fi.description,
                    python_entry=py_entry,
                    dependencies=list(fi.dependencies),
                    parameter_schema=dict(fi.parameter_schema),
                    status="ACTIVE",
                    owner="research",
                    created_at=ts,
                    updated_at=ts,
                )
            )
            upserted += 1
        else:
            existing.factor_name = fi.factor_name
            existing.version = fi.version
            existing.category = fi.category
            existing.display_name = fi.display_name
            existing.description = fi.description
            existing.python_entry = py_entry
            existing.dependencies = list(fi.dependencies)
            existing.parameter_schema = dict(fi.parameter_schema)
            existing.updated_at = ts
            upserted += 1

    db.commit()
    return {"count": len(infos), "upserted": upserted}


def list_factor_metadata(db: Session) -> list[FactorMetadata]:
    return list(db.scalars(select(FactorMetadata).order_by(FactorMetadata.factor_name)).all())

