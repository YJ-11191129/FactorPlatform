from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

import numpy as np
import pandas as pd

from app.factors.base import BaseFactor, FactorInfo
from app.factors.registry import register_factor


EPS = 1e-12


@dataclass(frozen=True)
class QlibAlphaDef:
    code: str
    expression: str
    description: str
    category: str
    family: str
    direction_hint: str = "unknown"

    @property
    def factor_name(self) -> str:
        return f"QLIB_ALPHA_{self.code}_V1"


def _safe_div(num: pd.Series, den: pd.Series | float) -> pd.Series:
    den_s = den if isinstance(den, pd.Series) else pd.Series(den, index=num.index)
    return num / den_s.replace(0.0, np.nan)


def _prepare(daily_bar: pd.DataFrame) -> pd.DataFrame:
    required = {"trade_date", "asset_code", "open", "high", "low", "close", "volume"}
    missing = required - set(daily_bar.columns)
    if missing:
        raise ValueError(f"daily_bar missing columns for qlib alpha factors: {sorted(missing)}")

    df = daily_bar[["trade_date", "asset_code", "open", "high", "low", "close", "volume"]].copy()
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    df = df.sort_values(["asset_code", "trade_date"], kind="mergesort").reset_index(drop=True)
    return df


def _by_asset(df: pd.DataFrame, func: Callable[[pd.DataFrame], pd.Series]) -> pd.Series:
    pieces: list[pd.Series] = []
    for _, group in df.groupby("asset_code", sort=False):
        values = func(group)
        if not isinstance(values, pd.Series):
            values = pd.Series(values, index=group.index)
        pieces.append(values.reindex(group.index))
    if not pieces:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.concat(pieces).sort_index()


def _window(code: str, prefix: str) -> int | None:
    if code.startswith(prefix) and code[len(prefix) :].isdigit():
        return int(code[len(prefix) :])
    return None


def _rolling_mean_ratio(df: pd.DataFrame, source: str, window: int, denom: str) -> pd.Series:
    return _by_asset(df, lambda g: _safe_div(g[source].rolling(window, min_periods=window).mean(), g[denom] + EPS))


def _rolling_std_ratio(df: pd.DataFrame, source: str, window: int, denom: str) -> pd.Series:
    return _by_asset(df, lambda g: _safe_div(g[source].rolling(window, min_periods=window).std(), g[denom] + EPS))


def _lag_ratio(df: pd.DataFrame, source: str, lag: int, denom: str) -> pd.Series:
    return _by_asset(df, lambda g: _safe_div(g[source].shift(lag), g[denom] + EPS))


def _rolling_quantile_ratio(df: pd.DataFrame, source: str, window: int, q: float, denom: str) -> pd.Series:
    return _by_asset(df, lambda g: _safe_div(g[source].rolling(window, min_periods=window).quantile(q), g[denom] + EPS))


def _rolling_rank_pct(df: pd.DataFrame, source: str, window: int) -> pd.Series:
    return _by_asset(
        df,
        lambda g: g[source].rolling(window, min_periods=window).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False),
    )


def _rolling_idx(df: pd.DataFrame, source: str, window: int, mode: str) -> pd.Series:
    def calc_arr(x: np.ndarray) -> float:
        if np.isnan(x).all():
            return np.nan
        idx = np.nanargmax(x) if mode == "max" else np.nanargmin(x)
        return float(idx + 1) / float(window)

    return _by_asset(df, lambda g: g[source].rolling(window, min_periods=window).apply(calc_arr, raw=True))


def _rsv(df: pd.DataFrame, window: int) -> pd.Series:
    def calc(g: pd.DataFrame) -> pd.Series:
        low_min = g["low"].rolling(window, min_periods=window).min()
        high_max = g["high"].rolling(window, min_periods=window).max()
        return _safe_div(g["close"] - low_min, high_max - low_min + EPS)

    return _by_asset(df, calc)


def _count_ratio(df: pd.DataFrame, window: int, mode: str) -> pd.Series:
    def calc(g: pd.DataFrame) -> pd.Series:
        diff = g["close"] - g["close"].shift(1)
        up = (diff > 0).astype(float)
        down = (diff < 0).astype(float)
        up[diff.isna()] = np.nan
        down[diff.isna()] = np.nan
        up_r = up.rolling(window, min_periods=window).mean()
        down_r = down.rolling(window, min_periods=window).mean()
        if mode == "up":
            return up_r
        if mode == "down":
            return down_r
        return up_r - down_r

    return _by_asset(df, calc)


