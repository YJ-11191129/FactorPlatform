from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests


@dataclass(frozen=True)
class MacroInputs:
    topic: str
    event: str | None = None
    region: str | None = None
    horizon: str | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _wind_data_root() -> Path:
    return Path(os.getenv("FACTOR_PLATFORM_WIND_DATA_ROOT", r"D:\Kaggle\data\wind_data"))


def _read_macro_cross_asset_panel() -> pd.DataFrame | None:
    p = _wind_data_root() / "03_market_state" / "macro_cross_asset_daily.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _read_stock_ohlcv_status() -> dict[str, Any]:
    p = Path(os.getenv("FACTOR_PLATFORM_REAL_OHLCV_PATH", r"D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_ohlcv.parquet"))
    if not p.exists():
        return {"path": str(p), "exists": False}

    out: dict[str, Any] = {
        "path": str(p),
        "exists": True,
        "start_date": None,
        "end_date": None,
        "asset_count": None,
        "row_count": None,
        "file_size_bytes": int(p.stat().st_size),
        "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
    }

    try:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(str(p))
        meta = pf.metadata
        out["row_count"] = int(meta.num_rows) if meta is not None else None

        date_idx = None
        if meta is not None:
            for i in range(meta.num_columns):
                if meta.schema.column(i).name == "date":
                    date_idx = i
                    break

        if meta is not None and date_idx is not None and meta.num_row_groups > 0:
            min_v = None
            max_v = None
            for rg in range(meta.num_row_groups):
                col = meta.row_group(rg).column(date_idx)
                stats = col.statistics
                if stats is None:
                    continue
                if stats.has_min_max:
                    if min_v is None or stats.min < min_v:
                        min_v = stats.min
                    if max_v is None or stats.max > max_v:
                        max_v = stats.max
            if min_v is not None:
                out["start_date"] = str(pd.to_datetime(min_v).date())
            if max_v is not None:
                out["end_date"] = str(pd.to_datetime(max_v).date())

        return out
    except Exception:
        try:
            df = pd.read_parquet(p, columns=["date"])
            d = pd.to_datetime(df["date"]).dt.date
            out["row_count"] = int(len(df))
            out["start_date"] = str(d.min()) if len(d) else None
            out["end_date"] = str(d.max()) if len(d) else None
            return out
        except Exception:
            return out


def _topic_registry(topic: str) -> dict[str, Any]:
    t = (topic or "").strip().lower()
    if any(k in t for k in ["oil", "wti", "brent", "原油", "石油", "能源"]):
        return {
            "topic": topic,
            "related_assets": [
                {"asset_name": "WTI", "wind_code": "CL00.NYM"},
                {"asset_name": "GOLD", "wind_code": "GC00.CMX"},
                {"asset_name": "DXY", "wind_code": "USDX.FX"},
                {"asset_name": "UST10Y", "wind_code": "10YRNO"},
                {"asset_name": "VIX", "wind_code": "VIX.GI"},
                {"asset_name": "SP500", "wind_code": "SPX.GI"},
            ],
        }
    return {"topic": topic, "related_assets": []}


def _summarize_time_series(df: pd.DataFrame, date_col: str, value_col: str) -> dict[str, Any]:
    if df.empty:
        return {"points": 0}
    x = df.sort_values(date_col).copy()
    x[value_col] = pd.to_numeric(x[value_col], errors="coerce")
    x = x.dropna(subset=[value_col])
    if x.empty:
        return {"points": 0}
    last = float(x[value_col].iloc[-1])
    first = float(x[value_col].iloc[0])
    chg = last - first
    chg_pct = (chg / first) if first else None
    return {
        "points": int(len(x)),
        "start": str(x[date_col].iloc[0]),
        "end": str(x[date_col].iloc[-1]),
        "first": first,
        "last": last,
        "change": chg,
        "change_pct": chg_pct,
    }


