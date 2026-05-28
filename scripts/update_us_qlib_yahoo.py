from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import IncompleteRead, RemoteDisconnected
import json
import math
import shutil
import struct
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.datahub.loaders.qlib_bin import _feature_dir_name, _read_feature_bin, read_calendar


DEFAULT_PROVIDER_URI = Path(r"D:\mcQlib\data\qlib_bin\us_data")
FIELDS = ("open", "high", "low", "close", "volume", "factor", "change")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update a qlib US provider from Yahoo Chart API without native qlib/yfinance."
    )
    parser.add_argument("--provider-uri", type=Path, default=DEFAULT_PROVIDER_URI)
    parser.add_argument("--universes", nargs="+", default=["sp500", "nasdaq100"], help="Instrument files to update.")
    parser.add_argument("--symbols", nargs="+", help="Optional explicit symbols; overrides universes.")
    parser.add_argument("--start", help="YYYY-MM-DD. Defaults to existing calendar latest date + 1 day.")
    parser.add_argument("--end", default=date.today().isoformat(), help="YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--limit", type=int, default=0, help="Limit symbols for smoke tests. 0 means no limit.")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first N symbols. Useful for batch resume.")
    parser.add_argument("--sleep", type=float, default=0.05, help="Delay between Yahoo requests.")
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--workers", type=int, default=1, help="Concurrent Yahoo fetch workers. 1 keeps sequential behavior.")
    parser.add_argument("--max-failures", type=int, default=0, help="Stop after N failed symbols. 0 means never stop early.")
    parser.add_argument("--failure-log", type=Path, help="Optional JSON file for failed symbols.")
    parser.add_argument("--backup", action="store_true", help="Create provider backup before writing.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-all-file", action="store_true", help="Also update instruments/all.txt end dates for updated symbols.")
    return parser.parse_args()


def read_instrument_rows(provider_uri: Path, universe: str) -> list[tuple[str, str | None, str | None]]:
    path = provider_uri / "instruments" / ("all.txt" if universe == "all" else f"{universe}.txt")
    rows: list[tuple[str, str | None, str | None]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        rows.append((parts[0], parts[1] if len(parts) > 1 else None, parts[2] if len(parts) > 2 else None))
    return rows


def unique_symbols(provider_uri: Path, universes: list[str], explicit: list[str] | None) -> list[str]:
    if explicit:
        return list(dict.fromkeys(symbol.strip().upper() for symbol in explicit if symbol.strip()))
    symbols: list[str] = []
    for universe in universes:
        symbols.extend(symbol for symbol, _, _ in read_instrument_rows(provider_uri, universe))
    return list(dict.fromkeys(symbols))


def yahoo_symbol(symbol: str) -> str:
    # Some qlib instrument files store class shares as BRK.B while Yahoo uses
    # BRK-B. Keep the provider symbol unchanged on disk and only map the query.
    return symbol.strip().upper().replace(".", "-")


def yahoo_chart_url(symbol: str, start: date, end: date) -> str:
    period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    query = urllib.parse.urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    return f"https://{{host}}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_symbol(symbol))}?{query}"


def fetch_yahoo(symbol: str, start: date, end: date, retries: int) -> pd.DataFrame:
    url_template = yahoo_chart_url(symbol, start, end)
    last_error: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        host = "query1" if attempt % 2 else "query2"
        url = url_template.format(host=host)
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "FactorPlatform-US-Qlib-Yahoo-Updater/1.0",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            result = (payload.get("chart", {}).get("result") or [None])[0]
            if not result:
                error = payload.get("chart", {}).get("error")
                raise RuntimeError(f"empty Yahoo result: {error}")

            timestamps = result.get("timestamp") or []
            quote = (result.get("indicators", {}).get("quote") or [{}])[0]
            adjclose = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
            if not timestamps:
                return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "factor"])

            df = pd.DataFrame(
                {
                    "date": [datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat() for ts in timestamps],
                    "open_raw": quote.get("open") or [],
                    "high_raw": quote.get("high") or [],
                    "low_raw": quote.get("low") or [],
                    "close_raw": quote.get("close") or [],
                    "volume": quote.get("volume") or [],
                    "adjclose": adjclose if len(adjclose) == len(timestamps) else [math.nan] * len(timestamps),
                }
            )
            for col in ["open_raw", "high_raw", "low_raw", "close_raw", "volume", "adjclose"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close_raw"]).copy()
            if df.empty:
                return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "factor"])

            factor = (df["adjclose"] / df["close_raw"]).replace([np.inf, -np.inf], np.nan)
            factor = factor.where(factor.notna() & (factor > 0), 1.0)
            df["factor"] = factor
            df["open"] = df["open_raw"] * df["factor"]
            df["high"] = df["high_raw"] * df["factor"]
            df["low"] = df["low_raw"] * df["factor"]
            df["close"] = df["close_raw"] * df["factor"]
            return df[["date", "open", "high", "low", "close", "volume", "factor"]].drop_duplicates("date")
        except HTTPError as exc:
            if exc.code in {404, 410}:
                raise RuntimeError(f"Yahoo symbol not found or delisted: HTTP {exc.code}") from exc
            last_error = exc
            time.sleep(min(2 * attempt, 8))
        except (URLError, TimeoutError, RuntimeError, json.JSONDecodeError, IncompleteRead, RemoteDisconnected) as exc:
            last_error = exc
            time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"{symbol} Yahoo fetch failed after {retries} attempts: {last_error}")