def _movement_share(df: pd.DataFrame, source: str, window: int, mode: str) -> pd.Series:
    def calc(g: pd.DataFrame) -> pd.Series:
        diff = g[source] - g[source].shift(1)
        pos = diff.clip(lower=0.0)
        neg = (-diff).clip(lower=0.0)
        den = diff.abs().rolling(window, min_periods=window).sum() + EPS
        pos_s = pos.rolling(window, min_periods=window).sum() / den
        neg_s = neg.rolling(window, min_periods=window).sum() / den
        if mode == "up":
            return pos_s
        if mode == "down":
            return neg_s
        return pos_s - neg_s

    return _by_asset(df, calc)


def _rolling_corr(df: pd.DataFrame, window: int, diff: bool = False) -> pd.Series:
    def calc(g: pd.DataFrame) -> pd.Series:
        left = g["close"].diff() if diff else g["close"]
        right = np.log1p(g["volume"].clip(lower=0.0))
        if diff:
            right = right.diff()
        return left.rolling(window, min_periods=window).corr(right)

    return _by_asset(df, calc)


def _wvma(df: pd.DataFrame, window: int) -> pd.Series:
    def calc(g: pd.DataFrame) -> pd.Series:
        weighted_move = (g["close"] / g["close"].shift(1) - 1.0).abs() * g["volume"]
        mean = weighted_move.rolling(window, min_periods=window).mean()
        std = weighted_move.rolling(window, min_periods=window).std()
        return std / (mean + EPS)

    return _by_asset(df, calc)


def _trend_regression(df: pd.DataFrame, window: int, mode: str) -> pd.Series:
    x = np.arange(window, dtype="float64")
    x_mean = float(x.mean())
    x_centered = x - x_mean
    x_var = float(np.sum(x_centered * x_centered))

    def slope_arr(y: np.ndarray) -> float:
        if np.isnan(y).any() or x_var <= EPS:
            return np.nan
        return float(np.sum(x_centered * (y - y.mean())) / x_var)

    def rsqr_arr(y: np.ndarray) -> float:
        if np.isnan(y).any():
            return np.nan
        y_mean = float(y.mean())
        ss_tot = float(np.sum((y - y_mean) ** 2))
        if ss_tot <= EPS:
            return 0.0
        beta = slope_arr(y)
        alpha = y_mean - beta * x_mean
        pred = alpha + beta * x
        ss_res = float(np.sum((y - pred) ** 2))
        return max(0.0, min(1.0, 1.0 - ss_res / ss_tot))

    def resi_arr(y: np.ndarray) -> float:
        if np.isnan(y).any():
            return np.nan
        beta = slope_arr(y)
        alpha = float(y.mean()) - beta * x_mean
        pred_last = alpha + beta * x[-1]
        return float(y[-1] - pred_last)

    def calc(g: pd.DataFrame) -> pd.Series:
        roll = g["close"].rolling(window, min_periods=window)
        if mode == "beta":
            return roll.apply(slope_arr, raw=True) / (g["close"] + EPS)
        if mode == "rsqr":
            return roll.apply(rsqr_arr, raw=True)
        return roll.apply(resi_arr, raw=True) / (g["close"] + EPS)

    return _by_asset(df, calc)


