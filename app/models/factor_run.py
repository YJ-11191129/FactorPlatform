from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FactorRun(Base):
    __tablename__ = "factor_runs"

    calc_batch_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    factor_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(64), nullable=False, default="factor_library", index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    universe_name: Mapped[str] = mapped_column(String(128), nullable=False, default="A_SHARE_ALL", index=True)
    provider_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    instrument_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifact_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS", index=True)
    error: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

