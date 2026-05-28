from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.compute as pc
import pyarrow as pa

from app.datahub.loaders.qlib_bin import load_daily_bar as load_qlib_daily_bar
from app.services.strategy_service import ensure_strategies_loaded
from app.services.strategy_validator import indicator_alias, validate_strategy_spec
from app.strategies.registry import get_strategy


@dataclass(frozen=True)
class BacktestArtifact:
    backtest_id: str
    created_at: str
    strategy_id: str
    row_count: int
    equity_curve_path: str
    positions_path: str
    summary_path: str


@dataclass(frozen=True)
class BacktestPriceSource:
    kind: str
    source_id: str
    provider_uri: str | None = None
    path: Path | None = None
    region: str | None = None
    universe: str | None = None
    instruments: tuple[str, ...] = ()
    requested_universe: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source_id": self.source_id,
            "provider_uri": self.provider_uri,
            "path": str(self.path) if self.path else None,
            "region": self.region,
            "universe": self.universe,
            "instruments": list(self.instruments),
            "requested_universe": list(self.requested_universe),
        }


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _select_backtest_root() -> Path:
    override = os.getenv("FACTOR_PLATFORM_BACKTEST_DIR")
    project_default = _project_root() / "data" / "exports" / "backtests"
    temp_base = Path(os.getenv("TEMP") or str(_project_root()))
    temp_default = temp_base / "FactorPlatformBacktests"

    candidates = [Path(override)] if override else []
    candidates.extend([project_default, temp_default])

    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe_dir = p / ".probe"
            probe_dir.mkdir(parents=True, exist_ok=True)
            probe_file = probe_dir / "write_test.txt"
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink(missing_ok=True)
            probe_dir.rmdir()
            return p
        except Exception:
            continue
    return temp_default


def new_backtest_id(prefix: str = "bt") -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    rnd = secrets.token_hex(4)
    return f"{prefix}_{ts}_{rnd}"


def _resolve_ohlcv_source() -> tuple[str, Path]:
    explicit = os.getenv("FACTOR_PLATFORM_BACKTEST_OHLCV_PATH")
    if explicit:
        p = Path(explicit)
        if p.exists():
            return "FACTOR_PLATFORM_BACKTEST_OHLCV_PATH", p

    real = os.getenv("FACTOR_PLATFORM_REAL_OHLCV_PATH")
    if real:
        p = Path(real)
        if p.exists():
            return "FACTOR_PLATFORM_REAL_OHLCV_PATH", p

    processed = _project_root() / "data" / "processed" / "daily_bar_csi300.parquet"
    if processed.exists():
        return "data/processed/daily_bar_csi300.parquet", processed

    from app.services.factor_library_master_service import _default_real_ohlcv_path

    p = _default_real_ohlcv_path()
    if p.exists():
        return "default_real_ohlcv_path", p

    raise FileNotFoundError("no ohlcv parquet found for backtest")


def _default_qlib_provider_uri(region: str) -> str:
    if region == "us":
        return os.getenv("FACTOR_PLATFORM_US_PROVIDER_URI", r"D:\mcQlib\data\qlib_bin\us_data")
    return os.getenv("FACTOR_PLATFORM_PROVIDER_URI", r"D:\mcQlib\data\qlib_bin\cn_data")


def _normalize_ai_backtest_data_source(value: str | None) -> str:
    raw = (value or os.getenv("FACTOR_PLATFORM_AI_BACKTEST_DATA_SOURCE") or "qlib").strip().lower()
    if raw in {"wind", "parquet", "ohlcv", "wind_parquet", "local_parquet"}:
        return "parquet"
    return "qlib"


def _clean_universe(values: Optional[list[str]]) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in (values or []) if str(item).strip())


def _is_cn_symbol(value: str) -> bool:
    text = value.strip().upper()
    return bool(re.match(r"^(SZ|SH|BJ)\d{6}$", text) or re.match(r"^\d{6}\.(SZ|SH|BJ)$", text) or re.match(r"^\d{6}$", text))


def _to_qlib_cn_symbol(value: str) -> str:
    text = value.strip().upper()
    match = re.match(r"^(\d{6})\.(SZ|SH|BJ)$", text)
    if match:
        return f"{match.group(2)}{match.group(1)}"
    match = re.match(r"^(SZ|SH|BJ)(\d{6})$", text)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    if re.match(r"^\d{6}$", text):
        prefix = "SH" if text.startswith(("5", "6", "9")) else "SZ"
        return f"{prefix}{text}"
    return text


def _to_qlib_us_symbol(value: str) -> str:
    return value.strip().upper()


