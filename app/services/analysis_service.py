from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from app.db.session import db_session
from app.models.analysis_result import AnalysisResult
from app.models.factor_run import FactorRun
from app.core.settings import get_settings


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _artifact_root() -> Path:
    p = _project_root() / "data" / "exports" / "factor_library"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_daily_close() -> pd.DataFrame:
    p = os.getenv("FACTOR_PLATFORM_REAL_OHLCV_PATH")
    candidates: list[Path] = []
    if p:
        candidates.append(Path(p))
    candidates.append(_project_root() / "data" / "processed" / "daily_bar_csi300.parquet")
    for c in candidates:
        if not c.exists():
            continue
        df = pd.read_parquet(c)
        cols = set(df.columns)
        if {"trade_date", "asset_code", "close"}.issubset(cols):
            out = df[["trade_date", "asset_code", "close"]].copy()
            out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
            out["asset_code"] = out["asset_code"].astype(str)
            out["close"] = pd.to_numeric(out["close"], errors="coerce")
            return out.dropna(subset=["trade_date", "asset_code", "close"]).sort_values(
                ["asset_code", "trade_date"], kind="mergesort"
            )
        if {"date", "wind_code", "close"}.issubset(cols):
            out = df[["date", "wind_code", "close"]].rename(columns={"date": "trade_date", "wind_code": "asset_code"})
            out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
            out["asset_code"] = out["asset_code"].astype(str)
            out["close"] = pd.to_numeric(out["close"], errors="coerce")
            return out.dropna(subset=["trade_date", "asset_code", "close"]).sort_values(
                ["asset_code", "trade_date"], kind="mergesort"
            )
    raise FileNotFoundError("daily close parquet not found; set FACTOR_PLATFORM_REAL_OHLCV_PATH or provide data/processed/daily_bar_csi300.parquet")


def _resolve_factor_values_path(calc_batch_id: str) -> Path:
    p = _artifact_root() / "runs" / calc_batch_id / "factor_values.parquet"
    if p.exists():
        return p

    try:
        with db_session() as db:
            r = db.get(FactorRun, calc_batch_id)
        if r is not None and r.artifact_path:
            p = Path(r.artifact_path)
            if p.exists():
                return p
    except Exception:
        pass
    raise FileNotFoundError(f"factor values artifact not found for calc_batch_id={calc_batch_id}")


