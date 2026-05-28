from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketDataSource(Base):
    __tablename__ = "market_data_sources"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    storage_origin: Mapped[str] = mapped_column(String(1024), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    asset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    freshness_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN", index=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketUniverseMember(Base):
    __tablename__ = "market_universe_members"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    universe: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class DailyOHLCV(Base):
    __tablename__ = "daily_ohlcv"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    market: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    adj_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class StructuredMarketDataset(Base):
    __tablename__ = "structured_market_datasets"

    record_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dataset_type: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    asset_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RoadshowSeedState(Base):
    __tablename__ = "roadshow_seed_state"

    seed_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dump_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    dump_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    restored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
