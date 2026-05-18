from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FactorMetadata(Base):
    __tablename__ = "factor_metadata"

    factor_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(String(2048), nullable=False)
    python_entry: Mapped[str] = mapped_column(String(512), nullable=False)
    dependencies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    parameter_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE", index=True)
    owner: Mapped[str] = mapped_column(String(128), nullable=False, default="research")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

