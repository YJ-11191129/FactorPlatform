from __future__ import annotations

import argparse
import os
import site
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq


def _prepare_windpy_path() -> None:
    try:
        user_site = site.getusersitepackages()
        sys.path[:] = [p for p in sys.path if os.path.normcase(p) != os.path.normcase(user_site)]
    except Exception:
        pass
    for candidate in [Path(r"D:\wind\x64"), Path(r"D:\wind\bin")]:
        if (candidate / "WindPy.py").exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


def _import_wind() -> object:
    _prepare_windpy_path()
    import WindPy

    from WindPy import w

    r = w.start()
    if getattr(r, "ErrorCode", None) not in (0, None):
        wind_errors = {
            -40520005: "No Python API Authority",
            -40520014: "Please log on iWind first",
            -40520019: "Account restricted",
            -40520004: "Login failed",
            -40520008: "Timeout",
            -40520009: "WBox lost",
        }
        error_code = int(r.ErrorCode)
        message = wind_errors.get(error_code, "Start error")
        raise RuntimeError(f"Wind start failed: ErrorCode={error_code} ({message})")
    return w


def _max_date_in_parquet(path: Path) -> date | None:
    if not path.exists():
        return None
    dataset = ds.dataset(str(path), format="parquet")
    if "date" not in dataset.schema.names:
        return None
    scanner = dataset.scanner(columns=["date"], batch_size=200_000)
    best: date | None = None
    for batch in scanner.to_batches():
        arr = batch.column(0)
        m = pc.max(arr)
        if not m.is_valid:
            continue
        d = pd.to_datetime(m.as_py()).date()
        best = d if best is None else max(best, d)
    return best


def _read_universe_codes(data_root: Path) -> list[str] | None:
    p = data_root / "01_master" / "a_share_universe.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=["wind_code"])
    if df.empty:
        return None
    out = df["wind_code"].astype(str).dropna().drop_duplicates().sort_values().tolist()
    return out


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _fetch_wsd_panel(w, codes: list[str], fields: list[str], start: str, end: str, options: str) -> pd.DataFrame:
    merged: pd.DataFrame | None = None
    for field_name in fields:
        frames: list[pd.DataFrame] = []
        for idx, code_chunk in enumerate(_chunk(codes, 200), start=1):
            result = w.wsd(",".join(code_chunk), field_name, start, end, options)
            if getattr(result, "ErrorCode", None) != 0:
                raise RuntimeError(f"WSD failed: field={field_name} ErrorCode={result.ErrorCode}")
            times = [t.strftime("%Y-%m-%d") for t in (result.Times or [])]
            data = result.Data or []

            if len(data) == 1 and len(code_chunk) > 1 and isinstance(data[0], list) and len(data[0]) == len(code_chunk):
                data = data[0]

            if len(data) == len(times) and len(code_chunk) > 1 and data and isinstance(data[0], list) and len(data[0]) == len(code_chunk):
                data = list(map(list, zip(*data)))

            if len(data) != len(code_chunk):
                raise RuntimeError(f"Unexpected WSD shape: field={field_name} got_rows={len(data)} want={len(code_chunk)}")
            rows: list[dict] = []
            for code, values in zip(code_chunk, data):
                if values is None:
                    values = [None] * len(times)
                elif not isinstance(values, (list, tuple)):
                    values = [values] * len(times)
                for dt, v in zip(times, values):
                    rows.append({"date": dt, "wind_code": code, field_name: v})
            if rows:
                frames.append(pd.DataFrame(rows))

            if idx % 5 == 0:
                print(f"WSD progress: field={field_name} chunk={idx}")
        field_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "wind_code", field_name])
        merged = field_df if merged is None else merged.merge(field_df, on=["date", "wind_code"], how="outer")
    return merged if merged is not None else pd.DataFrame(columns=["date", "wind_code"])


def _append_parquet_atomic(dst: Path, new_df: pd.DataFrame) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        new_df.to_parquet(dst, index=False)
        return

    pf = pq.ParquetFile(str(dst))
    schema = pf.schema_arrow
    want = [n for n in schema.names]
    out_path = dst.with_suffix(dst.suffix + ".tmp")
    writer = pq.ParquetWriter(str(out_path), schema=schema, compression="zstd")
    try:
        for i in range(pf.num_row_groups):
            writer.write_table(pf.read_row_group(i))
        table = pa.Table.from_pandas(new_df[want], preserve_index=False)
        table = table.cast(schema)
        writer.write_table(table)
    finally:
        writer.close()
    os.replace(out_path, dst)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=r"D:\Kaggle\data\wind_data")
    parser.add_argument("--path", default=None)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default="today")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    dst = Path(args.path) if args.path else (data_root / "02_daily_stock" / "stock_daily_ohlcv.parquet")

    last = _max_date_in_parquet(dst)
    if args.start:
        start = args.start
    else:
        start = (last + timedelta(days=1)).isoformat() if last is not None else "2018-01-01"

    end = args.end
    if end == "today":
        end = datetime.today().strftime("%Y-%m-%d")
    w = _import_wind()

    t = w.tdays(start, end, "")
    if getattr(t, "ErrorCode", None) not in (0, None):
        raise RuntimeError(f"Wind tdays failed: ErrorCode={t.ErrorCode}")
    times = getattr(t, "Times", None) or []
    if not times:
        print(f"No new trading days between {start} and {end}. Current max={last}")
        return

    start_eff = times[0].strftime("%Y-%m-%d")
    end_eff = times[-1].strftime("%Y-%m-%d")

    codes = _read_universe_codes(data_root)
    if not codes:
        raise RuntimeError("a_share_universe.parquet not found or empty; please run universe download first")

    print(f"Fetching OHLCV: codes={len(codes)} range={start_eff}~{end_eff}")
    df = _fetch_wsd_panel(w, codes, ["open", "high", "low", "close", "volume", "amt"], start_eff, end_eff, "PriceAdj=F")
    if df.empty:
        print("No rows fetched")
        return

    for c in ["open", "high", "low", "close", "volume", "amt"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["wind_code"] = df["wind_code"].astype(str)
    df = df.dropna(subset=["date", "wind_code", "close"]).drop_duplicates(["date", "wind_code"], keep="last")
    df = df.sort_values(["date", "wind_code"], kind="mergesort").reset_index(drop=True)

    _append_parquet_atomic(dst, df)
    print(f"Updated {dst} with {len(df)} rows ({start_eff} ~ {end_eff})")


if __name__ == "__main__":
    main()
