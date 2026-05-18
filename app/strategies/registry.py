from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Type

from app.strategies.base import BaseStrategy, StrategyInfo


@dataclass(frozen=True)
class RegisteredStrategy:
    info: StrategyInfo
    strategy_cls: Type[BaseStrategy]
    python_entry: str


class StrategyRegistry:
    def __init__(self) -> None:
        self._by_id: Dict[str, RegisteredStrategy] = {}

    def register(self, strategy_cls: Type[BaseStrategy]) -> None:
        info = strategy_cls.info()
        entry = f"{strategy_cls.__module__}:{strategy_cls.__name__}"
        self._by_id[info.strategy_id] = RegisteredStrategy(info=info, strategy_cls=strategy_cls, python_entry=entry)

    def list(self) -> list[RegisteredStrategy]:
        return [rs for rs in sorted(self._by_id.values(), key=lambda x: x.info.strategy_id)]

    def get(self, strategy_id: str) -> RegisteredStrategy:
        return self._by_id[strategy_id]


registry = StrategyRegistry()


def register_strategy(strategy_cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
    registry.register(strategy_cls)
    return strategy_cls


def list_strategies() -> list[RegisteredStrategy]:
    return registry.list()


def get_strategy(strategy_id: str) -> RegisteredStrategy:
    return registry.get(strategy_id)


def ensure_registered(modules: Iterable[str]) -> None:
    for m in modules:
        __import__(m)