def _forward_return(close_df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    if horizon <= 0:
        raise ValueError("horizon must be >= 1")
    x = close_df.copy()
    x["close"] = pd.to_numeric(x["close"], errors="coerce")
    x = x.dropna(subset=["close"]).copy()
    x["future_close"] = x.groupby("asset_code", group_keys=False)["close"].shift(-horizon)
    with np.errstate(divide="ignore", invalid="ignore"):
        x["fwd_ret"] = x["future_close"] / x["close"] - 1.0
    out = x.dropna(subset=["fwd_ret"])[["trade_date", "asset_code", "fwd_ret"]].copy()
    return out


def run_single_factor_analysis(
    calc_batch_id: str,
    horizon: int = 1,
    quantiles: int = 5,
    value_col: str = "neutralized_value",
) -> dict[str, Any]:
    factor_path = _resolve_factor_values_path(calc_batch_id)
    fv = pd.read_parquet(factor_path)
    if fv.empty:
        raise ValueError("factor values is empty")
    fv["trade_date"] = pd.to_datetime(fv["trade_date"]).dt.date
    if "asset_code" not in fv.columns and "wind_code" in fv.columns:
        fv["asset_code"] = fv["wind_code"].astype(str)
    fv["asset_code"] = fv["asset_code"].astype(str)
    if value_col not in fv.columns:
        raise ValueError(f"value_col not found: {value_col}")

    close_df = _load_daily_close()
    ret = _forward_return(close_df, horizon=horizon)
    m = fv.merge(ret, on=["trade_date", "asset_code"], how="inner")
    m = m.dropna(subset=[value_col, "fwd_ret"]).copy()
    if m.empty:
        raise ValueError("no overlapping rows between factor values and forward returns")

    def _corr_one(g: pd.DataFrame) -> dict[str, Any]:
        s = pd.to_numeric(g[value_col], errors="coerce")
        r = pd.to_numeric(g["fwd_ret"], errors="coerce")
        ok = s.notna() & r.notna()
        s, r = s[ok], r[ok]
        if len(s) < 5:
            return {"ic": np.nan, "rank_ic": np.nan, "n": int(len(s))}
        ic = float(s.corr(r, method="pearson"))
        ric = float(s.corr(r, method="spearman"))
        return {"ic": ic, "rank_ic": ric, "n": int(len(s))}

    ic_df = (
        m.groupby("trade_date", group_keys=False)
        .apply(lambda g: pd.Series(_corr_one(g)))
        .reset_index()
        .rename(columns={"trade_date": "date"})
    )

    def _group_one(g: pd.DataFrame) -> pd.DataFrame:
        s = pd.to_numeric(g[value_col], errors="coerce")
        r = pd.to_numeric(g["fwd_ret"], errors="coerce")
        ok = s.notna() & r.notna()
        x = g.loc[ok, ["trade_date", "asset_code"]].copy()
        x["v"] = s[ok].values
        x["r"] = r[ok].values
        if x.shape[0] < max(10, quantiles * 2):
            return pd.DataFrame()
        try:
            x["q"] = pd.qcut(x["v"], q=quantiles, labels=False, duplicates="drop")
        except Exception:
            return pd.DataFrame()
        out = x.groupby("q", as_index=False)["r"].mean()
        out["trade_date"] = x["trade_date"].iloc[0]
        out["q"] = out["q"].astype(int)
        out = out.rename(columns={"r": "avg_fwd_ret"})
        return out[["trade_date", "q", "avg_fwd_ret"]]

    grp = pd.concat([_group_one(g) for _, g in m.groupby("trade_date")], axis=0, ignore_index=True)
    if grp.empty:
        grp = pd.DataFrame(columns=["trade_date", "q", "avg_fwd_ret"])

    ls = pd.DataFrame()
    if not grp.empty:
        pivot = grp.pivot_table(index="trade_date", columns="q", values="avg_fwd_ret", aggfunc="mean")
        if pivot.shape[1] >= 2:
            top = pivot.max(axis=1)
            bot = pivot.min(axis=1)
            ls = pd.DataFrame({"trade_date": pivot.index, "long_short": (top - bot).values}).reset_index(drop=True)

    def _summary(series: pd.Series) -> dict[str, Any]:
        x = pd.to_numeric(series, errors="coerce").dropna()
        if x.empty:
            return {"mean": None, "std": None, "ir": None, "win_rate": None, "n": 0}
        mean = float(x.mean())
        std = float(x.std(ddof=0))
        ir = float(mean / std * np.sqrt(252)) if std > 0 else None
        win = float((x > 0).mean())
        return {"mean": mean, "std": std, "ir": ir, "win_rate": win, "n": int(x.shape[0])}

    ic_summary = _summary(ic_df["ic"])
    ric_summary = _summary(ic_df["rank_ic"])
    ls_summary = _summary(ls["long_short"]) if not ls.empty else {"mean": None, "std": None, "ir": None, "win_rate": None, "n": 0}

    factor_name = str(fv["factor_name"].iloc[0]) if "factor_name" in fv.columns else ""
    factor_version = str(fv["factor_version"].iloc[0]) if "factor_version" in fv.columns else ""

    analysis_id = uuid4().hex
    out_dir = _artifact_root() / "runs" / calc_batch_id / "analysis" / analysis_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ic_df.to_parquet(out_dir / "ic_series.parquet", index=False)
    grp.to_parquet(out_dir / "group_returns.parquet", index=False)
    if not ls.empty:
        ls.to_parquet(out_dir / "long_short.parquet", index=False)

    summary = {
        "calc_batch_id": calc_batch_id,
        "factor_name": factor_name,
        "factor_version": factor_version,
        "horizon": horizon,
        "quantiles": quantiles,
        "value_col": value_col,
        "ic": ic_summary,
        "rank_ic": ric_summary,
        "long_short": ls_summary,
        "row_count": int(m.shape[0]),
        "date_count": int(ic_df.shape[0]),
    }
    with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    if get_settings().require_db:
        try:
            with db_session() as db:
                db.add(
                    AnalysisResult(
                        analysis_id=analysis_id,
                        analysis_type="single_factor",
                        calc_batch_id=calc_batch_id,
                        factor_name=factor_name,
                        factor_version=factor_version,
                        status="SUCCESS",
                        summary=summary,
                        artifact_path=str(out_dir),
                        row_count=int(m.shape[0]),
                    )
                )
        except Exception:
            pass

    return {"analysis_id": analysis_id, "artifact_path": str(out_dir), "summary": summary}
