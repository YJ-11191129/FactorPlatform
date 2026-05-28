from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


DAILY_COLUMNS = [
    "source_id",
    "trade_date",
    "asset_code",
    "market",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adj_factor",
    "vwap",
    "meta",
]

MAX_MULTI_INSERT_PARAMS = 60_000


def _safe_multi_chunksize(df: pd.DataFrame, requested: int) -> int:
    """Keep pandas multi-row INSERTs under PostgreSQL's bind parameter limit."""
    if df.empty:
        return 1
    column_count = max(len(df.columns), 1)
    limit = max(MAX_MULTI_INSERT_PARAMS // column_count, 1)
    return max(min(int(requested), limit), 1)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)[:10]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        x = float(value)
        return x if math.isfinite(x) else None
    if pd.isna(value):
        return None
    return value


def _record_hash(*parts: Any) -> str:
    raw = json.dumps([_json_safe(p) for p in parts], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _upgrade_db(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


def _engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def _execute(engine: Engine, sql: str, params: dict[str, Any] | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def _upsert_source(
    engine: Engine,
    *,
    source_id: str,
    label: str,
    source_type: str,
    market: str,
    storage_origin: str,
    row_count: int,
    asset_count: int,
    start_date: str | None,
    end_date: str | None,
    meta: dict[str, Any] | None = None,
) -> None:
    _execute(
        engine,
        """
        insert into market_data_sources (
            source_id, label, source_type, market, storage_origin, start_date, end_date,
            row_count, asset_count, freshness_status, meta, updated_at
        )
        values (
            :source_id, :label, :source_type, :market, :storage_origin,
            cast(:start_date as date), cast(:end_date as date), :row_count, :asset_count,
            :freshness_status, cast(:meta as json), now()
        )
        on conflict (source_id) do update set
            label = excluded.label,
            source_type = excluded.source_type,
            market = excluded.market,
            storage_origin = excluded.storage_origin,
            start_date = excluded.start_date,
            end_date = excluded.end_date,
            row_count = excluded.row_count,
            asset_count = excluded.asset_count,
            freshness_status = excluded.freshness_status,
            meta = excluded.meta,
            updated_at = now()
        """,
        {
            "source_id": source_id,
            "label": label,
            "source_type": source_type,
            "market": market,
            "storage_origin": storage_origin,
            "start_date": start_date,
            "end_date": end_date,
            "row_count": int(row_count),
            "asset_count": int(asset_count),
            "freshness_status": "OK" if end_date else "WARN",
            "meta": json.dumps(meta or {}, ensure_ascii=False, default=str),
        },
    )


def _delete_source_rows(engine: Engine, source_id: str) -> None:
    _execute(engine, "delete from daily_ohlcv where source_id = :source_id", {"source_id": source_id})
    _execute(engine, "delete from market_universe_members where source_id = :source_id", {"source_id": source_id})


def _clean_daily_frame(df: pd.DataFrame, *, source_id: str, market: str) -> pd.DataFrame:
    out = df.copy()
    rename = {}
    if "date" in out.columns and "trade_date" not in out.columns:
        rename["date"] = "trade_date"
    if "datetime" in out.columns and "trade_date" not in out.columns:
        rename["datetime"] = "trade_date"
    for candidate in ["wind_code", "ts_code", "ticker", "symbol", "code"]:
        if candidate in out.columns and "asset_code" not in out.columns:
            rename[candidate] = "asset_code"
            break
    if "vol" in out.columns and "volume" not in out.columns:
        rename["vol"] = "volume"
    if "amt" in out.columns and "amount" not in out.columns:
        rename["amt"] = "amount"
    if rename:
        out = out.rename(columns=rename)
    if "trade_date" not in out.columns or "asset_code" not in out.columns or "close" not in out.columns:
        raise ValueError("daily data must include trade_date/date, asset_code/symbol, and close")
    out["source_id"] = source_id
    out["market"] = market
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.date
    out["asset_code"] = out["asset_code"].astype(str)
    for col in ["open", "high", "low", "close", "volume", "amount", "adj_factor", "vwap"]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["meta"] = "{}"
    out = out[DAILY_COLUMNS]
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=["trade_date", "asset_code", "close"])
    out = out.drop_duplicates(subset=["source_id", "trade_date", "asset_code"], keep="last")
    return out.where(pd.notnull(out), None)


def _upsert_daily(engine: Engine, df: pd.DataFrame, table_suffix: str) -> int:
    if df.empty:
        return 0
    stage = f"_stage_daily_ohlcv_{table_suffix}"
    df.to_sql(stage, engine, if_exists="replace", index=False, chunksize=_safe_multi_chunksize(df, 20_000), method="multi")
    try:
        _execute(
            engine,
            f"""
            insert into daily_ohlcv (
                source_id, trade_date, asset_code, market, open, high, low, close,
                volume, amount, adj_factor, vwap, meta
            )
            select
                source_id,
                trade_date::date,
                asset_code,
                market,
                open,
                high,
                low,
                close,
                volume,
                amount,
                adj_factor,
                vwap,
                coalesce(nullif(meta, '')::json, '{{}}'::json)
            from {stage}
            on conflict (source_id, trade_date, asset_code) do update set
                market = excluded.market,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                amount = excluded.amount,
                adj_factor = excluded.adj_factor,
                vwap = excluded.vwap,
                meta = excluded.meta
            """,
        )
    finally:
        _execute(engine, f"drop table if exists {stage}")
    return int(df.shape[0])


def _source_stats(engine: Engine, source_id: str) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                select count(*) as row_count,
                       count(distinct asset_code) as asset_count,
                       min(trade_date) as start_date,
                       max(trade_date) as end_date
                from daily_ohlcv
                where source_id = :source_id
                """
            ),
            {"source_id": source_id},
        ).mappings().one()
    return {
        "row_count": int(row["row_count"] or 0),
        "asset_count": int(row["asset_count"] or 0),
        "start_date": str(row["start_date"]) if row["start_date"] else None,
        "end_date": str(row["end_date"]) if row["end_date"] else None,
    }


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for idx in range(0, len(values), max(size, 1)):
        yield values[idx : idx + size]


def import_qlib(
    engine: Engine,
    *,
    provider_uri: Path,
    source_id: str,
    label: str,
    market: str,
    batch_size: int,
    instrument_limit: int | None,
    replace: bool,
) -> dict[str, Any]:
    from app.datahub.loaders.qlib_bin import load_daily_bar, read_instruments

    if not provider_uri.exists():
        return {"source_id": source_id, "status": "MISSING", "path": str(provider_uri)}
    if replace:
        _delete_source_rows(engine, source_id)
    universes: dict[str, list[str]] = {}
    ins_dir = provider_uri / "instruments"
    for file in sorted(ins_dir.glob("*.txt")):
        universe = file.stem.lower()
        symbols = read_instruments(str(provider_uri), universe)
        if instrument_limit is not None:
            symbols = symbols[: max(int(instrument_limit), 0)]
        universes[universe] = symbols
        _upsert_universe(engine, source_id, universe, symbols)
    all_symbols = universes.get("all") or sorted({s for values in universes.values() for s in values})
    if instrument_limit is not None:
        all_symbols = all_symbols[: max(int(instrument_limit), 0)]

    total = 0
    for batch_no, symbols in enumerate(_chunks(all_symbols, batch_size), start=1):
        df = load_daily_bar(str(provider_uri), universe="all", instruments=symbols)
        if df.empty:
            continue
        daily = _clean_daily_frame(df, source_id=source_id, market=market)
        total += _upsert_daily(engine, daily, f"{source_id}_{os.getpid()}_{batch_no}")
        print(f"{source_id}: imported batch {batch_no}, rows={len(daily)}, total={total}", flush=True)
    stats = _source_stats(engine, source_id)
    _upsert_source(
        engine,
        source_id=source_id,
        label=label,
        source_type="postgres_ohlcv",
        market=market,
        storage_origin=f"portable:{provider_uri}",
        meta={"provider_uri": str(provider_uri), "universes": {k: len(v) for k, v in universes.items()}, "freshness_days": 5},
        **stats,
    )
    return {"source_id": source_id, "status": "IMPORTED", **stats}


def _upsert_universe(engine: Engine, source_id: str, universe: str, symbols: list[str]) -> None:
    if not symbols:
        return
    df = pd.DataFrame(
        {
            "source_id": source_id,
            "universe": universe,
            "asset_code": list(dict.fromkeys(symbols)),
            "start_date": None,
            "end_date": None,
            "meta": "{}",
        }
    )
    stage = f"_stage_universe_{source_id}_{os.getpid()}"
    df.to_sql(stage, engine, if_exists="replace", index=False, chunksize=_safe_multi_chunksize(df, 20_000), method="multi")
    try:
        _execute(
            engine,
            f"""
            insert into market_universe_members (source_id, universe, asset_code, start_date, end_date, meta)
            select source_id, universe, asset_code, start_date::date, end_date::date, meta::json from {stage}
            on conflict (source_id, universe, asset_code) do update set
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                meta = excluded.meta
            """,
        )
    finally:
        _execute(engine, f"drop table if exists {stage}")


def import_ohlcv_parquet(
    engine: Engine,
    *,
    path: Path,
    source_id: str,
    label: str,
    market: str,
    replace: bool,
    batch_size: int,
) -> dict[str, Any]:
    if not path.exists():
        return {"source_id": source_id, "status": "MISSING", "path": str(path)}
    if replace:
        _delete_source_rows(engine, source_id)
    dataset = ds.dataset(str(path), format="parquet")
    total = 0
    for batch_no, batch in enumerate(dataset.scanner(batch_size=batch_size).to_batches(), start=1):
        df = batch.to_pandas()
        daily = _clean_daily_frame(df, source_id=source_id, market=market)
        total += _upsert_daily(engine, daily, f"{source_id}_{os.getpid()}_{batch_no}")
        print(f"{source_id}: imported parquet batch {batch_no}, rows={len(daily)}, total={total}", flush=True)
    stats = _source_stats(engine, source_id)
    _upsert_source(
        engine,
        source_id=source_id,
        label=label,
        source_type="postgres_ohlcv",
        market=market,
        storage_origin=f"portable:{path}",
        meta={"parquet_path": str(path), "freshness_days": 5},
        **stats,
    )
    return {"source_id": source_id, "status": "IMPORTED", **stats}


def import_structured_parquet(
    engine: Engine,
    *,
    path: Path,
    source_id: str,
    dataset_type: str,
    batch_size: int,
    row_limit: int | None,
) -> dict[str, Any]:
    if not path.exists():
        return {"source_id": source_id, "dataset_type": dataset_type, "status": "MISSING", "path": str(path)}
    dataset = ds.dataset(str(path), format="parquet")
    imported = 0
    for batch_no, batch in enumerate(dataset.scanner(batch_size=batch_size).to_batches(), start=1):
        df = batch.to_pandas()
        if row_limit is not None:
            remaining = max(int(row_limit) - imported, 0)
            if remaining <= 0:
                break
            df = df.head(remaining)
        rows: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            payload = {str(k): _json_safe(v) for k, v in row.to_dict().items()}
            trade_date = payload.get("trade_date") or payload.get("date") or payload.get("report_date") or payload.get("ann_dt")
            asset_code = payload.get("asset_code") or payload.get("wind_code") or payload.get("ts_code") or payload.get("symbol") or payload.get("code")
            parsed_date = pd.to_datetime(trade_date, errors="coerce")
            trade_text = str(parsed_date.date()) if pd.notna(parsed_date) else None
            rid = _record_hash(source_id, dataset_type, trade_text, asset_code, payload)
            rows.append(
                {
                    "record_id": rid,
                    "source_id": source_id,
                    "dataset_type": dataset_type,
                    "trade_date": trade_text,
                    "asset_code": str(asset_code) if asset_code is not None else None,
                    "payload": json.dumps(payload, ensure_ascii=False, default=str),
                }
            )
        if not rows:
            continue
        stage = f"_stage_structured_{source_id}_{os.getpid()}_{batch_no}"
        structured_df = pd.DataFrame(rows)
        structured_df.to_sql(
            stage,
            engine,
            if_exists="replace",
            index=False,
            chunksize=_safe_multi_chunksize(structured_df, 10_000),
            method="multi",
        )
        try:
            _execute(
                engine,
                f"""
                insert into structured_market_datasets (record_id, source_id, dataset_type, trade_date, asset_code, payload)
                select record_id, source_id, dataset_type, trade_date::date, asset_code, payload::json from {stage}
                on conflict (record_id) do update set
                    source_id = excluded.source_id,
                    dataset_type = excluded.dataset_type,
                    trade_date = excluded.trade_date,
                    asset_code = excluded.asset_code,
                    payload = excluded.payload
                """,
            )
        finally:
            _execute(engine, f"drop table if exists {stage}")
        imported += len(rows)
        print(f"{dataset_type}: imported structured batch {batch_no}, rows={len(rows)}, total={imported}", flush=True)
    _upsert_source(
        engine,
        source_id=source_id,
        label=dataset_type.replace("_", " ").title(),
        source_type="postgres_structured",
        market="multi",
        storage_origin=f"portable:{path}",
        row_count=imported,
        asset_count=0,
        start_date=None,
        end_date=None,
        meta={"parquet_path": str(path), "dataset_type": dataset_type},
    )
    return {"source_id": source_id, "dataset_type": dataset_type, "status": "IMPORTED", "row_count": imported}


def _dump_database(database_url: str, dump_out: Path) -> None:
    dump_out.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    pg_url = database_url.replace("postgresql+psycopg://", "postgresql://")
    env["DATABASE_URL"] = pg_url
    proc = subprocess.run(["pg_dump", "--format=custom", "--file", str(dump_out), pg_url], env=env, text=True)
    if proc.returncode != 0:
        raise RuntimeError("pg_dump failed; install PostgreSQL client tools or use scripts/build_roadshow_db.ps1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import portable roadshow market data into PostgreSQL.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:factorplatform_dev_password@localhost:5432/factor_platform"))
    parser.add_argument("--portable-root", type=Path, default=PROJECT_ROOT / "data" / "portable")
    parser.add_argument("--markets", default="cn,us,wind,structured", help="Comma-separated: cn,us,wind,structured")
    parser.add_argument("--qlib-batch-size", type=int, default=100)
    parser.add_argument("--parquet-batch-size", type=int, default=100_000)
    parser.add_argument("--instrument-limit", type=int, default=None, help="Smoke-test limit. Omit for full import.")
    parser.add_argument("--structured-row-limit", type=int, default=None, help="Smoke-test limit. Omit for full import.")
    parser.add_argument("--append", action="store_true", help="Do not delete existing source rows before import.")
    parser.add_argument("--dump-out", type=Path, default=None)
    args = parser.parse_args()

    database_url = args.database_url
    os.environ["DATABASE_URL"] = database_url
    _upgrade_db(database_url)
    engine = _engine(database_url)
    selected = {x.strip().lower() for x in args.markets.split(",") if x.strip()}
    portable = args.portable_root
    results: list[dict[str, Any]] = []

    if "cn" in selected:
        results.append(
            import_qlib(
                engine,
                provider_uri=portable / "mcqlib" / "qlib_bin" / "cn_data",
                source_id="qlib_cn_daily",
                label="Qlib CN daily provider",
                market="cn",
                batch_size=args.qlib_batch_size,
                instrument_limit=args.instrument_limit,
                replace=not args.append,
            )
        )
    if "us" in selected:
        results.append(
            import_qlib(
                engine,
                provider_uri=portable / "mcqlib" / "qlib_bin" / "us_data",
                source_id="qlib_us_daily",
                label="Qlib US daily provider",
                market="us",
                batch_size=args.qlib_batch_size,
                instrument_limit=args.instrument_limit,
                replace=not args.append,
            )
        )
    if "wind" in selected:
        results.append(
            import_ohlcv_parquet(
                engine,
                path=portable / "kaggle" / "wind_data" / "02_daily_stock" / "stock_daily_ohlcv.parquet",
                source_id="wind_stock_ohlcv",
                label="Wind stock daily OHLCV",
                market="cn",
                replace=not args.append,
                batch_size=args.parquet_batch_size,
            )
        )
    if "structured" in selected:
        structured_specs = [
            ("wind_daily_basic", "stock_daily_basic", portable / "kaggle" / "wind_data" / "02_daily_stock" / "stock_daily_basic.parquet"),
            ("macro_cross_asset", "macro_cross_asset_daily", portable / "kaggle" / "wind_data" / "03_market_state" / "macro_cross_asset_daily.parquet"),
            ("financial_statement", "financial_statement_pit", portable / "kaggle" / "processed" / "financial_statement.parquet"),
            ("daily_pit_features", "daily_pit_features", portable / "kaggle" / "processed" / "daily_pit_features.parquet"),
        ]
        for source_id, dataset_type, path in structured_specs:
            results.append(
                import_structured_parquet(
                    engine,
                    path=path,
                    source_id=source_id,
                    dataset_type=dataset_type,
                    batch_size=args.parquet_batch_size,
                    row_limit=args.structured_row_limit,
                )
            )

    manifest = {"generated_at": pd.Timestamp.utcnow().isoformat(), "portable_root": str(portable), "results": results}
    out_path = PROJECT_ROOT / "data" / "db_dumps" / "roadshow_import_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))

    if args.dump_out:
        _dump_database(database_url, args.dump_out)
        print(f"dump written: {args.dump_out}")


if __name__ == "__main__":
    main()