def _compute_series(code: str, df: pd.DataFrame) -> pd.Series:
    open_ = df["open"]
    high = df["high"]
    low = df["low"]
    close = df["close"]
    volume = df["volume"]
    candle_range = high - low + EPS
    upper_base = pd.concat([open_, close], axis=1).max(axis=1)
    lower_base = pd.concat([open_, close], axis=1).min(axis=1)

    if code == "KMID":
        return _safe_div(close - open_, open_)
    if code == "KMID2":
        return (close - open_) / candle_range
    if code == "KLEN":
        return _safe_div(high - low, open_)
    if code == "KUP":
        return _safe_div(high - upper_base, open_)
    if code == "KUP2":
        return (high - upper_base) / candle_range
    if code == "KLOW":
        return _safe_div(lower_base - low, open_)
    if code == "KLOW2":
        return (lower_base - low) / candle_range
    if code == "KSFT":
        return _safe_div(2.0 * close - high - low, open_)
    if code == "KSFT2":
        return (2.0 * close - high - low) / candle_range

    for prefix, source, denom in [
        ("OPEN", "open", "close"),
        ("HIGH", "high", "close"),
        ("LOW", "low", "close"),
        ("CLOSE", "close", "close"),
        ("VOLUME", "volume", "volume"),
    ]:
        n = _window(code, prefix)
        if n is not None:
            return _lag_ratio(df, source, n, denom)

    n = _window(code, "MA")
    if n is not None:
        return _rolling_mean_ratio(df, "close", n, "close")
    n = _window(code, "STD")
    if n is not None:
        return _rolling_std_ratio(df, "close", n, "close")
    n = _window(code, "ROC")
    if n is not None:
        return _by_asset(df, lambda g: g["close"] / (g["close"].shift(n) + EPS) - 1.0)
    n = _window(code, "MAX")
    if n is not None:
        return _by_asset(df, lambda g: g["high"].rolling(n, min_periods=n).max() / (g["close"] + EPS))
    n = _window(code, "MIN")
    if n is not None:
        return _by_asset(df, lambda g: g["low"].rolling(n, min_periods=n).min() / (g["close"] + EPS))
    n = _window(code, "QTLU")
    if n is not None:
        return _rolling_quantile_ratio(df, "close", n, 0.8, "close")
    n = _window(code, "QTLD")
    if n is not None:
        return _rolling_quantile_ratio(df, "close", n, 0.2, "close")
    n = _window(code, "RANK")
    if n is not None:
        return _rolling_rank_pct(df, "close", n)
    n = _window(code, "RSV")
    if n is not None:
        return _rsv(df, n)
    n = _window(code, "IMAX")
    if n is not None:
        return _rolling_idx(df, "high", n, "max")
    n = _window(code, "IMIN")
    if n is not None:
        return _rolling_idx(df, "low", n, "min")
    n = _window(code, "IMXD")
    if n is not None:
        return _rolling_idx(df, "high", n, "max") - _rolling_idx(df, "low", n, "min")

    n = _window(code, "CNTP")
    if n is not None:
        return _count_ratio(df, n, "up")
    n = _window(code, "CNTN")
    if n is not None:
        return _count_ratio(df, n, "down")
    n = _window(code, "CNTD")
    if n is not None:
        return _count_ratio(df, n, "diff")
    n = _window(code, "SUMP")
    if n is not None:
        return _movement_share(df, "close", n, "up")
    n = _window(code, "SUMN")
    if n is not None:
        return _movement_share(df, "close", n, "down")
    n = _window(code, "SUMD")
    if n is not None:
        return _movement_share(df, "close", n, "diff")

    n = _window(code, "VMA")
    if n is not None:
        return _rolling_mean_ratio(df, "volume", n, "volume")
    n = _window(code, "VSTD")
    if n is not None:
        return _rolling_std_ratio(df, "volume", n, "volume")
    n = _window(code, "WVMA")
    if n is not None:
        return _wvma(df, n)
    n = _window(code, "VSUMP")
    if n is not None:
        return _movement_share(df, "volume", n, "up")
    n = _window(code, "VSUMN")
    if n is not None:
        return _movement_share(df, "volume", n, "down")
    n = _window(code, "VSUMD")
    if n is not None:
        return _movement_share(df, "volume", n, "diff")

    n = _window(code, "CORR")
    if n is not None:
        return _rolling_corr(df, n, diff=False)
    n = _window(code, "CORD")
    if n is not None:
        return _rolling_corr(df, n, diff=True)
    n = _window(code, "BETA")
    if n is not None:
        return _trend_regression(df, n, "beta")
    n = _window(code, "RSQR")
    if n is not None:
        return _trend_regression(df, n, "rsqr")
    n = _window(code, "RESI")
    if n is not None:
        return _trend_regression(df, n, "resi")

    raise KeyError(f"unsupported qlib alpha code: {code}")


