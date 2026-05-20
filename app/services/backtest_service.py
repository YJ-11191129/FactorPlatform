from __future__ import annotations

import json
import os
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

from app.services.strategy_service import ensure_strategies_loaded
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

    sim_assets = sorted(pos["asset_code"].astype(str).unique().tolist())
    prices = prices[prices["asset_code"].astype(str).isin(sim_assets)]

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

    root = _select_backtest_root()
    bt_id = new_backtest_id() if id_prefix == "bt" else new_backtest_id(id_prefix)
    bt_dir = root / bt_id
    bt_dir.mkdir(parents=True, exist_ok=True)

    equity_df = pd.DataFrame({"trade_date": equity.index.astype(str), "equity": equity.values, "net_ret": net_ret.values})
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
        "metrics": _compute_metrics(equity),
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
) -> tuple[BacktestArtifact, dict[str, Any]]:
    ensure_strategies_loaded()
    rs = get_strategy(strategy_id)
    prices = _load_daily_bar(start_date=start_date, end_date=end_date, universe=universe)
    prices = _filter_prices(prices, start_date=start_date, end_date=end_date, universe=universe)
    if prices.empty:
        raise ValueError("no price data after filtering")

    ctx = _Context(prices)
    stg = rs.strategy_cls()
    pos = stg.run(ctx, params)
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
    )


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


def read_equity_curve(backtest_id: str) -> pd.DataFrame:
    root = _select_backtest_root()
    p = root / backtest_id / "equity_curve.parquet"
    return pd.read_parquet(p)
