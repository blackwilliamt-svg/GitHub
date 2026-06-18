from __future__ import annotations
import pandas as pd
from .base import Strategy, Signal


class BollingerStrategy(Strategy):
    """Bollinger Bands mean-reversion — buys at lower band, sells at upper band."""

    name = "bollinger"

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev
        self._upper: pd.Series = pd.Series(dtype=float)
        self._lower: pd.Series = pd.Series(dtype=float)
        self._mid: pd.Series = pd.Series(dtype=float)

    def initialize(self, data: pd.DataFrame):
        close = data["close"]
        self._mid = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()
        self._upper = self._mid + self.std_dev * std
        self._lower = self._mid - self.std_dev * std

    def generate_signal(self, index: int, data: pd.DataFrame) -> Signal:
        if index < self.period:
            return Signal.HOLD

        close = data.iloc[index]["close"]
        lower = self._lower.iloc[index]
        upper = self._upper.iloc[index]

        close_prev = data.iloc[index - 1]["close"]
        lower_prev = self._lower.iloc[index - 1]
        upper_prev = self._upper.iloc[index - 1]

        if close_prev > lower_prev and close <= lower:
            return Signal.BUY
        if close_prev < upper_prev and close >= upper:
            return Signal.SELL
        return Signal.HOLD
