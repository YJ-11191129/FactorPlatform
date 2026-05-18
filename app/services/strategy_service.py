from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.strategies.loader import ensure_strategy_dir_exists, load_strategies_from_dir
from app.strategies.registry import ensure_registered, list_strategies


DEFAULT_STRATEGY_MODULES = [
    "app.strategies.builtins.mom_ma_v1",
]


def ensure_strategies_loaded() -> None:
    ensure_registered(DEFAULT_STRATEGY_MODULES)
    ensure_strategy_dir_exists()
    load_strategies_from_dir()


def list_strategy_infos() -> list[dict[str, Any]]:
    ensure_strategies_loaded()
    out: list[dict[str, Any]] = []
    for rs in list_strategies():
        d = asdict(rs.info)
        if d.get("parameter_schema") is None:
            d["parameter_schema"] = {}
        d["python_entry"] = rs.python_entry
        out.append(d)
    return out