def _infer_qlib_region(asset_class: str | None, universe: tuple[str, ...], requested_region: str | None = None) -> str:
    region = (requested_region or "").strip().lower()
    if region in {"cn", "china", "a_share", "a-share"}:
        return "cn"
    if region in {"us", "usa", "america", "sp500", "nasdaq100"}:
        return "us"

    joined = " ".join([asset_class or "", *universe]).lower()
    if any(token in joined for token in ["sp500", "s&p", "nasdaq", "nyse", "us_", "usa", "america"]):
        return "us"
    if any(_is_cn_symbol(item) for item in universe):
        return "cn"
    if universe and all(re.match(r"^[A-Za-z][A-Za-z0-9.\-]{0,9}$", item.strip()) for item in universe):
        return "us"

    env_region = os.getenv("FACTOR_PLATFORM_AI_BACKTEST_QLIB_REGION", "cn").strip().lower()
    return "us" if env_region in {"us", "usa"} else "cn"


def _extract_qlib_universe(region: str, requested: tuple[str, ...], explicit: str | None = None) -> tuple[str, tuple[str, ...]]:
    default_universe = "sp500" if region == "us" else "csi300"
    allowed = {"all", "sp500", "nasdaq100"} if region == "us" else {"all", "csi100", "csi300", "csi500", "csi800", "csi1000", "csiall"}

    if explicit and explicit.strip().lower() in allowed:
        qlib_universe = explicit.strip().lower()
    else:
        qlib_universe = default_universe

    instruments: list[str] = []
    for item in requested:
        token = item.strip()
        lower = token.lower()
        if lower in allowed:
            qlib_universe = lower
            continue
        instruments.append(token)
    return qlib_universe, tuple(instruments)


def _normalize_qlib_instruments(region: str, instruments: tuple[str, ...]) -> tuple[str, ...]:
    if region == "us":
        return tuple(dict.fromkeys(_to_qlib_us_symbol(item) for item in instruments if item.strip()))
    return tuple(dict.fromkeys(_to_qlib_cn_symbol(item) for item in instruments if item.strip()))


def resolve_ai_backtest_data_source(
    spec: Mapping[str, Any],
    *,
    universe: Optional[list[str]] = None,
    data_source: str | None = None,
    provider_uri: str | None = None,
    qlib_region: str | None = None,
    qlib_universe: str | None = None,
) -> BacktestPriceSource:
    source_kind = _normalize_ai_backtest_data_source(data_source)
    requested = _clean_universe(universe) or _clean_universe(list(spec.get("universe") or []))
    if source_kind == "parquet":
        source_id, path = _resolve_ohlcv_source()
        return BacktestPriceSource(
            kind="parquet",
            source_id=source_id,
            path=path,
            requested_universe=requested,
            instruments=requested,
        )

    region = _infer_qlib_region(str(spec.get("asset_class") or ""), requested, qlib_region)
    provider = provider_uri or _default_qlib_provider_uri(region)
    universe_name, requested_instruments = _extract_qlib_universe(region, requested, qlib_universe)
    instruments = _normalize_qlib_instruments(region, requested_instruments)
    source_id = "qlib_us_daily" if region == "us" else "qlib_cn_daily"
    return BacktestPriceSource(
        kind="qlib",
        source_id=source_id,
        provider_uri=provider,
        region=region,
        universe=universe_name,
        instruments=instruments,
        requested_universe=requested,
    )


def resolve_backtest_data_source(
    *,
    universe: Optional[list[str]] = None,
    data_source: str | None = None,
    provider_uri: str | None = None,
    qlib_region: str | None = None,
    qlib_universe: str | None = None,
) -> BacktestPriceSource:
    requested = _clean_universe(universe)
    source_kind = "parquet" if data_source is None else _normalize_ai_backtest_data_source(data_source)
    if source_kind == "parquet":
        source_id, path = _resolve_ohlcv_source()
        return BacktestPriceSource(
            kind="parquet",
            source_id=source_id,
            path=path,
            requested_universe=requested,
            instruments=requested,
        )

    region = _infer_qlib_region("equity", requested, qlib_region)
    provider = provider_uri or _default_qlib_provider_uri(region)
    universe_name, requested_instruments = _extract_qlib_universe(region, requested, qlib_universe)
    instruments = _normalize_qlib_instruments(region, requested_instruments)
    source_id = "qlib_us_daily" if region == "us" else "qlib_cn_daily"
    return BacktestPriceSource(
        kind="qlib",
        source_id=source_id,
        provider_uri=provider,
        region=region,
        universe=universe_name,
        instruments=instruments,
        requested_universe=requested,
    )


