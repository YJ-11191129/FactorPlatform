from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable

from app.strategies.base import BaseStrategy
from app.strategies.registry import register_strategy


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_strategy_dir() -> Path:
    override = os.getenv("FACTOR_PLATFORM_STRATEGY_DIR")
    if override:
        return Path(override)
    return _project_root() / "strategy_library"


def _load_module_from_file(py_file: Path) -> ModuleType:
    mod_name = f"factorplatform_user_strategy_{py_file.stem}_{abs(hash(str(py_file)))}"
    spec = importlib.util.spec_from_file_location(mod_name, str(py_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load module spec: {py_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def load_strategies_from_dir(strategy_dir: Path | None = None) -> list[str]:
    d = strategy_dir or default_strategy_dir()
    if not d.exists():
        return []

    loaded: list[str] = []
    for py in sorted(d.glob("*.py")):
        module = _load_module_from_file(py)
        loaded.extend(_register_module_strategies(module))
    return loaded


def _register_module_strategies(module: ModuleType) -> list[str]:
    out: list[str] = []
    for v in module.__dict__.values():
        if isinstance(v, type) and issubclass(v, BaseStrategy) and v is not BaseStrategy:
            register_strategy(v)
            out.append(v.info().strategy_id)
    return out


def ensure_strategy_dir_exists() -> Path:
    d = default_strategy_dir()
    d.mkdir(parents=True, exist_ok=True)
    init = d / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
    return d