def _build_defs() -> tuple[QlibAlphaDef, ...]:
    defs: dict[str, QlibAlphaDef] = {}

    def add(code: str, expression: str, description: str, category: str, family: str, direction_hint: str = "unknown") -> None:
        defs[code] = QlibAlphaDef(code, expression, description, category, family, direction_hint)

    candle = "QLIB_CANDLE_SHAPE"
    price = "QLIB_PRICE_LEVEL"
    trend = "QLIB_TREND"
    momentum = "QLIB_MOMENTUM"
    volatility = "QLIB_VOLATILITY"
    volume = "QLIB_VOLUME"
    interaction = "QLIB_VOLUME_PRICE"
    position = "QLIB_POSITION"
    count = "QLIB_COUNTING"

    add("KMID", "($close-$open)/$open", "Candlestick body return relative to open.", candle, "candle_body")
    add("KMID2", "($close-$open)/($high-$low+1e-12)", "Candlestick body relative to intraday range.", candle, "candle_body")
    add("KLEN", "($high-$low)/$open", "Candlestick range relative to open.", candle, "intraday_range")
    add("KUP", "($high-Max($open,$close))/$open", "Upper shadow relative to open.", candle, "shadow")
    add("KUP2", "($high-Max($open,$close))/($high-$low+1e-12)", "Upper shadow relative to range.", candle, "shadow")
    add("KLOW", "(Min($open,$close)-$low)/$open", "Lower shadow relative to open.", candle, "shadow")
    add("KLOW2", "(Min($open,$close)-$low)/($high-$low+1e-12)", "Lower shadow relative to range.", candle, "shadow")
    add("KSFT", "(2*$close-$high-$low)/$open", "Close location relative to open.", candle, "close_location")
    add("KSFT2", "(2*$close-$high-$low)/($high-$low+1e-12)", "Close location relative to intraday range.", candle, "close_location")

    for lag in range(0, 6):
        add(f"OPEN{lag}", f"Ref($open,{lag})/$close", f"Open price lag {lag} relative to current close.", price, "ohlc_lag_ratio")
        add(f"HIGH{lag}", f"Ref($high,{lag})/$close", f"High price lag {lag} relative to current close.", price, "ohlc_lag_ratio")
        add(f"LOW{lag}", f"Ref($low,{lag})/$close", f"Low price lag {lag} relative to current close.", price, "ohlc_lag_ratio")
        add(f"CLOSE{lag}", f"Ref($close,{lag})/$close", f"Close price lag {lag} relative to current close.", price, "ohlc_lag_ratio")
        add(f"VOLUME{lag}", f"Ref($volume,{lag})/($volume+1e-12)", f"Volume lag {lag} relative to current volume.", volume, "volume_lag_ratio")

    for n in (5, 10, 20, 30, 60, 120):
        add(f"MA{n}", f"Mean($close,{n})/$close", f"{n}-day moving average relative to close.", trend, "moving_average")
        add(f"ROC{n}", f"$close/Ref($close,{n})-1", f"{n}-day close rate of change.", momentum, "rate_of_change", "positive")
        add(f"VMA{n}", f"Mean($volume,{n})/($volume+1e-12)", f"{n}-day volume average relative to current volume.", volume, "volume_average")
        add(f"WVMA{n}", f"Std(Abs(Return)*$volume,{n})/(Mean(Abs(Return)*$volume,{n})+1e-12)", f"{n}-day volume-weighted movement variability.", interaction, "weighted_volume_move")

    for n in (5, 10, 20, 30, 60):
        add(f"STD{n}", f"Std($close,{n})/$close", f"{n}-day close volatility relative to close.", volatility, "price_volatility", "negative")
        add(f"MAX{n}", f"Max($high,{n})/$close", f"{n}-day rolling high relative to close.", position, "rolling_extreme")
        add(f"MIN{n}", f"Min($low,{n})/$close", f"{n}-day rolling low relative to close.", position, "rolling_extreme")
        add(f"QTLU{n}", f"Quantile($close,{n},0.8)/$close", f"80% rolling close quantile relative to close over {n} days.", position, "rolling_quantile")
        add(f"QTLD{n}", f"Quantile($close,{n},0.2)/$close", f"20% rolling close quantile relative to close over {n} days.", position, "rolling_quantile")
        add(f"RANK{n}", f"Rank($close,{n})", f"Rolling percentile rank of close in the last {n} days.", position, "rolling_rank")
        add(f"RSV{n}", f"($close-Min($low,{n}))/(Max($high,{n})-Min($low,{n})+1e-12)", f"Close location inside the {n}-day high-low channel.", position, "channel_position", "positive")
        add(f"IMAX{n}", f"IdxMax($high,{n})/{n}", f"Position of the highest high in the last {n} days, scaled by window.", position, "extreme_timing")
        add(f"IMIN{n}", f"IdxMin($low,{n})/{n}", f"Position of the lowest low in the last {n} days, scaled by window.", position, "extreme_timing")
        add(f"IMXD{n}", f"IdxMax($high,{n})/{n}-IdxMin($low,{n})/{n}", f"Relative timing spread between rolling high and rolling low over {n} days.", position, "extreme_timing")
        add(f"CNTP{n}", f"Mean($close>Ref($close,1),{n})", f"{n}-day ratio of up-close days.", count, "up_down_count", "positive")
        add(f"CNTN{n}", f"Mean($close<Ref($close,1),{n})", f"{n}-day ratio of down-close days.", count, "up_down_count", "negative")
        add(f"CNTD{n}", f"CNTP{n}-CNTN{n}", f"{n}-day up-minus-down close-day ratio.", count, "up_down_count", "positive")
        add(f"SUMP{n}", f"Sum(PositiveDelta($close),{n})/(Sum(AbsDelta($close),{n})+1e-12)", f"Share of positive close movement over {n} days.", count, "movement_share", "positive")
        add(f"SUMN{n}", f"Sum(NegativeDelta($close),{n})/(Sum(AbsDelta($close),{n})+1e-12)", f"Share of negative close movement over {n} days.", count, "movement_share", "negative")
        add(f"SUMD{n}", f"SUMP{n}-SUMN{n}", f"Positive minus negative close movement share over {n} days.", count, "movement_share", "positive")
        add(f"VSTD{n}", f"Std($volume,{n})/($volume+1e-12)", f"{n}-day volume volatility relative to current volume.", volume, "volume_volatility")
        add(f"VSUMP{n}", f"Sum(PositiveDelta($volume),{n})/(Sum(AbsDelta($volume),{n})+1e-12)", f"Share of positive volume movement over {n} days.", volume, "volume_movement_share")
        add(f"VSUMN{n}", f"Sum(NegativeDelta($volume),{n})/(Sum(AbsDelta($volume),{n})+1e-12)", f"Share of negative volume movement over {n} days.", volume, "volume_movement_share")
        add(f"VSUMD{n}", f"VSUMP{n}-VSUMN{n}", f"Positive minus negative volume movement share over {n} days.", volume, "volume_movement_share")
        add(f"CORR{n}", f"Corr($close,Log(1+$volume),{n})", f"{n}-day rolling correlation between close and log volume.", interaction, "price_volume_corr")
        add(f"CORD{n}", f"Corr(Delta($close),Delta(Log(1+$volume)),{n})", f"{n}-day rolling correlation between close changes and volume changes.", interaction, "price_volume_corr")
        add(f"BETA{n}", f"Slope($close,{n})/$close", f"Normalized linear trend slope over {n} days.", trend, "linear_trend", "positive")
        add(f"RSQR{n}", f"Rsquare($close,{n})", f"R-squared of the {n}-day close trend regression.", trend, "linear_trend")
        add(f"RESI{n}", f"Residual($close,{n})/$close", f"Last close residual from the {n}-day linear trend regression.", trend, "linear_trend")

    return tuple(defs.values())


