from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd


@dataclass(frozen=True)
class FactorInfo:
    factor_name: str
    display_name: str
    category: str
    description: str
    version: str
    dependencies: list[str]
    parameter_schema: Mapping[str, Any]


class BaseFactor(ABC):
    @classmethod
    @abstractmethod
    def info(cls) -> FactorInfo:
        raise NotImplementedError

    @classmethod
    def validate_params(cls, params: Mapping[str, Any]) -> dict[str, Any]:
        return dict(params)

    @classmethod
    @abstractmethod
    def compute(cls, daily_bar: pd.DataFrame, params: Mapping[str, Any]) -> pd.DataFrame:
        raise NotImplementedError

    @staticmethod
    def post_check(output_df: pd.DataFrame) -> pd.DataFrame:
        required = {"trade_date", "asset_code", "factor_value"}
        missing = required - set(output_df.columns)
        if missing:
            raise ValueError(f"missing columns: {sorted(missing)}")

        keys = ["trade_date", "asset_code"]
        if output_df.duplicated(keys).any():
            raise ValueError("duplicated trade_date+asset_code detected")

        if output_df["factor_value"].isna().all():
            raise ValueError("all factor_value is NA")

        return output_df
