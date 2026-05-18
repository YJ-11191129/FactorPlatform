from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Type

from app.factors.base import BaseFactor, FactorInfo


@dataclass(frozen=True)
class RegisteredFactor:
    info: FactorInfo
    factor_cls: Type[BaseFactor]


class FactorRegistry:
    def __init__(self) -> None:
        self._by_name: Dict[str, RegisteredFactor] = {}

    def register(self, factor_cls: Type[BaseFactor]) -> None:
        info = factor_cls.info()
        self._by_name[info.factor_name] = RegisteredFactor(info=info, factor_cls=factor_cls)

    def list(self) -> list[FactorInfo]:
        return [rf.info for rf in sorted(self._by_name.values(), key=lambda x: x.info.factor_name)]

    def get(self, factor_name: str) -> RegisteredFactor:
        return self._by_name[factor_name]


registry = FactorRegistry()


def register_factor(factor_cls: Type[BaseFactor]) -> Type[BaseFactor]:
    registry.register(factor_cls)
    return factor_cls


def list_factors() -> list[FactorInfo]:
    return registry.list()


def get_factor(factor_name: str) -> RegisteredFactor:
    return registry.get(factor_name)


def ensure_registered(factor_modules: Iterable[str]) -> None:
    for _ in factor_modules:
        __import__(_)