QLIB_ALPHA_DEFS: tuple[QlibAlphaDef, ...] = _build_defs()


def _make_factor_class(defn: QlibAlphaDef) -> type[BaseFactor]:
    class QlibAlphaFactor(BaseFactor):
        @classmethod
        def info(cls) -> FactorInfo:
            return FactorInfo(
                factor_name=defn.factor_name,
                display_name=f"Qlib Alpha {defn.code}",
                category=defn.category,
                description=f"{defn.description} Expression: {defn.expression}",
                version="V1",
                dependencies=[
                    "daily_bar.trade_date",
                    "daily_bar.asset_code",
                    "daily_bar.open",
                    "daily_bar.high",
                    "daily_bar.low",
                    "daily_bar.close",
                    "daily_bar.volume",
                ],
                parameter_schema={
                    "source": {"type": "string", "readOnly": True, "value": "qlib_bin_ohlcv"},
                    "family": {"type": "string", "readOnly": True, "value": defn.family},
                    "qlib_code": {"type": "string", "readOnly": True, "value": defn.code},
                    "expression": {"type": "string", "readOnly": True, "value": defn.expression},
                    "direction_hint": {"type": "string", "readOnly": True, "value": defn.direction_hint},
                },
            )

        @classmethod
        def validate_params(cls, params: Mapping[str, Any]) -> dict[str, Any]:
            return {}

        @classmethod
        def compute(cls, daily_bar: pd.DataFrame, params: Mapping[str, Any]) -> pd.DataFrame:
            cls.validate_params(params)
            df = _prepare(daily_bar)
            df["factor_value"] = _compute_series(defn.code, df).replace([np.inf, -np.inf], np.nan)
            out = df[["trade_date", "asset_code", "factor_value"]].dropna()
            return cls.post_check(out)

    QlibAlphaFactor.__name__ = f"QlibAlpha{defn.code}"
    QlibAlphaFactor.__qualname__ = QlibAlphaFactor.__name__
    QlibAlphaFactor.__module__ = __name__
    return register_factor(QlibAlphaFactor)


for _defn in QLIB_ALPHA_DEFS:
    globals()[f"QlibAlpha{_defn.code}"] = _make_factor_class(_defn)
