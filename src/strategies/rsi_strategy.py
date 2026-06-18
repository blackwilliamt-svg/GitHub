from __future__ import annotations
import pandas as pd
import numpy as np
from .base import Strategy, Signal


class RSIStrategy(Strategy):
    """RSI mean-reversion — buys oversold, sells overbought."""

    name = "rsi"

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self._rsi: pd.Series = pd.Series(dtype=float)

    def initialize(self, data: pd.DataFrame):
        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=self.period - 1, min_periods=self.period).mean()
        avg_loss = loss.ewm(com=self.period - 1, min_periods=self.period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        self._rsi = 100 - (100 / (1 + rs))

    def generate_signal(self, index: int, data: pd.DataFrame) -> Signal:
        if index < self.period:
            return Signal.HOLD

        rsi = self._rsi.iloc[index]
        rsi_prev = self._rsi.iloc[index - 1]

        if rsi_prev < self.oversold and rsi >= self.oversold:
            return Signal.BUY
        if rsi_prev > self.overbought and rsi <= self.overbought:
            return Signal.SELL
        return Signal.HOLD
