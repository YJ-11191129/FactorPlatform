from __future__ import annotations

import os
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sqlalchemy import and_, func, select

from app.core.settings import get_settings
from app.db.session import db_session, get_engine
from app.models.market_data import DailyOHLCV, MarketDataSource, MarketUniverseMember


TRUTHY = {"1", "true", "True", "YES", "yes", "on", "ON"}


def postgres_market_data_enabled() -> bool:
    raw = get_settings().market_data_backend or os.getenv("FACTOR_PLATFORM_MARKET_DATA_BACKEND", "files")
    return raw.strip().lower() in {"postgres", "postgresql", "db", "database"}


def resolve_market_source_id(
    *,
    provider_uri: str | None = None,
    universe: str | None = None,
    region: str | None = None,
    source_id: str | None = None,
) -> str:
    if source_id:
        return source_id
    text = " ".join([provider_uri or "", universe or "", region or ""]).lower()
    if any(token in text for token in ["us_data", "sp500", "nasdaq", "nyse", "usa", " us"]):
        return "qlib_us_daily"
    if any(token in text for token in ["wind", "parquet", "ohlcv"]):
        return "wind_stock_ohlcv"
    return "qlib_cn_daily"


class MarketDataRepository:
    def __init__(self, source_id: str | None = None) -> None:
        self.source_id = source_id

    def source_exists(self, source_id: str) -> bool:
        with db_session() as db:
            return db.get(MarketDataSource, source_id) is not None

    def source_status_items(self) -> list[dict[str, Any]]:
        with db_session() as db:
            rows = list(db.scalars(select(MarketDataSource).order_by(MarketDataSource.source_id)).all())
        return [self._status_item(row) for row in rows]

    def status_item(self, source_id: str) -> dict[str, Any] | None:
        with db_session() as db:
            row = db.get(MarketDataSource, source_id)
        return self._status_item(row) if row else None

    def _status_item(self, row: MarketDataSource) -> dict[str, Any]:
        latest = row.end_date.isoformat() if row.end_date else None
        days_since_latest = None
        if row.end_date:
            days_since_latest = int((date.today() - row.end_date).days)
        return {
            "source_id": row.source_id,
            "label": row.label,
            "path": row.storage_origin,
            "kind": row.source_type,
            "exists": row.row_count > 0,
            "file_size_bytes": None,
            "mtime": None,
            "row_count": int(row.row_count or 0),
            "asset_count": int(row.asset_count or 0),
            "start_date": row.start_date.isoformat() if row.start_date else None,
            "end_date": latest,
            "freshness_days": (row.meta or {}).get("freshness_days", 5),
            "days_since_latest": days_since_latest,
            "status": row.freshness_status or "UNKNOWN",
            "notes": list((row.meta or {}).get("notes") or []),
            "database_backed": True,
        }

    def data_status(self, source_id: str) -> dict[str, Any]:
        with db_session() as db:
            src = db.get(MarketDataSource, source_id)
            if src is None:
                raise FileNotFoundError(f"market data source not found in database: {source_id}")
            columns = [c.name for c in DailyOHLCV.__table__.columns]
        return {
            "source": f"postgres:{source_id}",
            "columns": columns,
            "start_date": src.start_date.isoformat() if src.start_date else "",
            "end_date": src.end_date.isoformat() if src.end_date else "",
            "asset_count": int(src.asset_count or 0),
            "row_count": int(src.row_count or 0),
        }

    def list_instruments(self, source_id: str, universe: str | None = None, instrument_limit: int | None = None) -> list[str]:
        universe_name = (universe or "all").strip().lower() or "all"
        limit = max(0, int(instrument_limit)) if instrument_limit is not None else None
        with db_session() as db:
            if universe_name != "all":
                stmt = (
                    select(MarketUniverseMember.asset_code)
                    .where(and_(MarketUniverseMember.source_id == source_id, MarketUniverseMember.universe == universe_name))
                    .order_by(MarketUniverseMember.asset_code)
                )
                if limit:
                    stmt = stmt.limit(limit)
                rows = [str(x) for x in db.scalars(stmt).all()]
                if rows:
                    return rows
            stmt = select(DailyOHLCV.asset_code).where(DailyOHLCV.source_id == source_id).distinct().order_by(DailyOHLCV.asset_code)
            if limit:
                stmt = stmt.limit(limit)
            return [str(x) for x in db.scalars(stmt).all()]

    def load_daily_bar(
        self,
        *,
        source_id: str | None = None,
        provider_uri: str | None = None,
        universe: str = "all",
        start_date: date | None = None,
        end_date: date | None = None,
        instruments: Iterable[str] | None = None,
        instrument_limit: int | None = None,
    ) -> pd.DataFrame:
        sid = source_id or self.source_id or resolve_market_source_id(provider_uri=provider_uri, universe=universe)
        selected = list(dict.fromkeys(str(x).strip() for x in (instruments or []) if str(x).strip()))
        if not selected:
            selected = self.list_instruments(sid, universe=universe, instrument_limit=instrument_limit)
        elif instrument_limit is not None:
            selected = selected[: max(int(instrument_limit), 0)]

        cols = [
            DailyOHLCV.trade_date,
            DailyOHLCV.asset_code,
            DailyOHLCV.open,
            DailyOHLCV.high,
            DailyOHLCV.low,
            DailyOHLCV.close,
            DailyOHLCV.volume,
            DailyOHLCV.amount,
            DailyOHLCV.adj_factor,
            DailyOHLCV.vwap,
        ]
        stmt = select(*cols).where(DailyOHLCV.source_id == sid)
        if start_date is not None:
            stmt = stmt.where(DailyOHLCV.trade_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(DailyOHLCV.trade_date <= end_date)
        if selected:
            stmt = stmt.where(DailyOHLCV.asset_code.in_(selected))
        stmt = stmt.order_by(DailyOHLCV.asset_code, DailyOHLCV.trade_date)

        df = pd.read_sql(stmt, get_engine())
        if df.empty:
            return pd.DataFrame(columns=["trade_date", "asset_code", "open", "high", "low", "close", "volume", "amount", "adj_factor", "vwap"])
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["asset_code"] = df["asset_code"].astype(str)
        for col in ["open", "high", "low", "close", "volume", "amount", "adj_factor", "vwap"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["trade_date", "asset_code", "close"])
        return df.sort_values(["asset_code", "trade_date"], kind="mergesort").reset_index(drop=True)

    def next_trade_date(self, *, source_id: str, signal_date: date) -> str | None:
        with db_session() as db:
            value = db.scalar(
                select(func.min(DailyOHLCV.trade_date)).where(
                    and_(DailyOHLCV.source_id == source_id, DailyOHLCV.trade_date > signal_date)
                )
            )
        return value.isoformat() if value else None


def repository_for_source(
    *,
    provider_uri: str | None = None,
    universe: str | None = None,
    region: str | None = None,
    source_id: str | None = None,
) -> MarketDataRepository:
    return MarketDataRepository(resolve_market_source_id(provider_uri=provider_uri, universe=universe, region=region, source_id=source_id))
