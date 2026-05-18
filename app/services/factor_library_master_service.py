from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from app.factors.registry import ensure_registered, get_factor
from app.services.factor_service import DEFAULT_FACTOR_MODULES, list_factor_infos


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _artifact_root() -> Path:
    p = _project_root() / "data" / "exports" / "factor_library"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _factor_registry_path() -> Path:
    return _artifact_root() / "factor_registry.parquet"


def _strategy_registry_path() -> Path:
    return _artifact_root() / "strategy_registry.parquet"


def _factor_values_path() -> Path:
    return _artifact_root() / "factor_values.parquet"


def _screened_latest_path() -> Path:
    return _artifact_root() / "screened_universe_latest.parquet"


def _screened_history_path() -> Path:
    return _artifact_root() / "screened_universe_history.parquet"


def _now_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _today() -> str:
    return date.today().isoformat()


def _default_real_ohlcv_path() -> Path:
    return Path("D:/Kaggle/Data/wind_data/02_daily_stock/stock_daily_ohlcv.parquet")


def _default_master_root() -> Path:
    p1 = Path("D:/Kaggle/data/wind_data/01_master")
    if p1.exists():
        return p1
    return Path("D:/Kaggle/Data/wind_data/01_master")


def _default_financial_statement_path() -> Path:
    p1 = Path("D:/Kaggle/data/processed/financial_statement.parquet")
    if p1.exists():
        return p1
    return Path("D:/Kaggle/Data/processed/financial_statement.parquet")


def _load_daily_bar_local() -> pd.DataFrame:
    p = Path(os.getenv("FACTOR_PLATFORM_REAL_OHLCV_PATH", str(_default_real_ohlcv_path())))
    if not p.exists():
        raise FileNotFoundError(f"daily ohlcv parquet not found: {p}")
    try:
        df = pd.read_parquet(p, columns=["date", "wind_code", "close"])
        df = df.rename(columns={"date": "trade_date", "wind_code": "asset_code"})
    except Exception:
        df = pd.read_parquet(p, columns=["trade_date", "asset_code", "close"])
        df = df.rename(columns={"trade_date": "trade_date", "asset_code": "asset_code"})
    if df.empty:
        raise ValueError(f"daily ohlcv parquet is empty: {p}")
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["asset_code"] = df["asset_code"].astype(str)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["trade_date", "asset_code", "close"])
    df = df.sort_values(["asset_code", "trade_date"], kind="mergesort").reset_index(drop=True)
    return df


def _build_factor_registry_df() -> pd.DataFrame:
    ensure_registered(DEFAULT_FACTOR_MODULES)
    rows: list[dict[str, Any]] = []
    ts = _now_utc()
    for fi in list_factor_infos():
        rf = get_factor(fi.factor_name)
        py_entry = f"{rf.factor_cls.__module__}:{rf.factor_cls.__name__}"
        lookback = None
        if isinstance(fi.parameter_schema, Mapping):
            n_def = fi.parameter_schema.get("n")
            if isinstance(n_def, Mapping):
                lookback = n_def.get("default")
        rows.append(
            {
                "factor_id": fi.factor_name.lower(),
                "factor_name": fi.factor_name,
                "factor_group": fi.category,
                "factor_family": fi.category,
                "description": fi.description,
                "formula_text": fi.description,
                "python_entry": py_entry,
                "skill_id": f"skills/factors/{fi.factor_name.lower()}",
                "input_fields": list(fi.dependencies),
                "required_tables": ["daily_bar"],
                "parameters_schema": dict(fi.parameter_schema),
                "lookback_window": int(lookback) if lookback is not None else None,
                "rebalance_frequency": "1D",
                "value_type": "float",
                "is_cross_sectional": True,
                "supports_neutralization": True,
                "supports_standardization": True,
                "default_direction": "high",
                "asset_scope": "A_SHARE",
                "market_scope": "CN",
                "status": "ACTIVE",
                "version": fi.version,
                "owner": "research",
                "created_at": ts,
                "updated_at": ts,
            }
        )
    return pd.DataFrame(rows)