def collect_holistic_context(inputs: MacroInputs, lookback_days: int = 120) -> dict[str, Any]:
    topic_meta = _topic_registry(inputs.topic)
    panel = _read_macro_cross_asset_panel()
    stock_status = _read_stock_ohlcv_status()

    out: dict[str, Any] = {
        "topic": inputs.topic,
        "event": inputs.event,
        "region": inputs.region,
        "horizon": inputs.horizon,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "data_sources": {
            "wind_stock_daily_ohlcv": stock_status,
            "macro_cross_asset_daily": {
                "path": str(_wind_data_root() / "03_market_state" / "macro_cross_asset_daily.parquet"),
                "exists": panel is not None,
            },
        },
        "topic_registry": topic_meta,
        "signals": {},
        "notes": [],
    }

    if panel is None:
        out["notes"].append("macro_cross_asset_daily.parquet not found; cross-asset context is limited")
        return out

    end_date = panel["date"].max() if "date" in panel.columns and not panel.empty else None
    if end_date is None:
        out["notes"].append("macro_cross_asset_daily.parquet is empty")
        return out
    start_date = end_date
    if isinstance(end_date, (datetime,)):
        start_date = end_date.date()
    if hasattr(end_date, "to_pydatetime"):
        start_date = end_date.to_pydatetime().date()
    start_date = start_date

    cutoff = pd.to_datetime(end_date) - pd.Timedelta(days=int(lookback_days))
    x = panel[pd.to_datetime(panel["date"]) >= cutoff].copy()

    for asset in topic_meta.get("related_assets", []):
        code = asset.get("wind_code")
        name = asset.get("asset_name")
        if not code or not name:
            continue
        sub = x[x.get("wind_code") == code]
        if sub.empty:
            continue
        if "value" in sub.columns:
            out["signals"][name] = _summarize_time_series(sub, "date", "value")

    return out


def _openai_chat_json(model: str, system: str, user: str, timeout_s: int = 60) -> dict[str, Any]:
    cfg = _llm_config()
    key = str(cfg.get("api_key") or "").strip()
    if not key:
        raise RuntimeError("LLM_API_KEY / OPENAI_API_KEY is not configured")

    url = str(cfg.get("endpoint") or "https://api.openai.com/v1/chat/completions")
    payload = {
        "model": model,
        "temperature": float(cfg.get("temperature") or 0.2),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if cfg.get("max_tokens") is not None:
        payload["max_tokens"] = int(cfg["max_tokens"])
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=int(cfg.get("timeout_s") or timeout_s))
    if r.status_code >= 400:
        raise RuntimeError(f"OpenAI error: status={r.status_code} body={r.text[:400]}")
    data = r.json()
    content = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""
    content = content.strip()
    try:
        return json.loads(content)
    except Exception:
        return {"text": content}


def llm_ready() -> bool:
    cfg = _llm_config()
    return bool(cfg.get("api_key"))


