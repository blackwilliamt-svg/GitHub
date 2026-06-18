from __future__ import annotations
import pandas as pd
from .base import Strategy, Signal


class MACrossover(Strategy):
    """Classic dual moving average crossover — buys on golden cross, sells on death cross."""

    name = "ma_crossover"

    def __init__(self, fast_period: int = 12, slow_period: int = 26, ma_type: str = "ema"):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.ma_type = ma_type
        self._fast_ma: pd.Series = pd.Series(dtype=float)
        self._slow_ma: pd.Series = pd.Series(dtype=float)

    def initialize(self, data: pd.DataFrame):
        close = data["close"]
        if self.ma_type == "ema":
            self._fast_ma = close.ewm(span=self.fast_period, adjust=False).mean()
            self._slow_ma = close.ewm(span=self.slow_period, adjust=False).mean()
        else:
            self._fast_ma = close.rolling(window=self.fast_period).mean()
            self._slow_ma = close.rolling(window=self.slow_period).mean()

    def generate_signal(self, index: int, data: pd.DataFrame) -> Signal:
        if index < self.slow_period:
            return Signal.HOLD

        fast_now = self._fast_ma.iloc[index]
        slow_now = self._slow_ma.iloc[index]
        fast_prev = self._fast_ma.iloc[index - 1]
        slow_prev = self._slow_ma.iloc[index - 1]

        if fast_prev <= slow_prev and fast_now > slow_now:
            return Signal.BUY
        if fast_prev >= slow_prev and fast_now < slow_now:
            return Signal.SELL
        return Signal.HOLD