def _build_strategy_registry_df() -> pd.DataFrame:
    ts = _now_utc()
    rows = [
        {
            "strategy_id": "stg_mom_ma_v1",
            "strategy_name": "Momentum + MA Bias",
            "description": "Simple technical combo strategy template.",
            "strategy_type": "stock_selection",
            "skill_id": "skills/strategies/mom_ma_v1",
            "factor_list": ["MOM_RET_N_D_V1", "TREND_MA_BIAS_N_D_V1"],
            "universe_rule": "A_SHARE_ALL",
            "risk_template": "basic_vol_control",
            "status": "ACTIVE",
            "version": "v1",
            "owner": "research",
            "created_at": ts,
            "updated_at": ts,
        },
        {
            "strategy_id": "stg_defensive_geo_v1",
            "strategy_name": "Geo-Energy Defensive",
            "description": "Defensive routing template for geo-energy shock windows.",
            "strategy_type": "regime_router",
            "skill_id": "skills/strategies/geo_energy_defensive",
            "factor_list": ["MOM_RET_N_D_V1"],
            "universe_rule": "A_SHARE_EX_ST",
            "risk_template": "geo_energy_defensive_template",
            "status": "ACTIVE",
            "version": "v1",
            "owner": "research",
            "created_at": ts,
            "updated_at": ts,
        },
    ]
    return pd.DataFrame(rows)


def ensure_registry_tables() -> None:
    fp = _factor_registry_path()
    sp = _strategy_registry_path()
    if not fp.exists():
        _build_factor_registry_df().to_parquet(fp, index=False)
    if not sp.exists():
        _build_strategy_registry_df().to_parquet(sp, index=False)


def list_factor_registry() -> pd.DataFrame:
    try:
        from sqlalchemy import select

        from app.db.session import db_session
        from app.models.factor_metadata import FactorMetadata

        with db_session() as db:
            rows = list(db.scalars(select(FactorMetadata).order_by(FactorMetadata.factor_name)).all())
        if rows:
            ts = _now_utc()
            out_rows: list[dict[str, Any]] = []
            for r in rows:
                out_rows.append(
                    {
                        "factor_id": r.factor_name.lower(),
                        "factor_name": r.factor_name,
                        "factor_group": r.category,
                        "factor_family": r.category,
                        "description": r.description,
                        "formula_text": r.description,
                        "python_entry": r.python_entry,
                        "skill_id": f"skills/factors/{r.factor_name.lower()}",
                        "input_fields": list(r.dependencies or []),
                        "required_tables": ["daily_bar"],
                        "parameters_schema": dict(r.parameter_schema or {}),
                        "lookback_window": None,
                        "rebalance_frequency": "1D",
                        "value_type": "float",
                        "is_cross_sectional": True,
                        "supports_neutralization": True,
                        "supports_standardization": True,
                        "default_direction": "high",
                        "asset_scope": "A_SHARE",
                        "market_scope": "CN",
                        "status": r.status,
                        "version": r.version,
                        "owner": r.owner,
                        "created_at": ts,
                        "updated_at": ts,
                    }
                )
            return pd.DataFrame(out_rows).sort_values("factor_name").reset_index(drop=True)
    except Exception:
        pass

    ensure_registry_tables()
    return pd.read_parquet(_factor_registry_path()).sort_values("factor_name").reset_index(drop=True)


def list_strategy_registry() -> pd.DataFrame:
    ensure_registry_tables()
    return pd.read_parquet(_strategy_registry_path()).sort_values("strategy_id").reset_index(drop=True)


def _winsorize_by_date(s: pd.Series) -> pd.Series:
    q1 = s.quantile(0.01)
    q99 = s.quantile(0.99)
    return s.clip(lower=q1, upper=q99)