def _llm_config() -> dict[str, Any]:
    provider = (os.getenv("LLM_PROVIDER") or "").strip() or "openai_compatible"
    api_key = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    model = (
        os.getenv("LLM_MODEL")
        or os.getenv("FACTOR_PLATFORM_LLM_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "deepseek-chat"
    ).strip()
    temperature_raw = (os.getenv("LLM_TEMPERATURE") or "").strip()
    timeout_raw = (os.getenv("LLM_TIMEOUT_SECONDS") or "").strip()
    max_tokens_raw = (os.getenv("LLM_MAX_TOKENS") or "").strip()

    temperature = 0.2
    if temperature_raw:
        try:
            temperature = float(temperature_raw)
        except Exception:
            temperature = 0.2

    timeout_s = 90
    if timeout_raw:
        try:
            timeout_s = int(float(timeout_raw))
        except Exception:
            timeout_s = 90

    max_tokens: int | None = None
    if max_tokens_raw:
        try:
            max_tokens = int(float(max_tokens_raw))
        except Exception:
            max_tokens = None

    base_or_endpoint = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or "https://api.deepseek.com"
    ).strip()
    endpoint = _normalize_openai_compatible_chat_completions_endpoint(base_or_endpoint)

    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "endpoint": endpoint,
        "timeout_s": timeout_s,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def _normalize_openai_compatible_chat_completions_endpoint(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return "https://api.openai.com/v1/chat/completions"

    if raw.endswith("/chat/completions") or raw.endswith("/v1/chat/completions"):
        return raw
    if raw.endswith("/v1"):
        return raw + "/chat/completions"

    p = urlparse(raw)
    if p.scheme in {"http", "https"} and (p.netloc and (p.path == "" or p.path == "/")):
        return raw.rstrip("/") + "/v1/chat/completions"

    return raw


def generate_chain_of_impact(inputs: MacroInputs, context: dict[str, Any]) -> dict[str, Any]:
    model = str(_llm_config().get("model") or "gpt-4o-mini")

    system = (
        "You are a macro research assistant. Produce a structured causal analysis in JSON only. "
        "Do not reveal private chain-of-thought. Provide concise, user-facing reasoning steps."
    )
    user = {
        "task": "macro_chain_of_impact",
        "topic": inputs.topic,
        "event": inputs.event,
        "region": inputs.region,
        "horizon": inputs.horizon,
        "context": context,
        "output_schema": {
            "regime_hypothesis": "string",
            "cause": ["string"],
            "transmission": [{"step": "string", "channel": "string", "who": "string", "timeframe": "string"}],
            "impact": {
                "assets": [{"name": "string", "direction": "up|down|mixed", "confidence": 0.0}],
                "sectors": [{"name": "string", "direction": "up|down|mixed", "confidence": 0.0}],
                "signals_to_watch": ["string"],
            },
            "risks": ["string"],
            "assumptions": ["string"],
            "confidence": 0.0,
        },
    }

    try:
        return _openai_chat_json(model=model, system=system, user=json.dumps(user, ensure_ascii=False), timeout_s=90)
    except Exception as e:
        signals = context.get("signals") or {}
        assets = [{"name": k, "direction": "mixed", "confidence": 0.35} for k in list(signals.keys())[:8]]
        return {
            "regime_hypothesis": "UNKNOWN",
            "cause": [inputs.event or f"Topic shock: {inputs.topic}"],
            "transmission": [
                {"step": "供给/需求预期变化", "channel": "expectations", "who": "producers/consumers", "timeframe": "days-weeks"},
                {"step": "风险偏好与波动反馈", "channel": "risk", "who": "investors", "timeframe": "days"},
                {"step": "汇率/利率与金融条件", "channel": "macro", "who": "policy/markets", "timeframe": "weeks"},
            ],
            "impact": {
                "assets": assets,
                "sectors": [
                    {"name": "能源", "direction": "mixed", "confidence": 0.35},
                    {"name": "运输/航空", "direction": "mixed", "confidence": 0.25},
                    {"name": "化工", "direction": "mixed", "confidence": 0.25},
                ],
                "signals_to_watch": ["WTI/Brent", "DXY", "UST10Y", "VIX"],
            },
            "risks": ["Data/news coverage incomplete", "Second-order policy response"],
            "assumptions": ["Fallback mode: LLM not configured"],
            "confidence": 0.25,
            "error": str(e),
        }


def generate_topic_report(inputs: MacroInputs, context: dict[str, Any]) -> dict[str, Any]:
    model = str(_llm_config().get("model") or "gpt-4o-mini")

    system = (
        "You are a macro research assistant. Write a structured report in JSON only. "
        "Do not reveal private chain-of-thought. Focus on: supply chain, regional S/D, geopolitics, logistics, "
        "and market indicators; cite data sources from context." 
    )
    user = {
        "task": "holistic_topic_report",
        "topic": inputs.topic,
        "region": inputs.region,
        "horizon": inputs.horizon,
        "context": context,
        "output_schema": {
            "executive_summary": "string",
            "drivers": ["string"],
            "supply_chain": [{"node": "string", "notes": "string"}],
            "regional_supply_demand": [{"region": "string", "balance": "string", "notes": "string"}],
            "geopolitics": ["string"],
            "logistics_storage": ["string"],
            "market_dashboard": [{"metric": "string", "value": "string", "interpretation": "string"}],
            "watchlist": ["string"],
            "disclaimer": "string",
        },
    }
    try:
        return _openai_chat_json(model=model, system=system, user=json.dumps(user, ensure_ascii=False), timeout_s=120)
    except Exception as e:
        signals = context.get("signals") or {}
        dashboard = []
        for k, v in list(signals.items())[:8]:
            last = v.get("last")
            chg_pct = v.get("change_pct")
            dashboard.append({"metric": k, "value": f"{last}", "interpretation": f"lookback change_pct={chg_pct}"})
        return {
            "executive_summary": f"(Fallback) Topic={inputs.topic}. LLM call failed; showing a template report.",
            "drivers": ["Supply/Demand", "Risk sentiment", "FX/Rates"],
            "supply_chain": [{"node": "Upstream", "notes": "Producer capacity / geopolitics"}, {"node": "Midstream", "notes": "Transport/storage"}, {"node": "Downstream", "notes": "Refining/consumption"}],
            "regional_supply_demand": [{"region": inputs.region or "Global", "balance": "unknown", "notes": "Needs dedicated crawler/news"}],
            "geopolitics": [inputs.event or "No event provided"],
            "logistics_storage": ["Shipping routes", "Inventory", "OPEC+ policy"],
            "market_dashboard": dashboard,
            "watchlist": ["WTI", "DXY", "VIX"],
            "disclaimer": "This is an automated summary for research only; not investment advice.",
            "error": str(e),
        }