def read_existing_series(provider_uri: Path, symbol: str, old_calendar: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    symbol_dir = provider_uri / "features" / _feature_dir_name(symbol)
    return {field: _read_feature_bin(symbol_dir / f"{field}.day.bin", len(old_calendar)) for field in FIELDS}


def latest_symbol_date(provider_uri: Path, symbol: str, calendar: pd.DatetimeIndex) -> date | None:
    close = _read_feature_bin(provider_uri / "features" / _feature_dir_name(symbol) / "close.day.bin", len(calendar))
    valid = np.where(np.isfinite(close))[0]
    if valid.size == 0:
        return None
    return calendar[int(valid[-1])].date()


def compute_change(close: np.ndarray) -> np.ndarray:
    out = np.full(close.shape, np.nan, dtype="float32")
    prev = np.roll(close, 1)
    valid = np.isfinite(close) & np.isfinite(prev) & (prev != 0)
    out[valid] = close[valid] / prev[valid] - 1.0
    if out.size:
        out[0] = np.nan
    return out


def write_feature_bin(path: Path, start_index: int, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = values.astype("<f4", copy=False)
    with path.open("wb") as file_obj:
        file_obj.write(struct.pack("<I", int(start_index)))
        if values.size:
            file_obj.write(values.tobytes(order="C"))


def trim_and_write_symbol(provider_uri: Path, symbol: str, calendar: list[str], series: dict[str, np.ndarray]) -> None:
    close = series["close"]
    valid = np.where(np.isfinite(close))[0]
    if valid.size == 0:
        return
    start_index = int(valid[0])
    end_index = int(valid[-1]) + 1
    symbol_dir = provider_uri / "features" / _feature_dir_name(symbol)
    for field in FIELDS:
        values = series[field][start_index:end_index]
        write_feature_bin(symbol_dir / f"{field}.day.bin", start_index, values)


def merge_calendar(old_calendar: pd.DatetimeIndex, fetched: dict[str, pd.DataFrame]) -> list[str]:
    dates = {ts.date().isoformat() for ts in old_calendar}
    for df in fetched.values():
        dates.update(str(value) for value in df.get("date", []) if value)
    return sorted(dates)


def update_instrument_file(provider_uri: Path, universe: str, updated_symbols: set[str], latest_date: str) -> None:
    path = provider_uri / "instruments" / ("all.txt" if universe == "all" else f"{universe}.txt")
    if not path.exists():
        return
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        symbol = parts[0]
        start = parts[1] if len(parts) > 1 else "1900-01-01"
        end = parts[2] if len(parts) > 2 else latest_date
        if symbol in updated_symbols:
            end = latest_date
        lines.append(f"{symbol}\t{start}\t{end}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_calendar(provider_uri: Path, calendar: list[str]) -> None:
    path = provider_uri / "calendars" / "day.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(calendar) + "\n", encoding="utf-8")


def update_provider(args: argparse.Namespace) -> dict[str, object]:
    provider_uri: Path = args.provider_uri
    old_calendar = read_calendar(str(provider_uri))
    old_latest = old_calendar.max().date()
    symbols = unique_symbols(provider_uri, args.universes, args.symbols)
    if args.offset and args.offset > 0:
        symbols = symbols[args.offset :]
    if args.limit and args.limit > 0:
        symbols = symbols[: args.limit]

    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        start = old_latest + timedelta(days=1)
    if start > end:
        return {"status": "SKIPPED", "message": f"selected symbols already up to date through {end}", "start": start, "end": end}
    print(f"provider={provider_uri}")
    print(f"old_latest={old_latest} start={start} end={end} symbols={len(symbols)}")

    fetched: dict[str, pd.DataFrame] = {}
    failed: dict[str, str] = {}
    started_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    workers = max(1, int(args.workers or 1))
    if workers == 1:
        for index, symbol in enumerate(symbols, start=1):
            try:
                df = fetch_yahoo(symbol, start, end, retries=args.retries)
                if not df.empty:
                    fetched[symbol] = df
                print(f"[{index:>4}/{len(symbols)}] {symbol:<8} rows={len(df)}")
            except Exception as exc:
                failed[symbol] = str(exc)
                print(f"[{index:>4}/{len(symbols)}] {symbol:<8} FAILED {exc}")
                if args.max_failures and len(failed) >= args.max_failures:
                    print(f"max_failures={args.max_failures} reached; stopping fetch loop.")
                    break
            if args.sleep > 0:
                time.sleep(args.sleep)
    else:
        print(f"fetch_workers={workers}")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_symbol = {}
            for symbol in symbols:
                future_to_symbol[executor.submit(fetch_yahoo, symbol, start, end, args.retries)] = symbol
                if args.sleep > 0:
                    time.sleep(args.sleep)
            for index, future in enumerate(as_completed(future_to_symbol), start=1):
                symbol = future_to_symbol[future]
                try:
                    df = future.result()
                    if not df.empty:
                        fetched[symbol] = df
                    print(f"[{index:>4}/{len(symbols)}] {symbol:<8} rows={len(df)}")
                except Exception as exc:
                    failed[symbol] = str(exc)
                    print(f"[{index:>4}/{len(symbols)}] {symbol:<8} FAILED {exc}")
                    if args.max_failures and len(failed) >= args.max_failures:
                        print(f"max_failures={args.max_failures} reached; stopping fetch loop.")
                        break

    if failed:
        failure_log = args.failure_log
        if failure_log is None:
            failure_log = PROJECT_ROOT / "data" / "exports" / "data_maintenance" / f"us_yahoo_failures_{started_at}.json"
        failure_log.parent.mkdir(parents=True, exist_ok=True)
        failure_log.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "provider_uri": str(provider_uri),
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "symbols_requested": len(symbols),
                    "symbols_updated": len(fetched),
                    "symbols_failed": len(failed),
                    "failed": failed,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"failure log written: {failure_log}")

    if not fetched:
        return {"status": "FAILED", "message": "no Yahoo rows fetched", "failed": failed}

    new_calendar = merge_calendar(old_calendar, fetched)
    date_to_index = {d: i for i, d in enumerate(new_calendar)}
    old_date_to_new_index = {ts.date().isoformat(): date_to_index[ts.date().isoformat()] for ts in old_calendar}
    latest_date = max(max(df["date"]) for df in fetched.values())
    if args.dry_run:
        return {
            "status": "DRY_RUN",
            "old_latest": old_latest.isoformat(),
            "latest_fetched": latest_date,
            "symbols_requested": len(symbols),
            "symbols_updated": len(fetched),
            "symbols_failed": len(failed),
            "failure_log": str(failure_log) if failed else None,
            "failed_sample": dict(list(failed.items())[:10]),
        }

    if args.backup:
        backup_dir = provider_uri.parent / f"{provider_uri.name}_backup_yahoo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"creating backup: {backup_dir}")
        shutil.copytree(provider_uri, backup_dir)

    for symbol, df in fetched.items():
        old_series = read_existing_series(provider_uri, symbol, old_calendar)
        full_series = {field: np.full(len(new_calendar), np.nan, dtype="float32") for field in FIELDS}
        for old_idx, new_idx in enumerate(old_date_to_new_index.values()):
            for field in FIELDS:
                full_series[field][new_idx] = old_series[field][old_idx]
        for _, row in df.iterrows():
            idx = date_to_index[str(row["date"])]
            for field in ("open", "high", "low", "close", "volume", "factor"):
                value = row[field]
                full_series[field][idx] = np.nan if pd.isna(value) else float(value)
        full_series["change"] = compute_change(full_series["close"])
        trim_and_write_symbol(provider_uri, symbol, new_calendar, full_series)

    write_calendar(provider_uri, new_calendar)
    for universe in args.universes:
        update_instrument_file(provider_uri, universe, set(fetched), latest_date)
    if args.include_all_file and "all" not in args.universes:
        update_instrument_file(provider_uri, "all", set(fetched), latest_date)

    return {
        "status": "SUCCESS",
        "old_latest": old_latest.isoformat(),
        "latest_fetched": latest_date,
        "calendar_latest": new_calendar[-1],
        "symbols_requested": len(symbols),
        "symbols_updated": len(fetched),
        "symbols_failed": len(failed),
        "failure_log": str(failure_log) if failed else None,
        "failed_sample": dict(list(failed.items())[:10]),
    }


def main() -> None:
    args = parse_args()
    result = update_provider(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
