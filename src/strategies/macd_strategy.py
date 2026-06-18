from __future__ import annotations
import pandas as pd
from .base import Strategy, Signal


class MACDStrategy(Strategy):
    """MACD crossover strategy — trades the MACD/signal line crossover with histogram confirmation."""

    name = "macd"

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        histogram_threshold: float = 0.0,
    ):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.histogram_threshold = histogram_threshold
        self._macd_line: pd.Series = pd.Series(dtype=float)
        self._signal_line: pd.Series = pd.Series(dtype=float)
        self._histogram: pd.Series = pd.Series(dtype=float)

    def initialize(self, data: pd.DataFrame):
        close = data["close"]
        ema_fast = close.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow_period, adjust=False).mean()
        self._macd_line = ema_fast - ema_slow
        self._signal_line = self._macd_line.ewm(span=self.signal_period, adjust=False).mean()
        self._histogram = self._macd_line - self._signal_line

    def generate_signal(self, index: int, data: pd.DataFrame) -> Signal:
        if index < self.slow_period + self.signal_period:
            return Signal.HOLD

        macd_now = self._macd_line.iloc[index]
        sig_now = self._signal_line.iloc[index]
        macd_prev = self._macd_line.iloc[index - 1]
        sig_prev = self._signal_line.iloc[index - 1]
        hist = self._histogram.iloc[index]

        if macd_prev <= sig_prev and macd_now > sig_now and hist > self.histogram_threshold:
            return Signal.BUY
        if macd_prev >= sig_prev and macd_now < sig_now and hist < -self.histogram_threshold:
            return Signal.SELL
        return Signal.HOLD