def _load_daily_bar_from_source(
    source: BacktestPriceSource,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    if source.kind == "qlib":
        if not source.provider_uri:
            raise FileNotFoundError("qlib provider_uri is not configured")
        provider = Path(source.provider_uri)
        if not provider.exists():
            raise FileNotFoundError(f"qlib provider_uri does not exist: {provider}")
        return load_qlib_daily_bar(
            str(provider),
            universe=source.universe or ("sp500" if source.region == "us" else "csi300"),
            start_date=start_date,
            end_date=end_date,
            instruments=list(source.instruments) if source.instruments else None,
        )

    if not source.path:
        raise FileNotFoundError("parquet OHLCV source is not configured")
    return _load_and_normalize_ohlcv(
        source.path,
        start_date=start_date,
        end_date=end_date,
        universe=list(source.instruments) if source.instruments else None,
    )


def _load_daily_bar(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    universe: Optional[list[str]] = None,
) -> pd.DataFrame:
    _, p = _resolve_ohlcv_source()
    return _load_and_normalize_ohlcv(p, start_date=start_date, end_date=end_date, universe=universe)


def backtest_data_status() -> dict[str, Any]:
    source_name, p = _resolve_ohlcv_source()
    dataset = _dataset(p)
    cols = list(dataset.schema.names)

    date_col = "trade_date" if "trade_date" in cols else ("date" if "date" in cols else ("datetime" if "datetime" in cols else None))
    asset_col = (
        "asset_code"
        if "asset_code" in cols
        else (
            "wind_code"
            if "wind_code" in cols
            else ("ts_code" if "ts_code" in cols else ("ticker" if "ticker" in cols else ("symbol" if "symbol" in cols else None)))
        )
    )

    row_count = int(dataset.count_rows())
    min_d: date | None = None
    max_d: date | None = None
    assets: set[str] = set()

    scan_cols = [c for c in [date_col, asset_col] if c]
    if scan_cols:
        scanner = dataset.scanner(columns=scan_cols, batch_size=200_000)
        for batch in scanner.to_batches():
            if date_col and date_col in scan_cols:
                arr = batch.column(scan_cols.index(date_col))
                bmin = pc.min(arr)
                bmax = pc.max(arr)
                if bmin.is_valid:
                    d = pd.to_datetime(bmin.as_py()).date()
                    min_d = d if min_d is None else min(min_d, d)
                if bmax.is_valid:
                    d = pd.to_datetime(bmax.as_py()).date()
                    max_d = d if max_d is None else max(max_d, d)

            if asset_col and asset_col in scan_cols and len(assets) < 200_000:
                arr = batch.column(scan_cols.index(asset_col))
                u = pc.unique(arr)
                for v in u.to_pylist():
                    if v is None:
                        continue
                    assets.add(str(v))

    return {
        "source": f"{source_name}:{p}",
        "columns": cols,
        "start_date": str(min_d) if min_d is not None else "",
        "end_date": str(max_d) if max_d is not None else "",
        "asset_count": int(len(assets)) if assets else 0,
        "row_count": row_count,
    }


def _dataset(path: Path) -> ds.Dataset:
    return ds.dataset(str(path), format="parquet")


def _read_parquet_any(path: Path, columns: list[str] | None = None, filt: ds.Expression | None = None) -> pd.DataFrame:
    dataset = _dataset(path)
    table = dataset.to_table(columns=columns, filter=filt)
    return table.to_pandas()


def _available_columns(path: Path) -> set[str]:
    return set(_dataset(path).schema.names)


def _load_and_normalize_ohlcv(
    path: Path,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    universe: Optional[list[str]] = None,
) -> pd.DataFrame:
    cols = _available_columns(path)
    pick = []
    for c in [
        "trade_date",
        "date",
        "datetime",
        "asset_code",
        "wind_code",
        "ts_code",
        "ticker",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vol",
        "adj_factor",
    ]:
        if c in cols:
            pick.append(c)

    date_col = "trade_date" if "trade_date" in cols else ("date" if "date" in cols else ("datetime" if "datetime" in cols else None))
    asset_col = (
        "asset_code"
        if "asset_code" in cols
        else (
            "wind_code"
            if "wind_code" in cols
            else ("ts_code" if "ts_code" in cols else ("ticker" if "ticker" in cols else ("symbol" if "symbol" in cols else None)))
        )
    )

    filt: ds.Expression | None = None
    apply_date_filter_in_arrow = False
    if date_col:
        try:
            t = _dataset(path).schema.field(date_col).type
            apply_date_filter_in_arrow = pa.types.is_timestamp(t) or pa.types.is_date32(t) or pa.types.is_date64(t)
        except Exception:
            apply_date_filter_in_arrow = False

    if date_col and apply_date_filter_in_arrow and (start_date is not None or end_date is not None):
        f = ds.field(date_col)
        if start_date is not None:
            filt = f >= pd.Timestamp(start_date)
        if end_date is not None:
            filt = (f <= pd.Timestamp(end_date)) if filt is None else (filt & (f <= pd.Timestamp(end_date)))

    if asset_col and universe:
        u = list(map(str, universe))
        f = ds.field(asset_col)
        asset_filter = f.isin(u)
        filt = asset_filter if filt is None else (filt & asset_filter)

    df = _read_parquet_any(path, columns=pick if pick else None, filt=filt)
    if df.empty:
        raise ValueError(f"ohlcv parquet is empty: {path}")

    rename_map: dict[str, str] = {}
    if "date" in df.columns and "trade_date" not in df.columns:
        rename_map["date"] = "trade_date"
    if "datetime" in df.columns and "trade_date" not in df.columns:
        rename_map["datetime"] = "trade_date"

    if "wind_code" in df.columns and "asset_code" not in df.columns:
        rename_map["wind_code"] = "asset_code"
    if "ts_code" in df.columns and "asset_code" not in df.columns:
        rename_map["ts_code"] = "asset_code"
    if "ticker" in df.columns and "asset_code" not in df.columns:
        rename_map["ticker"] = "asset_code"
    if "symbol" in df.columns and "asset_code" not in df.columns:
        rename_map["symbol"] = "asset_code"
    if "vol" in df.columns and "volume" not in df.columns:
        rename_map["vol"] = "volume"

    if rename_map:
        df = df.rename(columns=rename_map)

    if "trade_date" not in df.columns or "asset_code" not in df.columns:
        raise ValueError(f"ohlcv parquet missing required columns: {path}")

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["asset_code"] = df["asset_code"].astype(str)

    for c in ["open", "high", "low", "close", "volume", "adj_factor"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "close" not in df.columns:
        raise ValueError(f"ohlcv parquet missing close: {path}")

    for c in ["open", "high", "low", "volume", "adj_factor"]:
        if c not in df.columns:
            df[c] = np.nan

    df = df.dropna(subset=["trade_date", "asset_code", "close"])
    if not apply_date_filter_in_arrow:
        if start_date is not None:
            df = df[df["trade_date"] >= start_date]
        if end_date is not None:
            df = df[df["trade_date"] <= end_date]
    df = df.drop_duplicates(subset=["trade_date", "asset_code"], keep="last")
    df = df.sort_values(["asset_code", "trade_date"], kind="mergesort").reset_index(drop=True)
    return df


def _filter_prices(df: pd.DataFrame, start_date: Optional[date], end_date: Optional[date], universe: Optional[list[str]]) -> pd.DataFrame:
    out = df
    if start_date is not None:
        out = out[out["trade_date"] >= start_date]
    if end_date is not None:
        out = out[out["trade_date"] <= end_date]
    if universe:
        u = set(map(str, universe))
        out = out[out["asset_code"].astype(str).isin(u)]
    return out


class _Context:
    def __init__(self, prices: pd.DataFrame) -> None:
        self._prices = prices
        self._universe = sorted(prices["asset_code"].astype(str).unique().tolist())
        self._dates = sorted(prices["trade_date"].unique().tolist())

    def prices(self) -> pd.DataFrame:
        return self._prices

    def universe(self) -> list[str]:
        return self._universe

    def dates(self) -> list[date]:
        return self._dates


def _compute_metrics(equity: pd.Series) -> dict[str, Any]:
    eq = equity.dropna()
    if len(eq) < 3:
        return {"total_return": float(eq.iloc[-1] / eq.iloc[0] - 1.0) if len(eq) >= 2 else 0.0}

    rets = eq.pct_change().dropna()
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    ann_factor = 252.0
    ann_ret = float((1.0 + total_return) ** (ann_factor / max(len(eq) - 1, 1)) - 1.0)
    ann_vol = float(rets.std(ddof=0) * np.sqrt(ann_factor))
    sharpe = float((rets.mean() / (rets.std(ddof=0) + 1e-12)) * np.sqrt(ann_factor))

    peak = eq.cummax()
    dd = eq / peak - 1.0
    max_dd = float(dd.min())

    return {
        "total_return": total_return,
        "annual_return": ann_ret,
        "annual_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "start": str(eq.index.min()),
        "end": str(eq.index.max()),
        "bars": int(len(eq)),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if np.isnan(out) or np.isinf(out):
            return default
        return out
    except Exception:
        return default


def _simulate_positions(
    prices: pd.DataFrame,
    pos: pd.DataFrame,
    strategy_id: str,
    strategy_name: str,
    params: Mapping[str, Any],
    initial_cash: float,
    fee_bps: float,
    use_adj: bool,
    universe_size: int,
    id_prefix: str = "bt",
    metadata: Mapping[str, Any] | None = None,
) -> tuple[BacktestArtifact, dict[str, Any]]:
    if pos.empty:
        raise ValueError("strategy produced empty positions")

    requested_position_rows = int(pos.shape[0])
    pos = pos.copy()
    pos["trade_date"] = pd.to_datetime(pos["trade_date"]).dt.date
    pos["asset_code"] = pos["asset_code"].astype(str)
    pos["weight"] = pd.to_numeric(pos["weight"], errors="coerce")
    pos = pos.replace([np.inf, -np.inf], np.nan).dropna(subset=["trade_date", "asset_code", "weight"])
    pos = pos.groupby(["trade_date", "asset_code"], as_index=False)["weight"].sum()

    available_assets = set(prices["asset_code"].astype(str).unique().tolist())
    pos = pos[pos["asset_code"].isin(available_assets)]
    if pos.empty:
        raise ValueError("strategy positions do not match available price assets")
    normalized_position_rows = int(pos.shape[0])

    sim_assets = sorted(pos["asset_code"].astype(str).unique().tolist())
    prices = prices[prices["asset_code"].astype(str).isin(sim_assets)]
    price_rows = int(prices.shape[0])

    prices = prices.copy()
    if use_adj and "adj_factor" in prices.columns and prices["adj_factor"].notna().any():
        prices["close_bt"] = prices["close"] * prices["adj_factor"].fillna(1.0)
    else:
        prices["close_bt"] = prices["close"]

    close = prices.pivot(index="trade_date", columns="asset_code", values="close_bt").sort_index().ffill()
    rets = close.pct_change().fillna(0.0)

    w = pos.pivot(index="trade_date", columns="asset_code", values="weight")
    w = w.reindex(columns=close.columns)
    if len(w.index) > 0:
        w.loc[w.index] = w.loc[w.index].fillna(0.0)
    w = w.reindex(index=close.index).ffill().fillna(0.0)

    w = w.div(w.abs().sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)

    w_prev = w.shift(1).fillna(0.0)
    gross_ret = (w_prev * rets).sum(axis=1)
    turnover = (w - w_prev).abs().sum(axis=1) * 0.5
    cost = turnover * (float(fee_bps) / 10000.0)
    net_ret = gross_ret - cost
    equity = (1.0 + net_ret).cumprod() * float(initial_cash)
    prev_equity = equity.shift(1).fillna(float(initial_cash))

    metrics = _compute_metrics(equity)
    daily_net = pd.to_numeric(net_ret, errors="coerce").dropna()
    gross_exposure = w.abs().sum(axis=1)
    net_exposure = w.sum(axis=1)
    metrics.update(
        {
            "win_rate": _safe_float((daily_net > 0).mean()) if len(daily_net) else 0.0,
            "avg_daily_turnover": _safe_float(turnover.mean()),
            "max_daily_turnover": _safe_float(turnover.max()),
            "total_turnover": _safe_float(turnover.sum()),
            "total_transaction_cost": _safe_float((cost * prev_equity).sum()),
            "avg_gross_exposure": _safe_float(gross_exposure.mean()),
            "max_gross_exposure": _safe_float(gross_exposure.max()),
            "avg_net_exposure": _safe_float(net_exposure.mean()),
        }
    )

    root = _select_backtest_root()
    bt_id = new_backtest_id() if id_prefix == "bt" else new_backtest_id(id_prefix)
    bt_dir = root / bt_id
    bt_dir.mkdir(parents=True, exist_ok=True)

    equity_df = pd.DataFrame(
        {
            "trade_date": equity.index.astype(str),
            "equity": equity.values,
            "gross_ret": gross_ret.values,
            "turnover": turnover.values,
            "cost": cost.values,
            "net_ret": net_ret.values,
        }
    )
    equity_path = bt_dir / "equity_curve.parquet"
    equity_df.to_parquet(equity_path, index=False)

    positions_path = bt_dir / "positions.parquet"
    pos.to_parquet(positions_path, index=False)

    summary: dict[str, Any] = {
        "backtest_id": bt_id,
        "created_at": _now_utc(),
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "params": dict(params),
        "initial_cash": float(initial_cash),
        "fee_bps": float(fee_bps),
        "use_adj": bool(use_adj),
        "universe_size": int(universe_size),
        "metrics": metrics,
        "execution_model": {
            "signal_timestamp": "close_t",
            "execution_delay": "one_bar",
            "return_alignment": "positions from t-1 are applied to close-to-close returns on t",
            "cost_model": f"{float(fee_bps):g} bps applied to one-way turnover",
            "weight_normalization": "weights are normalized by gross absolute exposure each bar",
        },
        "diagnostics": {
            "price_rows": price_rows,
            "price_start_date": str(close.index.min()) if len(close.index) else None,
            "price_end_date": str(close.index.max()) if len(close.index) else None,
            "price_asset_count": int(len(close.columns)),
            "requested_position_rows": requested_position_rows,
            "normalized_position_rows": normalized_position_rows,
            "dropped_or_collapsed_position_rows": int(max(requested_position_rows - normalized_position_rows, 0)),
            "simulated_asset_count": int(len(sim_assets)),
            "simulated_assets_sample": sim_assets[:20],
        },
    }
    if metadata:
        summary.update(dict(metadata))
    summary_path = bt_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact = BacktestArtifact(
        backtest_id=bt_id,
        created_at=summary["created_at"],
        strategy_id=strategy_id,
        row_count=int(pos.shape[0]),
        equity_curve_path=str(equity_path),
        positions_path=str(positions_path),
        summary_path=str(summary_path),
    )
    return artifact, summary


def run_backtest(
    strategy_id: str,
    params: Mapping[str, Any],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    universe: Optional[list[str]] = None,
    initial_cash: float = 1_000_000.0,
    fee_bps: float = 5.0,
    use_adj: bool = True,
    data_source: str | None = None,
    provider_uri: str | None = None,
    qlib_region: str | None = None,
    qlib_universe: str | None = None,
) -> tuple[BacktestArtifact, dict[str, Any]]:
    ensure_strategies_loaded()
    rs = get_strategy(strategy_id)
    price_source = resolve_backtest_data_source(
        universe=universe,
        data_source=data_source,
        provider_uri=provider_uri,
        qlib_region=qlib_region,
        qlib_universe=qlib_universe,
    )
    if data_source is None:
        prices = _load_daily_bar(start_date=start_date, end_date=end_date, universe=universe)
    else:
        prices = _load_daily_bar_from_source(price_source, start_date=start_date, end_date=end_date)
    filter_universe = list(price_source.instruments) if price_source.instruments else (universe if price_source.kind == "parquet" else None)
    prices = _filter_prices(prices, start_date=start_date, end_date=end_date, universe=filter_universe)
    if prices.empty:
        raise ValueError("no price data after filtering")

    ctx = _Context(prices)
    stg = rs.strategy_cls()
    pos = stg.run(ctx, params)
    metadata = {
        "price_data_source": price_source.public_dict(),
        "timing_note": "Strategy signals are evaluated on bar t; simulation applies positions with a one-bar return delay.",
    }
    return _simulate_positions(
        prices=prices,
        pos=pos,
        strategy_id=rs.info.strategy_id,
        strategy_name=rs.info.strategy_name,
        params=params,
        initial_cash=initial_cash,
        fee_bps=fee_bps,
        use_adj=use_adj,
        universe_size=len(ctx.universe()),
        metadata=metadata,
    )


_AI_RULE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<|==|!=)\s*([A-Za-z_][A-Za-z0-9_]*|-?\d+(?:\.\d+)?)\s*$")


def run_strategy_spec_backtest(
    spec: Mapping[str, Any],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    universe: Optional[list[str]] = None,
    initial_cash: float = 1_000_000.0,
    fee_bps: float | None = None,
    use_adj: bool = True,
    data_source: str | None = None,
    provider_uri: str | None = None,
    qlib_region: str | None = None,
    qlib_universe: str | None = None,
) -> tuple[BacktestArtifact, dict[str, Any]]:
    from app.api.schemas.strategy_ai import StrategySpec

    strategy_spec = StrategySpec.model_validate(spec)
    validation = validate_strategy_spec(strategy_spec)
    if not validation.is_valid:
        errors = [x.message for x in validation.issues if x.severity == "error"]
        raise ValueError("invalid AI strategy spec: " + "; ".join(errors))
    strategy_spec = validation.normalized_spec

    price_universe = universe or strategy_spec.universe or None
    price_source = resolve_ai_backtest_data_source(
        strategy_spec.model_dump(),
        universe=price_universe,
        data_source=data_source,
        provider_uri=provider_uri,
        qlib_region=qlib_region,
        qlib_universe=qlib_universe,
    )
    prices = _load_daily_bar_from_source(price_source, start_date=start_date, end_date=end_date)
    filter_universe = list(price_source.instruments) if price_source.instruments else None
    prices = _filter_prices(prices, start_date=start_date, end_date=end_date, universe=filter_universe)
    if prices.empty:
        raise ValueError("no price data after filtering")

    positions = _positions_from_strategy_spec(prices, strategy_spec.model_dump())
    metadata = {
        "source": "ai_strategy_spec",
        "strategy_spec": strategy_spec.model_dump(),
        "validation": validation.model_dump(),
        "price_data_source": price_source.public_dict(),
        "timing_note": "AI StrategySpec signals are formed after close_t; simulation applies positions with a one-bar return delay.",
    }
    return _simulate_positions(
        prices=prices,
        pos=positions,
        strategy_id="ai_strategy_spec",
        strategy_name=strategy_spec.name,
        params={
            "entry_rules": strategy_spec.entry_rules,
            "exit_rules": strategy_spec.exit_rules,
            "ranking": strategy_spec.ranking,
            "max_positions": strategy_spec.risk.max_positions,
        },
        initial_cash=initial_cash,
        fee_bps=float(fee_bps if fee_bps is not None else strategy_spec.execution.fee_bps),
        use_adj=use_adj,
        universe_size=int(prices["asset_code"].nunique()),
        id_prefix="ai_bt",
        metadata=metadata,
    )


def _positions_from_strategy_spec(prices: pd.DataFrame, spec: Mapping[str, Any]) -> pd.DataFrame:
    px = prices.copy()
    px = px.sort_values(["asset_code", "trade_date"], kind="mergesort").reset_index(drop=True)
    px = _add_strategy_spec_indicators(px, spec)

    entry = pd.Series(True, index=px.index)
    for rule in spec.get("entry_rules") or []:
        entry = entry & _evaluate_ai_rule(px, str(rule))

    exit_mask = pd.Series(False, index=px.index)
    for rule in spec.get("exit_rules") or []:
        exit_mask = exit_mask | _evaluate_ai_rule(px, str(rule))

    eligible = px[entry & ~exit_mask].copy()
    eligible = eligible.dropna(subset=["trade_date", "asset_code"])
    if eligible.empty:
        raise ValueError("AI strategy spec produced no eligible positions")

    ranking = spec.get("ranking")
    max_positions = int(((spec.get("risk") or {}).get("max_positions")) or 10)
    max_positions = max(max_positions, 1)

    rows: list[dict[str, Any]] = []
    for trade_date, day in eligible.groupby("trade_date", sort=True):
        day = day.copy()
        if ranking and ranking in day.columns:
            day[ranking] = pd.to_numeric(day[ranking], errors="coerce")
            day = day.dropna(subset=[ranking]).sort_values(ranking, ascending=False)
        else:
            day = day.sort_values("asset_code")
        day = day.head(max_positions)
        if day.empty:
            continue
        weight = 1.0 / float(len(day))
        for asset in day["asset_code"].astype(str).tolist():
            rows.append({"trade_date": trade_date, "asset_code": asset, "weight": weight})

    if not rows:
        raise ValueError("AI strategy spec produced no positions after ranking")
    return pd.DataFrame(rows)


def _add_strategy_spec_indicators(px: pd.DataFrame, spec: Mapping[str, Any]) -> pd.DataFrame:
    out = px.copy()
    if "volume" not in out.columns:
        out["volume"] = np.nan

    for indicator in spec.get("indicators") or []:
        typ = str(indicator.get("type") or "").strip().lower()
        name = indicator_alias(type("_Indicator", (), indicator)())
        window = int(indicator.get("window") or 0)
        field = str(indicator.get("field") or "close").strip().lower()
        if field not in out.columns:
            raise ValueError(f"indicator field not available: {field}")

        series = pd.to_numeric(out[field], errors="coerce")
        grouped = series.groupby(out["asset_code"], sort=False)
        if typ == "sma":
            out[name] = grouped.transform(lambda s: s.rolling(window, min_periods=window).mean())
        elif typ == "ema":
            out[name] = grouped.transform(lambda s: s.ewm(span=window, adjust=False, min_periods=window).mean())
        elif typ == "momentum":
            out[name] = grouped.transform(lambda s: s.pct_change(window))
        elif typ == "volatility":
            returns = grouped.transform(lambda s: s.pct_change())
            out[name] = returns.groupby(out["asset_code"], sort=False).transform(
                lambda s: s.rolling(window, min_periods=window).std(ddof=0) * np.sqrt(252.0)
            )
        elif typ == "atr":
            prev_close = out.groupby("asset_code", sort=False)["close"].shift(1)
            high = pd.to_numeric(out["high"], errors="coerce").fillna(out["close"])
            low = pd.to_numeric(out["low"], errors="coerce").fillna(out["close"])
            tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
            out[name] = tr.groupby(out["asset_code"], sort=False).transform(lambda s: s.rolling(window, min_periods=window).mean())
        elif typ == "rsi":
            delta = grouped.transform(lambda s: s.diff())
            gain = delta.clip(lower=0.0)
            loss = (-delta.clip(upper=0.0))
            avg_gain = gain.groupby(out["asset_code"], sort=False).transform(lambda s: s.rolling(window, min_periods=window).mean())
            avg_loss = loss.groupby(out["asset_code"], sort=False).transform(lambda s: s.rolling(window, min_periods=window).mean())
            rs = avg_gain / avg_loss.replace(0.0, np.nan)
            out[name] = 100.0 - (100.0 / (1.0 + rs))
        else:
            raise ValueError(f"unsupported indicator type: {typ}")

    return out


def _evaluate_ai_rule(px: pd.DataFrame, rule: str) -> pd.Series:
    match = _AI_RULE_RE.match(rule)
    if not match:
        raise ValueError(f"unsupported AI strategy rule: {rule}")

    lhs, op, rhs_token = match.group(1), match.group(2), match.group(3)
    if lhs not in px.columns:
        raise ValueError(f"unknown rule field: {lhs}")
    lhs_s = pd.to_numeric(px[lhs], errors="coerce")
    if rhs_token in px.columns:
        rhs: pd.Series | float = pd.to_numeric(px[rhs_token], errors="coerce")
    else:
        rhs = float(rhs_token)

    if op == ">":
        return (lhs_s > rhs).fillna(False)
    if op == ">=":
        return (lhs_s >= rhs).fillna(False)
    if op == "<":
        return (lhs_s < rhs).fillna(False)
    if op == "<=":
        return (lhs_s <= rhs).fillna(False)
    if op == "==":
        return (lhs_s == rhs).fillna(False)
    if op == "!=":
        return (lhs_s != rhs).fillna(False)
    raise ValueError(f"unsupported AI strategy rule operator: {op}")


def run_portfolio_backtest(
    portfolio_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    universe: Optional[list[str]] = None,
    initial_cash: float = 1_000_000.0,
    fee_bps: float = 5.0,
    use_adj: bool = True,
) -> tuple[BacktestArtifact, dict[str, Any]]:
    from app.services.native_qlib_research_service import get_portfolio, read_portfolio_signals

    portfolio = get_portfolio(portfolio_id)
    signals = read_portfolio_signals(portfolio_id)
    if signals.empty:
        raise ValueError("portfolio signal artifact is empty")

    if start_date is not None:
        signals = signals[signals["trade_date"] >= start_date]
    if end_date is not None:
        signals = signals[signals["trade_date"] <= end_date]
    if signals.empty:
        raise ValueError("portfolio has no signals after date filtering")

    signal_assets = sorted(signals["asset_code"].astype(str).unique().tolist())
    price_universe = universe or signal_assets
    portfolio_provider = str(portfolio.get("provider_uri") or "").strip()
    if portfolio_provider:
        provider_lower = portfolio_provider.lower()
        portfolio_universe = str(portfolio.get("universe") or "").strip().lower() or None
        region = _infer_qlib_region("equity", tuple([*(price_universe or []), portfolio_universe or ""]), None)
        if "us_data" in provider_lower or portfolio_universe in {"sp500", "nasdaq100"}:
            region = "us"
        instruments = _normalize_qlib_instruments(region, tuple(price_universe or []))
        price_source = BacktestPriceSource(
            kind="qlib",
            source_id="qlib_us_daily" if region == "us" else "qlib_cn_daily",
            provider_uri=portfolio_provider,
            region=region,
            universe=portfolio_universe or ("sp500" if region == "us" else "csi300"),
            instruments=instruments,
            requested_universe=tuple(price_universe or []),
        )
        prices = _load_daily_bar_from_source(price_source, start_date=start_date, end_date=end_date)
        prices = _filter_prices(
            prices,
            start_date=start_date,
            end_date=end_date,
            universe=list(price_source.instruments) if price_source.instruments else None,
        )
    else:
        price_source = resolve_backtest_data_source(universe=price_universe, data_source=None)
        prices = _load_daily_bar(start_date=start_date, end_date=end_date, universe=price_universe)
        prices = _filter_prices(prices, start_date=start_date, end_date=end_date, universe=price_universe)
    if prices.empty:
        raise ValueError("no price data after filtering")

    params = {
        "portfolio_id": portfolio_id,
        "mining_run_id": portfolio.get("mining_run_id"),
        "selected_factors": portfolio.get("selected_factors"),
        "weighting_method": portfolio.get("weighting_method"),
    }
    metadata = {
        "portfolio_id": portfolio_id,
        "source_signal_artifact_path": portfolio.get("signal_artifact_path"),
        "price_data_source": price_source.public_dict(),
        "timing_note": portfolio.get(
            "timing_note",
            "Portfolio signal trade_date is already next-day effective; backtest applies positions after one more close-to-close shift.",
        ),
    }
    return _simulate_positions(
        prices=prices,
        pos=signals[["trade_date", "asset_code", "weight"]],
        strategy_id="qlib_portfolio",
        strategy_name=f"Qlib Factor Portfolio ({portfolio_id})",
        params=params,
        initial_cash=initial_cash,
        fee_bps=fee_bps,
        use_adj=use_adj,
        universe_size=len(price_universe),
        id_prefix="btp",
        metadata=metadata,
    )


def list_backtests(limit: int = 50) -> list[dict[str, Any]]:
    root = _select_backtest_root()
    if not root.exists():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir()]
    dirs = sorted(dirs, key=lambda p: p.name, reverse=True)[: max(int(limit), 0)]
    out: list[dict[str, Any]] = []
    for d in dirs:
        sp = d / "summary.json"
        if not sp.exists():
            continue
        try:
            out.append(json.loads(sp.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _backtest_dir(backtest_id: str) -> Path:
    if not re.match(r"^[A-Za-z0-9_.-]+$", str(backtest_id)):
        raise ValueError("invalid backtest_id")
    return _select_backtest_root() / str(backtest_id)


def read_backtest_summary(backtest_id: str) -> dict[str, Any]:
    p = _backtest_dir(backtest_id) / "summary.json"
    if not p.exists():
        raise FileNotFoundError(f"backtest summary not found: {backtest_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def read_equity_curve(backtest_id: str) -> pd.DataFrame:
    p = _backtest_dir(backtest_id) / "equity_curve.parquet"
    if not p.exists():
        raise FileNotFoundError(f"backtest equity curve not found: {backtest_id}")
    return pd.read_parquet(p)
