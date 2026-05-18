from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    analysis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analysis_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    calc_batch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    factor_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="SUCCESS")
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    artifact_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

