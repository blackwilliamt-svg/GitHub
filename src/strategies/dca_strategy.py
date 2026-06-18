from __future__ import annotations
import pandas as pd
from .base import Strategy, Signal


class DCAStrategy(Strategy):
    """Dollar-Cost Averaging — buys at fixed intervals, optionally with RSI filter."""

    name = "dca"

    def __init__(
        self,
        buy_interval: int = 24,
        rsi_filter: bool = False,
        rsi_threshold: float = 50.0,
        rsi_period: int = 14,
    ):
        self.buy_interval = buy_interval
        self.rsi_filter = rsi_filter
        self.rsi_threshold = rsi_threshold
        self.rsi_period = rsi_period
        self._rsi: pd.Series = pd.Series(dtype=float)
        self._bar_count: int = 0

    def initialize(self, data: pd.DataFrame):
        if self.rsi_filter:
            import numpy as np
            delta = data["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(com=self.rsi_period - 1, min_periods=self.rsi_period).mean()
            avg_loss = loss.ewm(com=self.rsi_period - 1, min_periods=self.rsi_period).mean()
            rs = avg_gain / avg_loss.replace(0, np.inf)
            self._rsi = 100 - (100 / (1 + rs))

    def generate_signal(self, index: int, data: pd.DataFrame) -> Signal:
        self._bar_count += 1

        if self._bar_count % self.buy_interval != 0:
            return Signal.HOLD

        if self.rsi_filter and index >= self.rsi_period:
            if self._rsi.iloc[index] > self.rsi_threshold:
                return Signal.HOLD

        return Signal.BUY
