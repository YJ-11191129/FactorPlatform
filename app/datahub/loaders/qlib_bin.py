from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd


def read_calendar(provider_uri: str) -> pd.DatetimeIndex:
    cal_path = Path(provider_uri) / "calendars" / "day.txt"
    dates = pd.to_datetime(cal_path.read_text(encoding="utf-8").splitlines(), format="%Y-%m-%d")
    return pd.DatetimeIndex(dates)


def read_instruments(provider_uri: str, universe: str) -> list[str]:
    uni_file = "all.txt" if universe == "all" else f"{universe}.txt"
    ins_path = Path(provider_uri) / "instruments" / uni_file

    instruments: list[str] = []
    seen: set[str] = set()
    for line in ins_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        symbol = parts[0]
        if symbol in seen:
            continue
        seen.add(symbol)
        instruments.append(symbol)
    return instruments


def _feature_dir_name(symbol: str) -> str:
    """Match qlib's filesystem-safe instrument directory convention."""

    return "".join(ch.lower() if ch.isalnum() else "_" for ch in symbol).strip("_")


def _read_feature_bin(path: Path, calendar_size: int) -> np.ndarray:
    if not path.exists():
        return np.full(calendar_size, np.nan, dtype="float32")

    raw = path.read_bytes()
    if len(raw) <= 4:
        return np.full(calendar_size, np.nan, dtype="float32")

    # qlib stores a 4-byte start index followed by float32 values. Some dumps
    # encode the header as float32, while local Wind exports use uint32.
    header = raw[:4]
    start_as_uint = int(np.frombuffer(header, dtype="<u4", count=1)[0])
    start_as_float = float(np.frombuffer(header, dtype="<f4", count=1)[0])
    if np.isfinite(start_as_float) and abs(start_as_float - round(start_as_float)) < 1e-6:
        candidate = int(round(start_as_float))
        start_index = candidate if 0 <= candidate < calendar_size else start_as_uint
    else:
        start_index = start_as_uint

    values = np.frombuffer(raw[4:], dtype="<f4")
    out = np.full(calendar_size, np.nan, dtype="float32")
    if start_index >= calendar_size or values.size == 0:
        return out

    end_index = min(calendar_size, start_index + values.size)
    out[start_index:end_index] = values[: end_index - start_index]
    return out


def load_daily_bar(
    provider_uri: str,
    universe: str = "csi300",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    instruments: Optional[Iterable[str]] = None,
    instrument_limit: Optional[int] = None,
) -> pd.DataFrame:
    full_calendar = read_calendar(provider_uri)
    calendar = full_calendar

    if start_date is not None:
        calendar = calendar[calendar.date >= start_date]
    if end_date is not None:
        calendar = calendar[calendar.date <= end_date]

    if calendar.empty:
        return pd.DataFrame(columns=["trade_date", "asset_code", "open", "high", "low", "close", "volume", "adj_factor"])

    idx = full_calendar.get_indexer(calendar)

    if instruments is None:
        instruments = read_instruments(provider_uri, universe)

    symbols = list(dict.fromkeys(str(sym).strip() for sym in instruments if str(sym).strip()))
    if instrument_limit is not None:
        symbols = symbols[: max(int(instrument_limit), 0)]

    base = Path(provider_uri) / "features"
    frames: list[pd.DataFrame] = []

    for sym in symbols:
        ins_dir = base / _feature_dir_name(sym)
        if not ins_dir.exists():
            continue

        close = _read_feature_bin(ins_dir / "close.day.bin", full_calendar.size)
        if close.size != full_calendar.size or pd.isna(close[idx]).all():
            continue

        open_ = _read_feature_bin(ins_dir / "open.day.bin", full_calendar.size)
        high = _read_feature_bin(ins_dir / "high.day.bin", full_calendar.size)
        low = _read_feature_bin(ins_dir / "low.day.bin", full_calendar.size)
        volume = _read_feature_bin(ins_dir / "volume.day.bin", full_calendar.size)
        adj_factor = _read_feature_bin(ins_dir / "factor.day.bin", full_calendar.size)

        df = pd.DataFrame(
            {
                "trade_date": calendar.date,
                "asset_code": sym,
                "open": open_[idx],
                "high": high[idx],
                "low": low[idx],
                "close": close[idx],
                "volume": volume[idx],
                "adj_factor": adj_factor[idx],
            }
        )

        df.loc[df["close"] == 0.0, ["open", "high", "low", "close", "adj_factor"]] = np.nan
        df = df.dropna(subset=["close"])

        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["trade_date", "asset_code", "open", "high", "low", "close", "volume", "adj_factor"])

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["asset_code", "trade_date"], kind="mergesort")
    return out