def _zscore_by_date(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    if sd == 0 or not np.isfinite(sd):
        return pd.Series(np.zeros(len(s), dtype=float), index=s.index)
    return (s - s.mean()) / sd


def _append_parquet(path: Path, df: pd.DataFrame) -> None:
    if path.exists():
        old = pd.read_parquet(path)
        out = pd.concat([old, df], axis=0, ignore_index=True)
    else:
        out = df.copy()
    out.to_parquet(path, index=False)


def compute_and_store_factor_values(
    factor_name: str,
    params: Mapping[str, Any] | None = None,
    universe_name: str = "A_SHARE_ALL",
    factor_version: str = "V1",
    start_date: date | None = None,
    end_date: date | None = None,
    instrument_limit: int | None = 200,
) -> dict[str, Any]:
    ensure_registered(DEFAULT_FACTOR_MODULES)
    rf = get_factor(factor_name)
    p = dict(params or {})
    daily_bar = _load_daily_bar_local()
    if start_date is not None:
        daily_bar = daily_bar[daily_bar["trade_date"] >= start_date]
    if end_date is not None:
        daily_bar = daily_bar[daily_bar["trade_date"] <= end_date]
    if instrument_limit is not None:
        codes = daily_bar["asset_code"].drop_duplicates().head(max(1, int(instrument_limit)))
        daily_bar = daily_bar[daily_bar["asset_code"].isin(codes)]
    if daily_bar.empty:
        raise ValueError("daily_bar is empty after applying start/end/instrument_limit filters")

    raw = rf.factor_cls.compute(daily_bar=daily_bar, params=p)
    raw = raw.rename(columns={"factor_value": "raw_value"}).copy()
    raw["trade_date"] = pd.to_datetime(raw["trade_date"]).dt.date

    x = raw.copy()
    x["winsorized_value"] = x.groupby("trade_date", group_keys=False)["raw_value"].apply(_winsorize_by_date)
    x["zscore_value"] = x.groupby("trade_date", group_keys=False)["winsorized_value"].apply(_zscore_by_date)
    x["neutralized_value"] = x["zscore_value"]
    calc_batch_id = f"flib_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
    x["factor_name"] = factor_name
    x["factor_version"] = factor_version
    x["universe_name"] = universe_name
    x["calc_batch_id"] = calc_batch_id
    x["computed_at"] = _now_utc()
    if "asset_code" in x.columns and "wind_code" not in x.columns:
        x["wind_code"] = x["asset_code"]
    out = x[
        [
            "trade_date",
            "asset_code",
            "wind_code",
            "factor_name",
            "factor_version",
            "raw_value",
            "winsorized_value",
            "zscore_value",
            "neutralized_value",
            "universe_name",
            "calc_batch_id",
            "computed_at",
        ]
    ].copy()

    run_dir = _artifact_root() / "runs" / calc_batch_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_values_path = run_dir / "factor_values.parquet"
    out.to_parquet(run_values_path, index=False)
    _append_parquet(_factor_values_path(), out)
    try:
        from app.db.session import db_session
        from app.models.factor_run import FactorRun

        with db_session() as db:
            db.add(
                FactorRun(
                    calc_batch_id=calc_batch_id,
                    factor_name=factor_name,
                    factor_version=factor_version,
                    mode="factor_library",
                    params=dict(p),
                    universe_name=universe_name,
                    provider_uri=None,
                    start_date=start_date,
                    end_date=end_date,
                    instrument_limit=instrument_limit,
                    artifact_path=str(run_values_path),
                    row_count=int(out.shape[0]),
                    status="SUCCESS",
                    error=None,
                )
            )
    except Exception:
        pass
    return {
        "factor_name": factor_name,
        "calc_batch_id": calc_batch_id,
        "row_count": int(out.shape[0]),
        "factor_values_path": str(run_values_path),
        "computed_at": out["computed_at"].iloc[0],
    }


def read_factor_values(
    factor_name: str | None = None,
    trade_date: str | None = None,
    limit: int = 200,
) -> pd.DataFrame:
    p = _factor_values_path()
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    if factor_name:
        df = df[df["factor_name"] == factor_name]
    if trade_date:
        td = pd.to_datetime(trade_date).date()
        df = df[pd.to_datetime(df["trade_date"]).dt.date == td]
    code_col = "wind_code" if "wind_code" in df.columns else ("asset_code" if "asset_code" in df.columns else None)
    if code_col is None:
        df = df.sort_values(["trade_date"], ascending=[False])
    else:
        df = df.sort_values(["trade_date", code_col], ascending=[False, True])
    return df.head(max(1, int(limit))).reset_index(drop=True)


def run_stock_screen(
    min_market_cap: float | None = None,
    max_market_cap: float | None = None,
    min_listed_days: int | None = 250,
    exclude_st: bool = True,
    trade_status: str = "交易",
    min_roe_avg: float | None = None,
    min_oper_rev_growth_ttm: float | None = None,
    min_net_profit_growth_ttm: float | None = None,
    max_debt_to_asset: float | None = None,
    topn: int = 2000,
) -> dict[str, Any]:
    base = _default_master_root()
    p_flags = Path(os.getenv("FACTOR_PLATFORM_TRADABLE_FLAGS_PATH", str(base / "tradable_flags.parquet")))
    p_uni = Path(os.getenv("FACTOR_PLATFORM_UNIVERSE_PATH", str(base / "a_share_universe.parquet")))
    p_fin = Path(
        os.getenv(
            "FACTOR_PLATFORM_FINANCIAL_STATEMENT_PATH",
            str(_default_financial_statement_path()),
        )
    )
    if not p_flags.exists() or not p_uni.exists():
        raise FileNotFoundError("tradable_flags or a_share_universe parquet not found")

    flags = pd.read_parquet(p_flags)
    uni = pd.read_parquet(p_uni)
    df = uni.merge(flags, on="wind_code", how="left")
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    asof = pd.to_datetime(df["snapshot_date"]).dt.date.max()
    df = df[df["snapshot_date"] == asof].copy()
    df["ipo_date"] = pd.to_datetime(df["ipo_date"], errors="coerce").dt.date
    df["listed_days"] = (pd.to_datetime(asof) - pd.to_datetime(df["ipo_date"])).dt.days

    financial_rows_used = 0
    financial_coverage_ratio = 0.0
    if p_fin.exists():
        fin_cols = [
            "wind_code",
            "report_date",
            "roe_avg",
            "oper_rev_growth_ttm",
            "net_profit_growth_ttm",
            "tot_assets",
            "tot_liab",
        ]
        fin = pd.read_parquet(p_fin, columns=fin_cols)
        if not fin.empty:
            fin["report_date"] = pd.to_datetime(fin["report_date"], errors="coerce").dt.date
            fin = fin.dropna(subset=["wind_code", "report_date"]).copy()
            fin = fin[fin["report_date"] <= asof]
            fin = fin.sort_values(["wind_code", "report_date"], kind="mergesort")
            fin = fin.drop_duplicates(subset=["wind_code"], keep="last")
            df = df.merge(fin, on="wind_code", how="left")
            ta = pd.to_numeric(df["tot_assets"], errors="coerce")
            tl = pd.to_numeric(df["tot_liab"], errors="coerce")
            with np.errstate(divide="ignore", invalid="ignore"):
                df["debt_to_asset"] = np.where(ta > 0, tl / ta, np.nan)
            financial_rows_used = int(fin.shape[0])
            financial_coverage_ratio = float(df["report_date"].notna().mean())

    if "report_date" not in df.columns:
        df["report_date"] = pd.NaT
        df["roe_avg"] = np.nan
        df["oper_rev_growth_ttm"] = np.nan
        df["net_profit_growth_ttm"] = np.nan
        df["tot_assets"] = np.nan
        df["tot_liab"] = np.nan
        df["debt_to_asset"] = np.nan

    if trade_status:
        df = df[df["trade_status"] == trade_status]
    if exclude_st:
        riskwarning = df["riskwarning"].astype(str).str.strip()
        st_true_values = {"\u662f", "Y", "1", "true", "True"}
        df = df[~riskwarning.isin(st_true_values)]
    if min_market_cap is not None:
        df = df[pd.to_numeric(df["mkt_cap_ard"], errors="coerce") >= float(min_market_cap)]
    if max_market_cap is not None:
        df = df[pd.to_numeric(df["mkt_cap_ard"], errors="coerce") <= float(max_market_cap)]
    if min_listed_days is not None:
        df = df[pd.to_numeric(df["listed_days"], errors="coerce") >= int(min_listed_days)]
    if min_roe_avg is not None:
        df = df[pd.to_numeric(df["roe_avg"], errors="coerce") >= float(min_roe_avg)]
    if min_oper_rev_growth_ttm is not None:
        df = df[pd.to_numeric(df["oper_rev_growth_ttm"], errors="coerce") >= float(min_oper_rev_growth_ttm)]
    if min_net_profit_growth_ttm is not None:
        df = df[
            pd.to_numeric(df["net_profit_growth_ttm"], errors="coerce")
            >= float(min_net_profit_growth_ttm)
        ]
    if max_debt_to_asset is not None:
        df = df[pd.to_numeric(df["debt_to_asset"], errors="coerce") <= float(max_debt_to_asset)]

    df = df.sort_values("mkt_cap_ard", ascending=False).head(max(1, int(topn))).copy()
    screen_rule_id = f"screen_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
    df["screen_rule_id"] = screen_rule_id
    df["asof_date"] = str(asof)
    df["computed_at"] = _now_utc()
    out = df[
        [
            "wind_code",
            "sec_name",
            "trade_status",
            "riskwarning",
            "ipo_date",
            "listed_days",
            "mkt_cap_ard",
            "report_date",
            "roe_avg",
            "oper_rev_growth_ttm",
            "net_profit_growth_ttm",
            "tot_assets",
            "tot_liab",
            "debt_to_asset",
            "screen_rule_id",
            "asof_date",
            "computed_at",
        ]
    ].reset_index(drop=True)

    out.to_parquet(_screened_latest_path(), index=False)
    _append_parquet(_screened_history_path(), out)
    return {
        "screen_rule_id": screen_rule_id,
        "asof_date": str(asof),
        "row_count": int(out.shape[0]),
        "latest_path": str(_screened_latest_path()),
        "history_path": str(_screened_history_path()),
        "financial_statement_path": str(p_fin),
        "financial_rows_used": financial_rows_used,
        "financial_coverage_ratio": financial_coverage_ratio,
    }
def read_screened_universe_latest(limit: int = 200) -> pd.DataFrame:
    p = _screened_latest_path()
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    return df.head(max(1, int(limit))).reset_index(drop=True)
