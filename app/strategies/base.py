from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Protocol

import pandas as pd


@dataclass(frozen=True)
class StrategyInfo:
    strategy_id: str
    strategy_name: str
    description: str
    version: str = "v1"
    owner: str = "research"
    parameter_schema: Mapping[str, Any] = None


class StrategyContext(Protocol):
    def prices(self) -> pd.DataFrame: ...
    def universe(self) -> list[str]: ...
    def dates(self) -> list[date]: ...


class BaseStrategy:
    @classmethod
    def info(cls) -> StrategyInfo:
        raise NotImplementedError

    def run(self, ctx: StrategyContext, params: Mapping[str, Any]) -> pd.DataFrame:
        raise NotImplementedError

